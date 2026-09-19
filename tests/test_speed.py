"""Speed matchup verdicts: outspeed / depends / outsped, Scarf handling and ties."""
from types import SimpleNamespace

import pytest

from vgc.megas import resolve_team
from vgc.speed import (DEPENDS, MOVE_FIRST, MOVE_LAST, OUTSPED, OUTSPEED, Field, benchmarks,
                        ceiling, matchup, team_speeds)
from vgc.stats import CHOICE_SCARF, calc_stat, nature_mod, scarf
from vgc.team import load_team

# base 120 threat: max+ 189, max neutral 172, uninvested 140, uninvested -Spe 126
THREAT = dict(spe_max_plus=189, spe_max_neutral=172, spe_uninvested=140,
              spe_uninvested_neg=126, spe_max_plus_scarf=283, spe_max_neutral_scarf=258)


def row(scarf_flag=False, **overrides):
    return SimpleNamespace(**{**THREAT, **overrides, "scarf_flag": scarf_flag})


def test_ceiling_ignores_scarf_unless_flagged():
    assert ceiling(row()) == 189
    assert ceiling(row(scarf_flag=True)) == 283


def test_benchmarks_include_scarf_only_when_flagged():
    assert 283 not in benchmarks(row())
    assert 283 in benchmarks(row(scarf_flag=True))


@pytest.mark.parametrize("speed,expected", [
    (190, OUTSPEED),   # faster than a max +Spe spread
    (188, DEPENDS),    # beats most spreads, not the fastest
    (141, DEPENDS),
    (125, OUTSPED),    # slower than even an uninvested -Spe spread
])
def test_matchup_without_scarf(speed, expected):
    assert matchup(speed, row()) == expected


def test_scarf_flag_moves_the_ceiling():
    """A speed that beats the unscarfed max is only 'Depends' once Scarf is common."""
    assert matchup(200, row()) == OUTSPEED
    assert matchup(200, row(scarf_flag=True)) == DEPENDS
    assert matchup(284, row(scarf_flag=True)) == OUTSPEED


@pytest.mark.parametrize("speed", [189, 172, 140, 126])
def test_exact_benchmark_is_flagged_as_a_tie(speed):
    assert matchup(speed, row()).endswith("· tie")


def test_scarf_benchmarks_only_tie_when_flagged():
    assert matchup(283, row()) == OUTSPEED
    assert matchup(283, row(scarf_flag=True)) == f"{DEPENDS} · tie"


# ---- Field effects: Tailwind and Trick Room ----------------------------------------

@pytest.mark.parametrize("speed,expected", [
    (190, OUTSPEED), (188, DEPENDS), (141, DEPENDS), (125, OUTSPED),
])
def test_field_off_matches_today(speed, expected):
    """Explicit no-op Field must be identical to the pre-field behaviour."""
    assert matchup(speed, row(), Field()) == expected
    assert matchup(speed, row(), Field()) == matchup(speed, row())


def test_your_tailwind_doubles_only_your_speed():
    field = Field(tailwind="yours")
    # 95 loses outright normally (< 126 floor); doubled to 190 it beats the 189 ceiling.
    assert matchup(95, row()) == OUTSPED
    assert matchup(95, row(), field) == OUTSPEED
    # The threat's own benchmarks are untouched: 189 ceiling stays 189, not 378.
    assert ceiling(row(), field) == 189


def test_their_tailwind_doubles_only_threat_benchmarks():
    field = Field(tailwind="theirs")
    assert ceiling(row(), field) == 189 * 2
    assert benchmarks(row(), field) == tuple(v * 2 for v in benchmarks(row()))
    # My speed is untouched: 300 beat the neutral 189 ceiling but not the doubled 378.
    assert matchup(300, row()) == OUTSPEED
    assert matchup(300, row(), field) == DEPENDS
    # A benchmark tie still fires once it's compared against the doubled value — hitting
    # the ceiling exactly is "Depends · tie", same convention as the unscaled case.
    assert matchup(189 * 2, row(), field) == f"{DEPENDS} · tie"


