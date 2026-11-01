"""Meta-side filtering: the MetaFilter contract, and that it reproduces fact_usage.

The load-bearing test here is test_unfiltered_reproduces_fact_usage. The marts moved
off the fact_usage rollup onto a live aggregation of fact_tournament_set so the meta
could be filtered at all; if the unfiltered path ever stops matching fact_usage, the
refactor has quietly changed every number in the app.
"""

from datetime import date

import pytest

from helpers import full_team_id
from vgc.db import session
from vgc.megas import resolve_team
from vgc.metafilter import TEAMS, THIN_SAMPLE, WINS, MetaFilter, sample_size
from vgc.offense import threats
from vgc.pressure import rank
from vgc.speed import meta_speed
from vgc.team import load_team

REG = "M-C"
PASTE = full_team_id()


@pytest.fixture(scope="module")
def built():
    """Skip the whole module unless the marts are built against real data."""
    try:
        with session() as con:
            if not con.execute(
                "select count(*) from fact_usage where source = 'limitless'").fetchone()[0]:
                pytest.skip("no limitless usage loaded")
            con.execute("select 1 from meta_usage(NULL, NULL, NULL, NULL, 'teams') limit 1")
    except Exception:  # noqa: BLE001
        pytest.skip("marts not built")


# --- the contract, no warehouse needed --------------------------------------

def test_default_is_no_filter():
    assert MetaFilter().is_default
    assert not MetaFilter(cut=16).is_default
    assert not MetaFilter(weight=WINS).is_default


def test_params_order_matches_the_macro_signature():
    f = MetaFilter(cut=8, since=date(2026, 9, 12), min_players=64, weight=WINS)
    assert f.params(REG) == [REG, 8, date(2026, 9, 12), 64, WINS]


def test_every_parameter_is_cast():
    """DuckDB cannot infer a type for a NULL parameter, and four of the five may be
    NULL, so every placeholder is cast explicitly rather than only the nullable ones."""
    call = MetaFilter().call("meta_top")
    assert call.count("?") == len(MetaFilter().params("M-C")) == 5
    assert call.count("CAST(?") == 5


def test_bad_weight_and_cut_are_rejected():
    with pytest.raises(ValueError):
        MetaFilter(weight="winrate")
    with pytest.raises(ValueError):
        MetaFilter(cut=0)


def test_label_describes_what_is_included():
    assert MetaFilter().label() == "all finishers"
    assert MetaFilter(cut=16, weight=WINS).label() == "top 16 finishers, weighted by wins"


# --- against the warehouse ---------------------------------------------------

def test_unfiltered_reproduces_fact_usage(built):
    """The whole refactor rests on this: no filter must mean the old numbers."""
    with session() as con:
        rows = con.execute("""
            select count(*) as n,
                   sum(case when abs(m.usage_pct - f.usage_pct) > 1e-12 then 1 else 0 end),
                   sum(case when m.sample_size <> f.sample_size then 1 else 0 end)
            from meta_usage(?, NULL, NULL, NULL, 'teams') m
            full join (select * from fact_usage
                       where source = 'limitless' and regulation = ?) f
              on f.pokemon_id = m.pokemon_id and f.regulation = m.regulation
        """, [REG, REG]).fetchone()
    n, pct_mismatch, size_mismatch = rows
    assert n > 0
    assert pct_mismatch == 0, f"{pct_mismatch} of {n} species disagree on usage_pct"
    assert size_mismatch == 0
    # rank is deliberately allowed to differ: the loader ties-breaks by Python sort
    # order, the macro by pokemon_id, and nothing reads species_rank.


def test_a_cut_shrinks_the_sample_and_keeps_percentages_valid(built):
    full = sample_size(REG)
    cut = sample_size(REG, MetaFilter(cut=16))
    assert 0 < cut < full
    metas = threats(REG, 10, MetaFilter(cut=16))
    assert metas and all(0 < t.usage_pct <= 1 for t in metas)


def test_win_weighting_keeps_every_team_in_the_sample(built):
    """Weighting changes each team's contribution, not who is counted."""
    assert sample_size(REG, MetaFilter(weight=WINS)) == sample_size(REG, MetaFilter(weight=TEAMS))


def test_a_cut_can_reorder_the_meta(built):
    """Not an assertion about any one Pokemon -- just that the filter actually bites."""
    plain = [t.forme_id for t in threats(REG, 15)]
    cut = [t.forme_id for t in threats(REG, 15, MetaFilter(cut=16))]
    assert plain != cut, "a top-16 cut produced an identical ranking; is it being applied?"


def test_an_impossible_filter_selects_nothing_without_raising(built):
    assert sample_size(REG, MetaFilter(min_players=10_000)) == 0
    assert threats(REG, 10, MetaFilter(min_players=10_000)) == []


def test_thin_sample_constant_is_below_the_unfiltered_sample(built):
    """The warning threshold has to be reachable, or it never fires."""
    assert THIN_SAMPLE < sample_size(REG)


def test_speed_and_pressure_accept_the_same_filter(built):
    """All three tabs read the meta through one filter, so they cannot disagree."""
    filt = MetaFilter(cut=16)
    try:
        team = load_team(PASTE)
    except (FileNotFoundError, LookupError):
        pytest.skip("paste not loaded")
    assert not meta_speed(REG, 10, filt).empty
    assert rank(REG, resolve_team(team, None), 10, filt)
