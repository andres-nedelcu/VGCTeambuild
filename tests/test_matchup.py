"""Arbitrary build vs arbitrary build, pinned two ways.

The risk this module carries is not that the formula is wrong — `vgc.damage` is
already pinned roll for roll against Showdown's own simulator. The risk is that
`vgc.matchup` assembles the *inputs* to that formula differently from the two modules
that were verified: a stage applied after an item instead of before, a defender's HP
taken with its nature, a spread flag read from the wrong place. Every one of those
produces plausible numbers that are quietly wrong.

So there are two independent pins:

  AGAINST THE SIMULATOR   every reference case whose spread flag agrees with
                          dim_move is rebuilt as two `Build`s and fired through
                          `versus()`, end to end, and must reproduce all sixteen
                          rolls. This also checks `Build.stat` and `Build.hp` against
                          what the simulator reports for the same set.

  AGAINST THE TEAM PATH   `versus()` must reproduce `outgoing()` and `incoming()`
                          row for row when handed the same builds. Those two are the
                          shipped, verified damage paths; if this module ever drifts
                          from them, that is the definition of a regression.

Regenerate the reference after touching anything in vgc.damage:
    node scripts/showdown_damage.js tests/fixtures/damage_cases.json \
        > tests/fixtures/damage_reference.json
"""

import json

import pytest

from vgc import REPO_ROOT
from vgc.damage import spreads_in_terrain
from vgc.db import session
from vgc.dex import likely_ability, meta_build
from vgc.ids import to_id
from vgc.incoming import incoming
from vgc.matchup import (ATTACKER, DEFENDER, Build, base_stats, damaging, move_data,
                         team_builds, versus)
from vgc.megas import resolve_team
from vgc.metafilter import MetaFilter
from vgc.offense import threats
from vgc.outgoing import outgoing
from vgc.stats import STATS
from vgc.team import list_teams, load_team

REG = "M-C"
TOP_N = 10
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "damage_reference.json"
WEATHER = {"raindance": "rain", "sunnyday": "sun"}
TERRAIN = {"grassyterrain": "grassy", "psychicterrain": "psychic",
           "electricterrain": "electric"}


@pytest.fixture(scope="module")
def reference():
    if not FIXTURE.exists():
        pytest.skip("run scripts/showdown_damage.js to build the reference")
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def dex_types():
    try:
        with session() as con:
            return {r[0]: tuple(t for t in r[1:] if t) for r in con.execute(
                "select pokemon_id, type1, type2 from dim_pokemon").fetchall()}
    except Exception:  # noqa: BLE001
        pytest.skip("warehouse not available")


@pytest.fixture(scope="module")
def ctx():
    full = [t for t in list_teams() if len(t.members) > 1]
    if not full:
        pytest.skip("no multi-Pokémon team saved")
    team = load_team(full[0].id)
    formes = resolve_team(team, None)
    try:
        meta = threats(REG, TOP_N, MetaFilter())
    except LookupError:
        pytest.skip("marts not built")
    if not meta:
        pytest.skip("no meta rows")
    return team, formes, meta


def _build(spec, types, moves=()):
    species = to_id(spec["species"])
    sp = dict.fromkeys(STATS, 0)
    sp.update({k: int(v) for k, v in (spec.get("evs") or {}).items()})
    return Build(
        forme_id=species, display_name=spec["species"], types=types[species],
        base=base_stats(species),
        ability_id=to_id(spec.get("ability") or "") or None,
        item_id=to_id(spec.get("item") or "") or None,
        nature=(spec.get("nature") or "").lower() or None,
        sp=sp, moves=tuple(moves))


def _consistent(case):
    """Cases whose `spread` flag agrees with the one `versus()` derives for itself.

    Seven reference cases fire Earthquake at a single target with `spread` forced
    off, and one fires Expanding Force at a single target in Psychic Terrain, where
    the move becomes a spread move. Both are legitimate things to pin in isolation,
    and neither can be driven through a Build: `versus()` reads the flag from
    dim_move and from `spreads_in_terrain`, and does not take an override, because
    inventing one for a test would make the production path less honest, not more.
    """
    move_id = to_id(case["move"])
    derived = move_data()[move_id][4] or spreads_in_terrain(
        TERRAIN.get(case.get("terrain")), move_id)
    return bool(case.get("spread")) == derived