@pytest.mark.parametrize("speed,expected", [
    (190, OUTSPEED), (188, DEPENDS), (141, DEPENDS), (125, OUTSPED),
])
def test_both_tailwind_restores_neutral_verdicts(speed, expected):
    """Doubling both sides by the same factor cannot change any comparison's outcome."""
    assert matchup(speed, row(), Field(tailwind="both")) == expected
    assert matchup(speed, row(scarf_flag=True), Field(tailwind="both")) == \
        matchup(speed, row(scarf_flag=True))


@pytest.mark.parametrize("speed,expected", [
    (125, MOVE_FIRST),   # slower than their slowest realistic spread: guaranteed first
    (190, MOVE_LAST),    # faster than their fastest realistic spread: guaranteed last
    (141, DEPENDS),
])
def test_trick_room_inverts_verdict_and_wording(speed, expected):
    assert matchup(speed, row(), Field(trick_room=True)) == expected


def test_trick_room_ties_still_flagged():
    for speed in (189, 172, 140, 126):
        assert matchup(speed, row(), Field(trick_room=True)).endswith("· tie")


def test_tailwind_and_trick_room_combine():
    """Your Tailwind boost feeds into the Trick Room comparison, not around it."""
    field = Field(tailwind="yours", trick_room=True)
    # 30 doubles to 60, still well under the 126 floor: guaranteed to move first.
    assert matchup(30, row(), field) == MOVE_FIRST
    # 63 doubles to exactly 126, the floor benchmark itself: a Depends tie.
    assert matchup(63, row(), field) == f"{DEPENDS} · tie"


def test_scarf_then_tailwind_order_pinned_on_odd_speed():
    """Scarf floors first, Tailwind doubles the floored value — not the reverse.

    base Speed 151, +Spe max stat 223 (odd). champ_scarf(223) = 223*3//2 = 334 (the
    mart's own value). Correct order: 2 * 334 = 668. The wrong order — double first,
    then floor — gives champ_scarf(446) = 669, one Speed point higher. That single
    point is exactly the kind of silent drift this test exists to catch.
    """
    threat = row(scarf_flag=True, spe_max_plus=223, spe_max_plus_scarf=334)
    assert ceiling(threat, Field(tailwind="theirs")) == 668
    assert ceiling(threat, Field(tailwind="theirs")) != 2 * 223 * 3 // 2


# ---- Your own item: known, so applied outright --------------------------------------
#
# A threat's Choice Scarf only moves a marker, because it is inferred from how often
# the species is seen holding one. Yours is read from the paste, so it is applied.

PASTE = "b58a4fb249fb3cbf"


@pytest.fixture(scope="module")
def loaded_team():
    try:
        return load_team(PASTE)
    except FileNotFoundError:
        pytest.skip("warehouse not built")


@pytest.mark.parametrize("raw,expected", [(143, 214), (100, 150), (101, 151)])
def test_scarf_multiplies_by_one_and_a_half_and_floors(raw, expected):
    assert scarf(raw) == expected


def test_your_speed_is_the_formula_times_the_item(loaded_team):
    """Every slot: the stat formula, Scarfed only where the paste actually holds one."""
    by_slot = {m.slot: m for m in loaded_team}
    speeds = team_speeds(loaded_team, resolve_team(loaded_team, None))
    assert speeds
    for s in speeds:
        held_scarf = by_slot[s.slot].item_id == CHOICE_SCARF
        assert s.scarfed == held_scarf
        raw = calc_stat(s.base_spe, s.sp, nature_mod(s.nature, "spe"))
        assert s.speed == (scarf(raw) if held_scarf else raw)


def test_the_scarf_case_is_actually_exercised(loaded_team):
    """Guards the test above, which would pass vacuously on a team with no Scarf."""
    speeds = team_speeds(loaded_team, resolve_team(loaded_team, None))
    holders = [s for s in speeds if s.scarfed]
    if not holders:
        pytest.skip(f"paste {PASTE} has no Choice Scarf user to exercise")
    for s in holders:
        raw = calc_stat(s.base_spe, s.sp, nature_mod(s.nature, "spe"))
        assert s.speed > raw, "a Scarf holder must come out faster than its bare stat"
