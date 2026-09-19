"""The dex side: which Pokémon you can pick, and what the meta says about them.

Two things here are worth a test rather than a glance.

THE SPECIES KEY. dim_pokemon's `base_species_id` collapses regional formes onto the
original, and the build marts do not — they hold `arcanine` and `arcaninehisui` as
separate rows with different builds. Keying on `base_species_id` therefore returns a
different Pokémon's item, nature and spread while looking entirely correct. It read
Arcanine-Hisui as Adamant @ Sitrus Berry against a true Jolly @ Focus Sash, which is
10% of its Attack and the wrong Speed tier. 35 of the 394 pickable entries are
affected.

LEGAL SPREADS. `vgc.incoming` and `vgc.outgoing` use per-stat modal investment, which
is correct for them — only one stat is read per hit, so the combination never
matters. A build panel is the opposite case: the six numbers are shown together and
can be edited, so they have to be a spread somebody could actually run. The marginals
are not: Farigiraf's sum to 71 against a cap of 66.
"""

import pytest

from vgc.dex import (DETAIL_TYPES, MOVE, SPREAD, build_key, dex_entries, entry,
                     format_spread, likely_ability, marginal_spread, meta_build,
                     parse_spread, picker_order, profile, usage_map)
from vgc.edit import problem
from vgc.matchup import damaging
from vgc.metafilter import MetaFilter
from vgc.offense import threats
from vgc.stats import SP_MAX_PER_STAT, SP_MAX_TOTAL, STATS
from vgc.db import session
from vgc.edit import Spread

REG = "M-C"


@pytest.fixture(scope="module")
def meta():
    try:
        rows = threats(REG, 30, MetaFilter())
    except LookupError:
        pytest.skip("marts not built")
    if not rows:
        pytest.skip("no meta rows")
    return rows


# --- which Pokémon you can pick -------------------------------------------------

def test_the_picker_is_the_legal_dex_not_all_1518_rows():
    entries = dex_entries()
    assert entries
    assert len(entries) < 600, "nonstandard rows are leaking into the picker"
    ids = {e.pokemon_id for e in entries}
    assert "bulbasaur" not in ids, "a Past-only species is pickable"


def test_everything_in_the_meta_is_pickable(meta):
    """The one thing this list must never do is hide something people are bringing."""
    ids = {e.pokemon_id for e in dex_entries()}
    missing = [t.display_name for t in meta if t.forme_id not in ids]
    assert not missing, f"in the meta but not pickable: {missing}"


def test_nonstandard_species_are_kept_when_the_data_says_they_are_played():
    """The rule is standard OR seen, not standard alone — otherwise a species the
    dex flags as Past but people demonstrably run would vanish from the picker."""
    with session() as con:
        played = con.execute("""
            select p.pokemon_id from dim_pokemon p
            where p.is_nonstandard is not null
              and (p.pokemon_id in (select forme_id from mart_meta_top)
                   or p.pokemon_id in (select pokemon_id from mart_build_detail))
        """).fetchall()
    if not played:
        pytest.skip("no nonstandard species appear in the landed data")
    ids = {e.pokemon_id for e in dex_entries()}
    assert all(pid in ids for (pid,) in played)


def test_the_picker_opens_on_the_meta(meta):
    ordered = picker_order(REG, MetaFilter())
    assert len(ordered) == len(dex_entries())
    assert ordered[0].pokemon_id == meta[0].forme_id
    assert {e.pokemon_id for e in ordered} == {e.pokemon_id for e in dex_entries()}


def test_an_entry_carries_what_the_calculator_needs():
    e = entry("rillaboom")
    assert e.types == ("Grass",)
    assert set(e.base) == set(STATS) and e.base["atk"] > 0
    assert "grassysurge" in e.abilities
    assert e.bst == sum(e.base.values())


# --- the species key ------------------------------------------------------------

def test_a_regional_forme_reads_its_own_builds_not_the_originals():
    """The bug this guards: base_species_id maps arcaninehisui -> arcanine, and both
    exist in mart_build_detail with genuinely different builds."""
    hisui = entry("arcaninehisui")
    assert hisui.base_species_id == "arcanine", "premise changed; revisit this test"
    assert build_key(hisui) == "arcaninehisui"
    assert meta_build("arcaninehisui", REG).nature != meta_build("arcanine", REG).nature


def test_a_mega_reads_its_base_species_builds():
    """The mirror case: a Mega has no build rows of its own, and should not."""
    mega = entry("salamencemega")
    assert build_key(mega) == "salamence"
    built = meta_build("salamencemega", REG)
    assert built.base == mega.base, "a Mega must use the Mega forme's stats"
    assert built.types == mega.types


