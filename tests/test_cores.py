"""Teammate cores from the tournament teamlists.

The subtle part is orientation: the mart stores each pair once with a_id < b_id, so
a species can appear on either side and `share` must always be read from YOUR side.
Getting that wrong silently halves the results and reports the wrong percentages.
"""

import pytest

from helpers import full_team_id
from vgc.cores import CHANCE, cores, min_support, partners
from vgc.db import session
from vgc.metafilter import MetaFilter, sample_size
from vgc.team import load_team

REG = "M-C"
PASTE = full_team_id()


@pytest.fixture(scope="module")
def built():
    try:
        with session() as con:
            con.execute("select 1 from mart_meta_cores limit 1")
    except Exception:  # noqa: BLE001
        pytest.skip("marts not built")


@pytest.fixture(scope="module")
def mine(built):
    try:
        return [m.pokemon_id for m in load_team(PASTE)]
    except (FileNotFoundError, LookupError):
        pytest.skip("paste not loaded")


def test_pairs_are_stored_once_in_a_stable_order(built):
    with session() as con:
        bad = con.execute(
            "select count(*) from mart_meta_cores where a_id >= b_id").fetchone()[0]
    assert bad == 0, "pair ordering is not canonical, so partners() would double-count"


def test_lift_matches_its_definition(built):
    """lift = together x total / (teams_a x teams_b). If this drifts, the whole tab lies."""
    with session() as con:
        rows = con.execute("""
            select c.together, c.teams_a, c.teams_b, c.lift,
                   (select max(sample_size) from meta_usage(?, NULL, NULL, NULL, 'teams')) as total
            from mart_meta_cores c where c.together >= 20 limit 50
        """, [REG]).fetchall()
    assert rows
    for together, teams_a, teams_b, lift, total in rows:
        assert lift == pytest.approx(together * total / (teams_a * teams_b))


def test_cores_keeps_only_real_associations(built):
    df = cores(REG)
    assert not df.empty
    assert (df["lift"] > CHANCE).all()
    assert (df["together"] >= min_support(REG)).all()
    assert df["lift"].is_monotonic_decreasing


def test_chance_pairs_are_excluded(built):
    """Rillaboom and Sneasler co-occur more than any other pair and mean nothing by it."""
    df = cores(REG, min_together=1)
    chance = df[(df["a_name"] == "Rillaboom") & (df["b_name"] == "Sneasler")]
    assert chance.empty or chance["lift"].iloc[0] > CHANCE


def test_partners_finds_both_orientations(mine):
    """A species on the b_id side must be found too, not just the a_id side."""
    df = partners(REG, mine)
    assert not df.empty
    with session() as con:
        sides = con.execute("""
            select sum(case when a_id in ? then 1 else 0 end) as as_a,
                   sum(case when b_id in ? then 1 else 0 end) as as_b
            from mart_meta_cores
        """, [mine, mine]).fetchone()
    if sides[0] and sides[1]:
        found = set(df["yours"])
        assert len(found) > 1, "only one orientation is being read"


def test_partners_excludes_what_you_already_run(mine):
    df = partners(REG, mine)
    with session() as con:
        names = {r[0] for r in con.execute(
            "select display_name from dim_pokemon where pokemon_id in ?", [mine]).fetchall()}
    assert not (set(df["partner"]) & names)
    assert set(df["yours"]) <= names


def test_partner_share_is_read_from_your_side(mine):
    """share must be 'of teams running YOUR Pokemon', not the partner's."""
    df = partners(REG, mine)
    assert not df.empty
    row = df.iloc[0]
    with session() as con:
        rec = con.execute("""
            select a_id, b_id, share_of_a, share_of_b from mart_meta_cores
            where (a_name = ? and b_name = ?) or (a_name = ? and b_name = ?)
        """, [row["yours"], row["partner"], row["partner"], row["yours"]]).fetchone()
    a_id, _b_id, share_a, share_b = rec
    expected = share_a if a_id in set(mine) else share_b
    assert row["share"] == pytest.approx(expected)


def test_empty_team_returns_an_empty_frame(built):
    assert partners(REG, []).empty


def test_support_floor_scales_with_the_sample(built):
    """A floor tuned for 1,553 teams would exclude everything in a top-8 view."""
    full = min_support(REG, MetaFilter())
    cut = min_support(REG, MetaFilter(cut=8))
    assert cut < full
    assert cut >= 5
    assert sample_size(REG, MetaFilter(cut=8)) < sample_size(REG)


def test_combos_are_canonically_ordered_and_distinct(built):
    """a < b < c, so each combination is stored once rather than six times."""
    from vgc.db import session
    with session() as con:
        bad = con.execute("""
            select count(*) from mart_meta_combos
            where not (a_id < b_id and b_id < c_id)
        """).fetchone()[0]
    assert bad == 0


def test_combos_rank_by_frequency(built):
    from vgc.cores import combos
    df = combos(REG, limit=10)
    assert not df.empty
    assert df["together"].is_monotonic_decreasing
    assert (df["share"] > 0).all() and (df["share"] <= 1).all()


def test_combos_can_be_filtered_to_your_own_picks(built, mine):
    from vgc.cores import combos
    df = combos(REG, limit=50, contains=mine)
    assert not df.empty
    for a, b, c in zip(df["a_id"], df["b_id"], df["c_id"]):
        assert {a, b, c} & set(mine), "a combination with none of my Pokémon slipped through"
