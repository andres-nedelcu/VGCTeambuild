"""Item-conditioned cores, and the failure mode that motivated them.

Species-level co-occurrence averages a species' builds together. When two builds want
opposite partners they cancel, and a near-deterministic partnership reads as chance.
Sneasler is the worked example and is pinned here: Unburden plus a terrain seed that
the terrain consumes, split between Grassy Seed (Rillaboom) and Psychic Seed
(Indeedee). If these numbers ever move, the item view has stopped working.
"""

import pytest

from vgc.cores import cores, item_cores
from vgc.db import session
from vgc.metafilter import MetaFilter

REG = "M-C"


@pytest.fixture(scope="module")
def built():
    try:
        with session() as con:
            con.execute("select 1 from mart_meta_item_cores limit 1")
    except Exception:  # noqa: BLE001
        pytest.skip("marts not built")


@pytest.fixture(scope="module")
def sneasler(built):
    df = item_cores(REG, min_delta=0.0)
    df = df[df["holder_id"] == "sneasler"]
    if df.empty:
        pytest.skip("Sneasler not in the landed data")
    return df


def test_grassy_seed_sneasler_brings_rillaboom(sneasler):
    row = sneasler[(sneasler["item_id"] == "grassyseed")
                   & (sneasler["partner_id"] == "rillaboom")]
    assert not row.empty, "Grassy Seed Sneasler / Rillaboom pairing has disappeared"
    assert row["share"].iloc[0] > 0.90
    assert row["delta"].iloc[0] > 0.25


def test_psychic_seed_sneasler_brings_indeedee_instead(sneasler):
    row = sneasler[(sneasler["item_id"] == "psychicseed")
                   & (sneasler["partner_id"] == "indeedeef")]
    assert not row.empty
    assert row["share"].iloc[0] > row["base_share"].iloc[0] + 0.25


def test_the_two_seeds_point_at_different_partners(sneasler):
    """The mechanism: each seed implies its own terrain setter, not the other's."""
    def share(item, partner):
        row = sneasler[(sneasler["item_id"] == item) & (sneasler["partner_id"] == partner)]
        return float(row["share"].iloc[0]) if not row.empty else 0.0

    assert share("grassyseed", "rillaboom") > share("grassyseed", "indeedeef")
    assert share("psychicseed", "indeedeef") > share("psychicseed", "rillaboom")


def test_species_level_lift_hides_this_pairing(built):
    """Documents the failure mode rather than asserting it is fine.

    Sneasler and Rillaboom co-occur about as often as chance predicts *because* the
    Psychic Seed builds pull the other way. If a future change makes this pair look
    strongly associated at species level, the item view may no longer be needed — but
    someone should notice and decide that deliberately.
    """
    df = cores(REG, min_together=1)
    pair = df[((df["a_id"] == "sneasler") & (df["b_id"] == "rillaboom"))
              | ((df["a_id"] == "rillaboom") & (df["b_id"] == "sneasler"))]
    if pair.empty:
        return  # dropped for lift <= 1, which is the same story
    assert pair["lift"].iloc[0] < 1.5, (
        "species-level lift now shows this pair as associated; re-check whether the "
        "item-conditioned view is still the right presentation")


def test_lift_cannot_exceed_its_ceiling(built):
    """lift <= 1 / the more common member's usage. A Pokemon on 54% of teams can
    never show more than 1.85 with anything, which is why a low lift is not proof
    of independence for a very common species."""
    with session() as con:
        rows = con.execute("""
            select c.lift, c.teams_a, c.teams_b,
                   (select max(sample_size) from meta_usage(?, NULL, NULL, NULL, 'teams'))
            from mart_meta_cores c where c.together >= 20 limit 200
        """, [REG]).fetchall()
    assert rows
    for lift, teams_a, teams_b, total in rows:
        assert lift <= total / max(teams_a, teams_b) + 1e-9


def test_delta_is_the_gap_between_the_two_shares(built):
    df = item_cores(REG, min_delta=0.0)
    assert not df.empty
    assert ((df["share"] - df["base_share"] - df["delta"]).abs() < 1e-9).all()
    assert df["share"].between(0, 1).all()
    assert df["base_share"].between(0, 1).all()


def test_holders_filter_limits_to_that_team(built):
    df = item_cores(REG, holders=["sneasler"])
    assert not df.empty
    assert set(df["holder_id"]) == {"sneasler"}


def test_results_are_sorted_by_the_gap(built):
    df = item_cores(REG)
    assert df["delta"].is_monotonic_decreasing


def test_an_unknown_holder_yields_nothing(built):
    assert item_cores(REG, holders=["notarealpokemon"]).empty
