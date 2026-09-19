"""The damage formula, pinned against Pokémon Showdown's own simulator.

Every other number in this tool is an annotation with a stated limit. This one is a
claim: "that move takes 112% of your HP" is either right or it is misinformation.

So it is not verified by reading the source and agreeing with myself. `tests/fixtures/
damage_reference.json` is produced by `scripts/showdown_damage.js`, which drives the
actual simulator in the pinned vendor/ checkout and reports what it computes. This
module asserts that vgc.damage reproduces it exactly, roll for roll — not the range,
all sixteen values, because a rounding error usually moves only one or two of them.

Regenerate after touching anything here:
    node scripts/showdown_damage.js tests/fixtures/damage_cases.json \
        > tests/fixtures/damage_reference.json
"""

import json

import pytest

from vgc import REPO_ROOT
from vgc.damage import (attack_after_item, base_power_multiplier, boosted,
                        damage_rolls, defence_after_item, final_multiplier,
                        weather_multiplier)
from vgc.db import session
from vgc.ids import to_id
from vgc.typechart import effectiveness

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "damage_reference.json"
WEATHER = {"raindance": "rain", "sunnyday": "sun"}
TERRAIN = {"grassyterrain": "grassy", "psychicterrain": "psychic",
           "electricterrain": "electric"}


@pytest.fixture(scope="module")
def reference():
    if not FIXTURE.exists():
        pytest.skip("run scripts/showdown_damage.js to build the reference")
    cases = json.loads(FIXTURE.read_text())
    assert cases, "reference fixture is empty"
    return cases


@pytest.fixture(scope="module")
def dex():
    try:
        with session() as con:
            moves = {r[0]: r[1:] for r in con.execute(
                "select move_id, base_power, type, category from dim_move").fetchall()}
            mons = {r[0]: tuple(t for t in r[1:] if t) for r in con.execute(
                "select pokemon_id, type1, type2 from dim_pokemon").fetchall()}
    except Exception:  # noqa: BLE001
        pytest.skip("warehouse not available")
    return moves, mons


def _inputs(case, dex):
    moves, mons = dex
    move_id = to_id(case["move"])
    base_power, move_type, category = moves[move_id]
    atk_types = mons[to_id(case["attacker"]["species"])]
    def_types = mons[to_id(case["defender"]["species"])]
    type_mult = effectiveness(move_type, def_types, None)

    # Raw, pre-item stats: Showdown's getStat() already folds items in, so starting
    # from those would bypass the item handling this is meant to check.
    raw_atk = case["attacker_stats_raw"]["atk" if category == "Physical" else "spa"]
    raw_def = case["defender_stats_raw"]["def" if category == "Physical" else "spd"]
    atk_item = to_id(case["attacker"].get("item") or "") or None
    def_item = to_id(case["defender"].get("item") or "") or None

    # Stage first, item second — sim/pokemon.ts:583 boosts before battle.modify().
    atk_stage = (case["attacker"].get("boosts") or {}).get(
        "atk" if category == "Physical" else "spa", 0)
    def_stage = (case["defender"].get("boosts") or {}).get(
        "def" if category == "Physical" else "spd", 0)

    return dict(
        base_power=base_power,
        attack=attack_after_item(boosted(raw_atk, atk_stage), atk_item, category),
        defense=defence_after_item(boosted(raw_def, def_stage), def_item, category),
        type_mult=type_mult,
        stab=move_type in atk_types,
        spread=bool(case.get("spread")),
        weather_mult=weather_multiplier(WEATHER.get(case.get("weather")), move_type),
        final_mult=final_multiplier(atk_item, type_mult),
        base_power_mult=base_power_multiplier(
            atk_item, move_type, TERRAIN.get(case.get("terrain")), move_id),
    )


def test_every_reference_case_matches_roll_for_roll(reference, dex):
    mismatches = []
    for case in reference:
        mine = damage_rolls(**_inputs(case, dex))
        theirs = tuple(case["rolls"])
        if mine != theirs:
            mismatches.append(f"{case['name']}: showdown={theirs} mine={mine}")
    assert not mismatches, "\n".join(mismatches)


def test_the_reference_covers_the_paths_that_matter(reference):
    """A fixture that only holds neutral single hits proves almost nothing."""
    names = " ".join(c["name"] for c in reference)
    assert "spread" in names
    assert "rain" in names
    assert "immunity" in names
    assert "resisted" in names
    assert any(c["attacker"].get("item") for c in reference)
    assert any(c["rolls"][0] != c["rolls"][-1] for c in reference), "no case rolls"


def test_rain_moves_golisopod_mega_across_the_ko_line(reference):
    """The case the feature exists for: 4x Fire becomes 2x under rain, and the
    difference is dying versus living."""
    dry = next(c for c in reference if c["name"] == "Fire into Golisopod-Mega, no weather")
    wet = next(c for c in reference if c["name"] == "Fire into Golisopod-Mega, in rain")
    assert dry["rolls"][0] > dry["defender_hp"], "expected a guaranteed OHKO in the dry case"
    assert wet["rolls"][-1] < wet["defender_hp"], "expected a survivable hit in rain"


def test_an_immune_matchup_deals_nothing(reference, dex):
    case = next(c for c in reference if c["name"].startswith("immunity"))
    assert set(case["rolls"]) == {0}
    assert damage_rolls(**_inputs(case, dex)) == (0,) * 16


