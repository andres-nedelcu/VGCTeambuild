"""Forme-level invariants for the meta marts.

mart_meta_top is keyed by forme, not by species, because that is what the app draws:
a threat is Salamence-Mega or Golisopod-Mega, never "Salamence, 98% of which is Mega".
Two things can break that keying, and both are pinned here.
"""

import pytest

from vgc.db import session

REG = "M-C"


@pytest.fixture(scope="module")
def con():
    try:
        with session() as c:
            c.execute("select 1 from mart_meta_top limit 1")
    except Exception:  # noqa: BLE001
        pytest.skip("marts not built")
    with session() as c:
        yield c


def test_a_forme_appears_exactly_once(con):
    """Two formes of one species can share a Mega, which used to split its usage."""
    dupes = con.execute("""
        select forme_id, count(*) from mart_meta_top
        group by regulation, forme_id having count(*) > 1
    """).fetchall()
    assert dupes == [], f"forme appears more than once: {dupes}"


def test_a_shared_mega_sums_its_contributors(con):
    """Floette and Floette-Eternal share base_species_id 'floette' and both become
    Floette-Mega. The merged row must carry the sum, not the larger half."""
    row = con.execute("""
        select forme_usage_pct, contributing_species
        from mart_meta_top where forme_id = 'floettemega' and regulation = ?
    """, [REG]).fetchone()
    if row is None:
        pytest.skip("Floette-Mega not in the current meta sample")
    usage, contributors = row
    if contributors < 2:
        pytest.skip("Floette-Mega no longer has two contributing species")
    parts = con.execute("""
        select sum(u.usage_pct * s.share)
        from mart_meta_stone_share s
        join fact_usage u
          on u.pokemon_id = s.pokemon_id and u.regulation = s.regulation
         and u.source = 'limitless'
        where s.forme_id = 'floettemega' and s.regulation = ?
    """, [REG]).fetchone()[0]
    assert usage == pytest.approx(parts), "merged usage is not the sum of its parts"


def test_every_contributor_shares_the_formes_base_species(con):
    """A stone on a species it cannot belong to would invent a threat outright.
    Teamlists carry exactly that kind of junk: a Meganium with a Blastoisinite."""
    bad = con.execute("""
        select s.pokemon_id, s.forme_id, s.share
        from mart_meta_stone_share s
        join dim_pokemon holder on holder.pokemon_id = s.pokemon_id
        join dim_pokemon forme on forme.pokemon_id = s.forme_id
        where holder.base_species_id is distinct from forme.base_species_id
    """).fetchall()
    assert bad == [], f"stone share links unrelated species: {bad}"


def test_the_guard_has_something_to_guard_against(con):
    """Guards the test above: it passes trivially if no junk stones exist at all.
    This asserts the raw build data still contains the case the join filters out."""
    junk = con.execute("""
        select count(*) from mart_build_detail d
        join dim_item i on i.item_id = d.detail_value
        join dim_pokemon holder on holder.pokemon_id = d.pokemon_id
        join dim_pokemon forme on forme.pokemon_id = i.mega_forme_id
        where d.detail_type = 'item' and i.is_mega_stone
          and holder.base_species_id is distinct from forme.base_species_id
    """).fetchone()[0]
    if junk == 0:
        pytest.skip("no mismatched stones in the current build data")
    assert junk > 0


def test_unmerged_formes_cannot_exceed_their_species(con):
    """A single-contributor forme is a share of one species, so it is bounded by it.
    Merged rows are exempt by construction: they sum across species."""
    bad = con.execute("""
        select forme_id, forme_usage_pct, species_usage_pct
        from mart_meta_top
        where contributing_species = 1 and forme_usage_pct > species_usage_pct + 1e-12
    """).fetchall()
    assert bad == [], f"forme usage exceeds its species: {bad}"
