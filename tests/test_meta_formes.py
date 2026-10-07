"""Forme-level invariants for the meta marts.

mart_meta_top is keyed by forme, not by species, because that is what the app draws:
a threat is Salamence-Mega or Golisopod-Mega, never "Salamence, 98% of which is Mega".
Two things can break that keying, and both are pinned here.
"""

import pytest

from vgc.db import load_settings, session

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


def test_a_mega_forme_carries_no_choice_scarf_benchmark(con):
    """A Mega is holding its stone, so a Scarfed Speed for it cannot exist.

    The Scarf share behind the flag is the BASE species' — Scarf Salamence is a real
    set — so before this, a Mega inherited it and `vgc.speed.ceiling` judged the Mega
    against a Speed it can never reach. Staraptor-Mega is the live case at 21.9%,
    over the 20% threshold, reading "Depends" where the answer was "You outspeed".
    """
    bad = con.execute("""
        select s.display_name, s.scarf_flag, s.spe_max_plus_scarf, s.spe_max_neutral_scarf
        from mart_meta_speed s
        join mart_meta_top t
          on t.forme_id = s.forme_id and t.regulation = s.regulation
        where t.is_mega and (s.scarf_flag
                             or s.spe_max_plus_scarf is not null
                             or s.spe_max_neutral_scarf is not null)
    """).fetchall()
    assert bad == [], f"Mega formes still carrying a Scarf benchmark: {bad}"


def test_the_mega_scarf_rule_has_numbers_to_suppress(con):
    """Guards the NUMBERS half of the test above. The mart nulls both Scarf columns on
    `is_mega` alone, with no reference to the share, so every Mega row would carry them
    if that CASE were removed. The only way this half goes vacuous is a meta with no
    Mega in it at all, which is what this asserts against."""
    megas = con.execute("select count(*) from mart_meta_top where is_mega").fetchone()[0]
    assert megas > 0, "no Mega forme in the meta sample, so the NULL columns prove nothing"


def test_the_mega_scarf_rule_has_a_flag_to_suppress(con):
    """Guards the FLAG half, which is a fact about the meta rather than about the code:
    `scarf_flag` only differs from the unsuppressed rule for a Mega whose BASE species
    is over the threshold. Staraptor-Mega was that case at 21.9%.

    It is no longer: the share comes from build data and the meta moved under it —
    Staraptor-Mega is the highest at 0.140 against a 0.20 threshold, and the gap has
    widened, not closed. So this skips rather than re-pinning the comparison lower.
    Re-pinning would be the worse of the two: the mart flags at defaults.scarf_threshold,
    so a guard that accepted 0.14 would pass while the flag half stayed vacuous — the
    one failure mode a guard exists to prevent. The threshold is read from settings
    rather than written here so this cannot test a different number than the mart uses.
    """
    threshold = load_settings()["defaults"]["scarf_threshold"]
    top = con.execute("""
        select s.display_name, s.scarf_share
        from mart_meta_speed s
        join mart_meta_top t
          on t.forme_id = s.forme_id and t.regulation = s.regulation
        where t.is_mega
        order by s.scarf_share desc
        limit 1
    """).fetchone()
    if top is None or top[1] < threshold:
        highest = f"highest is {top[0]} at {top[1]:.3f}" if top else "no Mega rows at all"
        pytest.skip(f"no Mega forme's base species reaches the {threshold:g} Choice Scarf "
                    f"threshold ({highest}), so the flag half of the rule above is "
                    f"vacuous today — the numbers half is still pinned")
    assert top[1] >= threshold


def test_a_non_mega_keeps_its_scarf_benchmark(con):
    """The suppression must be surgical: ordinary formes still get both numbers."""
    rows = con.execute("""
        select count(*) from mart_meta_speed s
        join mart_meta_top t
          on t.forme_id = s.forme_id and t.regulation = s.regulation
        where not t.is_mega and s.scarf_flag and s.spe_max_plus_scarf is not null
    """).fetchone()[0]
    assert rows > 0, "no ordinary forme is flagged for Scarf any more"