def test_no_pickable_entry_borrows_another_species_builds():
    with session() as con:
        keys = {r[0] for r in con.execute(
            "select distinct pokemon_id from mart_build_detail").fetchall()}
    for e in dex_entries():
        key = build_key(e)
        if key in keys and key != e.pokemon_id and not e.is_mega:
            # Only a regional-forme collapse could produce this, and build_key exists
            # precisely to stop it.
            assert e.pokemon_id not in keys, (
                f"{e.pokemon_id} has its own build rows but is reading {key}'s")


def test_likely_ability_agrees_with_the_threat_list(meta):
    """Two implementations of the same rule; they must not drift apart."""
    for t in meta:
        assert likely_ability(entry(t.forme_id), REG) == t.ability_id, t.display_name


# --- what the meta runs ---------------------------------------------------------

def test_profile_usage_matches_the_threat_list(meta):
    for t in meta[:10]:
        p = profile(t.forme_id, REG, MetaFilter())
        assert p.in_meta
        assert p.usage_pct == pytest.approx(t.usage_pct)
        assert p.rank >= 1 and p.sample_size > 0


def test_a_pokemon_nobody_brings_profiles_cleanly():
    """Picking something obscure must produce an empty profile, not an exception."""
    p = profile("furret", REG, MetaFilter())
    assert not p.in_meta and p.usage_pct is None and p.rank is None
    assert not p.has_builds()
    assert all(p.details.get(d) == () for d in DETAIL_TYPES)


def test_details_are_ordered_most_common_first(meta):
    p = profile(meta[0].forme_id, REG, MetaFilter())
    assert p.has_builds()
    for detail_type in DETAIL_TYPES:
        rows = p.details.get(detail_type) or ()
        assert list(rows) == sorted(rows, key=lambda r: -r[1]), detail_type


def test_usage_map_covers_every_meta_forme(meta):
    usage = usage_map(REG, MetaFilter())
    assert all(t.forme_id in usage for t in meta)


# --- legal spreads --------------------------------------------------------------

def test_every_meta_build_is_a_spread_someone_could_run(meta):
    """The panel seeds from these and enforces the cap, so an illegal seed would be
    refused by the editor the moment it rendered."""
    bad = []
    for t in meta:
        built = meta_build(t.forme_id, REG)
        err = problem(Spread(built.nature, built.sp))
        if err:
            bad.append(f"{t.display_name}: {format_spread(built.sp)} — {err}")
    assert not bad, "\n".join(bad)


def test_the_marginals_are_the_reason_that_test_exists(meta):
    """Pins the claim in marginal_spread's docstring rather than asserting it in
    prose: per-stat modes really can exceed the cap."""
    over = []
    for t in meta:
        sp = marginal_spread(build_key(entry(t.forme_id)), REG, MetaFilter())
        if sum(sp.values()) > SP_MAX_TOTAL:
            over.append(f"{t.display_name} {format_spread(sp)} = {sum(sp.values())}")
    assert over, ("no species' marginals exceed the cap any more — if that is a real "
                  "change in the data, meta_build's default can be revisited")


def test_a_meta_build_is_something_the_calculator_can_fire(meta):
    for t in meta[:10]:
        built = meta_build(t.forme_id, REG)
        assert built.forme_id == t.forme_id
        assert built.types == t.types
        assert built.hp > 0
        assert damaging(built.moves), f"{t.display_name} has no damaging move"


def test_marginal_and_modal_agree_for_most_of_the_meta(meta):
    """They differ, but not wildly — if they ever diverged across the board it would
    mean one of the two sources had changed shape."""
    same = sum(
        marginal_spread(build_key(entry(t.forme_id)), REG, MetaFilter())
        == meta_build(t.forme_id, REG).sp
        for t in meta)
    assert same >= len(meta) // 2, f"only {same}/{len(meta)} agree"


@pytest.mark.parametrize("text", ["32/32/0/0/2/0", "0/0/0/0/0/0", "2/0/0/32/0/32"])
def test_spread_text_round_trips(text):
    assert format_spread(parse_spread(text)) == text


def test_a_malformed_spread_is_refused():
    with pytest.raises(ValueError, match="Not a spread"):
        parse_spread("32/32/0")


def test_parsed_spreads_land_in_stat_order():
    assert parse_spread("1/2/3/4/5/6") == dict(zip(STATS, range(1, 7)))
    assert SP_MAX_PER_STAT == 32 and SP_MAX_TOTAL == 66


def test_move_lists_are_ids_the_move_table_knows(meta):
    for t in meta[:10]:
        p = profile(t.forme_id, REG, MetaFilter())
        ids = [v for v, _ in (p.details.get(MOVE) or ())]
        assert ids, t.display_name
        assert all(i == i.lower().replace(" ", "") for i in ids[:4])


def test_spread_details_all_parse(meta):
    for t in meta[:10]:
        for value, _pct in (profile(t.forme_id, REG, MetaFilter()).details.get(SPREAD) or ())[:5]:
            assert sum(parse_spread(value).values()) <= SP_MAX_TOTAL, f"{t.display_name} {value}"
