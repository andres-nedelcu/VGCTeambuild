"""Swaps: what a replacement closes, and what it costs.

The add view assumed a free slot, which a locked team does not have. The claim this
view makes — "this swap opens a hole" — is the one that has to be right, because it
is the reason to reject an otherwise attractive candidate.
"""

import pytest

from helpers import full_team_id
from vgc.defense import defense_matrix, flagged_types, summarize
from vgc.megas import resolve_team
from vgc.metafilter import MetaFilter
from vgc.offense import attackers, coverage_matrix, holes, threats
from vgc.swap import sole_coverage, swaps
from vgc.team import load_team

REG = "M-C"
PASTE = full_team_id()
TOP_N = 20


@pytest.fixture(scope="module")
def ctx():
    try:
        team = load_team(PASTE)
    except (FileNotFoundError, LookupError):
        pytest.skip("paste not loaded")
    formes = resolve_team(team, None)
    try:
        meta = threats(REG, TOP_N)
    except LookupError:
        pytest.skip("marts not built")
    if not meta:
        pytest.skip("no meta rows")
    base = attackers(team, formes)
    gaps = set(holes(coverage_matrix(base, meta)))
    flags = set(flagged_types(summarize(defense_matrix(formes))))
    return team, formes, meta, gaps, flags, swaps(REG, team, formes, MetaFilter(), TOP_N)


def test_there_are_swaps_to_consider(ctx):
    *_, rows = ctx
    assert rows


def test_sole_coverage_matches_a_direct_recomputation(ctx):
    """Independently remove each Pokémon and compare the holes that appear."""
    team, formes, meta, gaps, _flags, _rows = ctx
    computed = sole_coverage(REG, team, formes, MetaFilter(), TOP_N)
    base = attackers(team, formes)
    for a in base:
        kept = [x for x in base if x.slot != a.slot]
        expected = tuple(sorted(set(holes(coverage_matrix(kept, meta))) - gaps))
        assert computed[a.slot] == expected


def test_a_swap_can_only_open_what_the_outgoing_uniquely_covered(ctx):
    """The load-bearing invariant: holes_opened must be drawn from out_sole_cover."""
    *_, rows = ctx
    for s in rows:
        assert set(s.holes_opened) <= set(s.out_sole_cover), (
            f"{s.out_name} -> {s.in_name} opened something it did not uniquely cover")


def test_closed_and_opened_are_disjoint_from_each_other(ctx):
    *_, rows = ctx
    for s in rows:
        assert not (set(s.holes_closed) & set(s.holes_opened))


def test_closed_holes_were_holes_and_opened_ones_were_not(ctx):
    _team, _formes, _meta, gaps, _flags, rows = ctx
    for s in rows:
        assert set(s.holes_closed) <= gaps
        assert not (set(s.holes_opened) & gaps)


def test_net_is_the_difference(ctx):
    *_, rows = ctx
    for s in rows:
        assert s.net_holes == len(s.holes_closed) - len(s.holes_opened)
        assert s.net_flags == len(s.flags_cleared) - len(s.flags_raised)


def test_nothing_already_on_the_team_is_offered(ctx):
    team, *_, rows = ctx
    mine = {m.pokemon_id for m in team}
    for s in rows:
        assert s.in_species_id not in mine and s.in_forme_id not in mine


def test_some_swap_actually_costs_something(ctx):
    """Guards the whole feature: if nothing ever opens, 'Opens' is dead weight and
    the view has silently regressed to the add view."""
    *_, rows = ctx
    assert any(s.holes_opened for s in rows), "no swap opens a hole — is it computed?"


def test_limiting_to_one_slot_returns_only_that_slot(ctx):
    team, formes, *_ = ctx
    slot = formes[0].slot
    rows = swaps(REG, team, formes, MetaFilter(), TOP_N, out_slot=slot)
    assert rows
    assert {s.out_slot for s in rows} == {slot}


def test_ranking_is_the_stated_lexicographic_order(ctx):
    *_, rows = ctx
    keys = [s.rank_key for s in rows]
    assert keys == sorted(keys, reverse=True)


def test_an_impossible_filter_yields_nothing(ctx):
    team, formes, *_ = ctx
    assert swaps(REG, team, formes, MetaFilter(min_players=10_000), TOP_N) == []
