"""Spread editing: overrides applied in memory, never to the warehouse.

The editor's job is to make the rest of the tool true for the team actually being
played. If an edit silently fails to apply, every damage and Speed figure quietly
reverts to a 0 SP neutral build and nothing on screen says so.
"""

import pytest

from vgc.edit import ALL_NATURES, Spread, apply, problem, read_spread, to_paste
from vgc.stats import SP_MAX_PER_STAT, SP_MAX_TOTAL, STATS, sp_from_investment
from vgc.team import Member, load_team

PASTE = "b58a4fb249fb3cbf"


@pytest.fixture(scope="module")
def team():
    try:
        return load_team(PASTE)
    except (FileNotFoundError, LookupError):
        pytest.skip("paste not loaded")


def test_every_champions_nature_is_offered():
    assert len(ALL_NATURES) == 25
    assert "adamant" in ALL_NATURES and "serious" in ALL_NATURES


def test_reading_a_spread_round_trips(team):
    for member in team:
        spread = read_spread(member)
        assert set(spread.sp) == set(STATS)
        assert spread.total == sum(spread.sp.values())
        assert spread.remaining == SP_MAX_TOTAL - spread.total


def test_a_pasteless_member_reads_as_all_zeroes():
    """A team locked in the game arrives with no investment at all."""
    bare = Member(1, "rillaboom", None, None, investment=None, nature=None)
    spread = read_spread(bare)
    assert spread.sp == dict.fromkeys(STATS, 0)
    assert spread.remaining == SP_MAX_TOTAL


@pytest.mark.parametrize("sp,expect", [
    ({"hp": 32, "atk": 32, "def": 2, "spa": 0, "spd": 0, "spe": 0}, None),
    ({"hp": 33, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}, "between 0"),
    ({"hp": 32, "atk": 32, "def": 32, "spa": 0, "spd": 0, "spe": 0}, "allowed"),
    ({"hp": -1, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}, "between 0"),
])
def test_illegal_spreads_are_refused(sp, expect):
    got = problem(Spread("adamant", sp))
    assert (got is None) if expect is None else (expect in got)


def test_an_unknown_nature_is_refused():
    assert "nature" in problem(Spread("wobbly", dict.fromkeys(STATS, 0)))


def test_applying_an_edit_changes_the_member(team):
    want = Spread("jolly", {"hp": 4, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 30})
    out = apply(team, {team[0].slot: want})
    assert out[0].nature == "jolly"
    assert sp_from_investment(out[0].investment)["spe"] == 30
    assert out[1:] == team[1:], "untouched slots must be identical objects"


def test_an_illegal_edit_is_ignored_rather_than_applied(team):
    """Refusing loudly in the UI is the plan; silently writing a broken spread that
    raises deep inside calc_stat during a render is not."""
    bad = Spread("adamant", {s: SP_MAX_PER_STAT for s in STATS})
    assert apply(team, {team[0].slot: bad}) == list(team)


def test_the_original_team_is_never_mutated(team):
    before = [(m.nature, m.investment) for m in team]
    apply(team, {m.slot: Spread("timid", dict.fromkeys(STATS, 5)) for m in team})
    assert [(m.nature, m.investment) for m in team] == before


def test_export_is_loadable_showdown_format(team):
    edited = apply(team, {team[0].slot: Spread(
        "jolly", {"hp": 4, "atk": 32, "def": 0, "spa": 0, "spd": 0, "spe": 30})})
    text = to_paste(edited)
    assert "Level: 50" in text
    assert "Jolly Nature" in text
    assert "EVs: 4 HP / 32 Atk / 30 Spe" in text
    assert text.count("\n\n") == len(team) - 1, "one blank line between members"


def test_export_omits_an_empty_spread():
    bare = [Member(1, "rillaboom", "miracleseed", "grassysurge",
                   investment=None, nature=None, moves=["fakeout"])]
    text = to_paste(bare)
    assert "EVs:" not in text and "Nature" not in text
    assert "Rillaboom @ Miracle Seed" in text