# --- pinned against the simulator, end to end -----------------------------------

def test_versus_reproduces_the_simulator_roll_for_roll(reference, dex_types):
    checked, mismatches = 0, []
    for case in reference:
        if not _consistent(case):
            continue
        move_id = to_id(case["move"])
        attacker = _build(case["attacker"], dex_types, [move_id])
        defender = _build(case["defender"], dex_types)
        category = move_data()[move_id][2]
        akey = "atk" if category == "Physical" else "spa"
        dkey = "def" if category == "Physical" else "spd"
        rows = versus(
            attacker, defender,
            weather=WEATHER.get(case.get("weather")),
            terrain=TERRAIN.get(case.get("terrain")),
            atk_stage=(case["attacker"].get("boosts") or {}).get(akey, 0),
            def_stage=(case["defender"].get("boosts") or {}).get(dkey, 0),
            unknown=None)
        if not rows:
            continue
        got = rows[0].as_set.rolls
        if got != tuple(case["rolls"]):
            mismatches.append(f"{case['name']}: showdown={tuple(case['rolls'])} mine={got}")
        checked += 1
    assert checked >= 15, f"only {checked} reference cases were drivable end to end"
    assert not mismatches, "\n".join(mismatches)


def test_build_stats_match_what_the_simulator_reports(reference, dex_types):
    """Build.stat and Build.hp, against storedStats and maxhp for the same set.

    storedStats rather than getStat: getStat folds items in, and the point is that
    Build produces the raw figure that vgc.damage then modifies itself.
    """
    checked = 0
    for case in reference:
        defender = _build(case["defender"], dex_types)
        assert defender.hp == case["defender_hp"], case["name"]
        for key, value in case["defender_stats_raw"].items():
            assert defender.stat(key) == value, f"{case['name']} {key}"
        attacker = _build(case["attacker"], dex_types)
        for key, value in case["attacker_stats_raw"].items():
            assert attacker.stat(key) == value, f"{case['name']} {key}"
        checked += 1
    assert checked, "no reference cases"


def test_the_dex_cases_exist_and_cover_the_new_path(reference):
    """The three cases added for this feature: two arbitrary builds, single target,
    covering the base-power, stage and item branches that the Earthquake cases
    cannot reach because their spread flag is forced."""
    named = [c["name"] for c in reference if c["name"].startswith("dex: ")]
    assert len(named) >= 3, named
    joined = " ".join(named)
    assert "Terrain" in joined and "-1 Atk" in joined and "Choice Band" in joined


# --- pinned against the two shipped damage paths --------------------------------

def test_versus_reproduces_outgoing(ctx):
    """Your team into the meta. Same builds in, same sixteen rolls out."""
    team, formes, _meta = ctx
    rows = outgoing(REG, team, formes, MetaFilter(), TOP_N, per_move=True)
    assert rows, "nothing to compare against"
    mine = {b.forme_id: b for b in team_builds(team, formes)}
    by_slot = {f.slot: f for f in formes}
    cache: dict[str, Build] = {}

    checked = 0
    for row in rows:
        attacker = mine[by_slot[row.attacker_slot].forme_id]
        key = row.threat.forme_id
        if key not in cache:
            # marginal=True because that is what outgoing reads: per-stat modes, not
            # a real spread. See vgc.dex.marginal_spread for why it is not the default.
            cache[key] = meta_build(key, REG, MetaFilter(), marginal=True)
        got = versus(attacker, cache[key], unknown=DEFENDER, moves=[row.move_id])
        assert got, f"{attacker.display_name} -> {row.threat.display_name} {row.move_id}"
        label = f"{attacker.display_name} {row.move_id} -> {row.threat.display_name}"
        assert got[0].as_set.rolls == row.likely.rolls, label
        assert got[0].worst.rolls == row.bulkiest.rolls, label
        assert got[0].as_set.defender_hp == row.likely.defender_hp, label
        assert got[0].worst.defender_hp == row.bulkiest.defender_hp, label
        checked += 1
    assert checked > 20, f"only {checked} matchups compared"