def test_item_stat_modifiers_match_showdowns_rounding(reference):
    """Independently checks the 4096-step rounding on stat modifiers: whatever
    attack_after_item produces must equal what the simulator's getStat reports."""
    from vgc.damage import attack_after_item

    checked = 0
    for case in reference:
        item = to_id(case["attacker"].get("item") or "") or None
        if item not in ("choiceband", "choicespecs"):
            continue
        if case["attacker"].get("boosts"):
            continue   # isolates item rounding; the combined case is covered above
        stat = "atk" if item == "choiceband" else "spa"
        category = "Physical" if stat == "atk" else "Special"
        raw = case["attacker_stats_raw"][stat]
        assert attack_after_item(raw, item, category) == case["attacker_stats"][stat]
        checked += 1
    assert checked, "no Choice-item case in the fixture to check"


def test_stat_stages_match_the_simulator(reference):
    """The stage table and the clamp, checked against what getStat actually reports."""
    checked = 0
    for case in reference:
        boosts = case["attacker"].get("boosts") or {}
        stage = boosts.get("atk")
        if stage is None or case["attacker"].get("item"):
            continue   # item cases are covered separately; this isolates the boost
        raw = case["attacker_stats_raw"]["atk"]
        assert boosted(raw, stage) == case["attacker_stats"]["atk"], case["name"]
        checked += 1
    assert checked >= 2, "not enough boost-only cases to exercise the table"


def test_the_stage_table_covers_intimidate_and_a_setup_move(reference):
    names = " ".join(c["name"] for c in reference)
    assert "Intimidate" in names and "Swords Dance" in names and "Stamina" in names


@pytest.mark.parametrize("stage,expect", [
    (0, 200), (1, 300), (2, 400), (6, 800), (-1, 133), (-2, 100), (-6, 50),
])
def test_boost_table_endpoints(stage, expect):
    assert boosted(200, stage) == expect


def test_stages_clamp_beyond_six():
    assert boosted(200, 99) == boosted(200, 6)
    assert boosted(200, -99) == boosted(200, -6)


def test_terrain_and_type_items_are_covered(reference):
    names = " ".join(c["name"] for c in reference)
    assert "Grassy Terrain" in names and "Miracle Seed" in names
    assert "together" in names, "no case combines a terrain and a type item"


def test_expanding_force_gets_both_boosts_in_psychic_terrain(reference, dex):
    """Its own 1.5 chains with the generic Psychic Terrain boost, so roughly 1.95x —
    the number that decides psyspam prep."""
    dry = next(c for c in reference if c["name"] == "Expanding Force, no terrain")
    wet = next(c for c in reference if c["name"] == "Expanding Force in Psychic Terrain")
    ratio = wet["rolls"][-1] / dry["rolls"][-1]
    assert 1.85 < ratio < 2.05, f"expected about 1.95x, got {ratio:.3f}"
    # And it must beat a plain Psychic move, which only gets the generic boost.
    plain = next(c for c in reference
                 if c["name"] == "plain Psychic move in Psychic Terrain")
    assert wet["rolls"][-1] > plain["rolls"][-1]
    assert damage_rolls(**_inputs(wet, dex)) == tuple(wet["rolls"])


def test_expanding_force_becomes_a_spread_move_in_terrain():
    from vgc.damage import PSYCHIC_T, spreads_in_terrain
    assert spreads_in_terrain(PSYCHIC_T, "expandingforce")
    assert not spreads_in_terrain(None, "expandingforce")
    assert not spreads_in_terrain("grassy", "expandingforce")
    assert not spreads_in_terrain(PSYCHIC_T, "psychic")


def test_a_plain_psychic_move_gets_only_the_generic_boost(reference, dex):
    plain = next(c for c in reference
                 if c["name"] == "plain Psychic move in Psychic Terrain")
    assert damage_rolls(**_inputs(plain, dex)) == tuple(plain["rolls"])


@pytest.mark.parametrize("dry_name,wet_name,low,high", [
    ("Psyblade, no terrain", "Psyblade in Electric Terrain", 1.40, 1.55),
    ("Rising Voltage, no terrain", "Rising Voltage in Electric Terrain", 2.45, 2.65),
])
def test_electric_terrain_move_clauses(reference, dex, dry_name, wet_name, low, high):
    """Psyblade is Psychic-typed so it gets only its own 1.5; Rising Voltage is
    Electric-typed so it takes the generic boost on top of doubling."""
    dry = next(c for c in reference if c["name"] == dry_name)
    wet = next(c for c in reference if c["name"] == wet_name)
    ratio = wet["rolls"][-1] / dry["rolls"][-1]
    assert low < ratio < high, f"{wet_name}: got {ratio:.3f}"
    assert damage_rolls(**_inputs(wet, dex)) == tuple(wet["rolls"])


def test_every_terrain_clause_is_pinned_by_a_case(reference):
    """A multiplier in TERRAIN_MOVE_EXTRA with no fixture case behind it is exactly
    the unverified guess this harness exists to prevent."""
    from vgc.damage import TERRAIN_MOVE_EXTRA
    covered = {to_id(c["move"]) for c in reference if c.get("terrain")}
    missing = {mid for (_terrain, mid) in TERRAIN_MOVE_EXTRA} - covered
    assert not missing, f"unverified terrain clauses: {sorted(missing)}"