def test_versus_reproduces_incoming(ctx):
    """The meta into your team, with the unknown side swapped over."""
    team, formes, _meta = ctx
    rows = incoming(REG, team, formes, MetaFilter(), TOP_N)
    assert rows, "nothing to compare against"
    mine = {f.slot: b for f, b in zip(formes, team_builds(team, formes))}
    with session() as con:
        move_ids = {name: mid for mid, name in con.execute(
            "select move_id, display_name from dim_move").fetchall()}
    cache: dict[str, Build] = {}

    checked = 0
    for row in rows:
        move_id = move_ids.get(row.likely.move_name)
        if move_id is None:
            continue
        key = row.threat.forme_id
        if key not in cache:
            cache[key] = meta_build(key, REG, MetaFilter(), marginal=True)
        got = versus(cache[key], mine[row.target_slot], unknown=ATTACKER,
                     moves=[move_id])
        assert got, f"{row.threat.display_name} {move_id} -> {row.target_name}"
        label = f"{row.threat.display_name} {move_id} -> {row.target_name}"
        assert got[0].as_set.rolls == row.likely.rolls, label
        assert got[0].worst.rolls == row.worst.rolls, label
        checked += 1
    assert checked > 10, f"only {checked} matchups compared"


# --- the two-figure contract ----------------------------------------------------

def test_an_unknown_defender_can_only_take_less(ctx):
    team, formes, meta = ctx
    attacker = team_builds(team, formes)[0]
    seen = 0
    for threat in meta:
        defender = meta_build(threat.forme_id, REG)
        for m in versus(attacker, defender, unknown=DEFENDER):
            assert m.worst.low <= m.as_set.low, f"{m.move_name} -> {threat.display_name}"
            assert m.worst.defender_hp >= m.as_set.defender_hp
            seen += 1
    assert seen, "no damaging moves at all"


def test_an_unknown_attacker_can_only_hit_harder(ctx):
    team, formes, meta = ctx
    defender = team_builds(team, formes)[0]
    seen = 0
    for threat in meta:
        attacker = meta_build(threat.forme_id, REG)
        for m in versus(attacker, defender, unknown=ATTACKER):
            assert m.worst.low >= m.as_set.low, f"{threat.display_name} {m.move_name}"
            assert m.worst.defender_hp == m.as_set.defender_hp
            seen += 1
    assert seen, "no damaging moves at all"


def test_both_sides_known_reports_one_number(ctx):
    """When nothing is being guessed, the second figure must not invent a range."""
    team, formes, _meta = ctx
    builds = team_builds(team, formes)
    rows = versus(builds[0], builds[-1], unknown=None)
    assert rows, "the team's first Pokémon has no damaging move"
    for m in rows:
        assert m.certain
        assert m.worst.rolls == m.as_set.rolls
        assert m.kos == m.as_set_kos


def test_an_unrecognised_unknown_side_is_refused(ctx):
    team, formes, _meta = ctx
    builds = team_builds(team, formes)
    with pytest.raises(ValueError, match="unknown must be"):
        versus(builds[0], builds[1], unknown="either")


def test_status_moves_are_dropped_not_zeroed(ctx):
    """A Protect row reading '0 damage' is noise; it should not be a row at all."""
    assert damaging(["protect", "earthquake", "trickroom"]) == ["earthquake"]
    team, formes, _meta = ctx
    builds = team_builds(team, formes)
    for b in builds:
        rows = versus(b, builds[0], unknown=None)
        assert len(rows) == len(damaging(b.moves))


def test_results_are_ordered_by_the_figure_you_can_rely_on(ctx):
    team, formes, meta = ctx
    attacker = team_builds(team, formes)[0]
    rows = versus(attacker, meta_build(meta[0].forme_id, REG), unknown=DEFENDER)
    assert rows == sorted(rows, key=lambda m: m.worst.low, reverse=True)
