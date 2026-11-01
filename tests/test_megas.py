"""Mega resolution against the real warehouse."""

import pytest

from helpers import reference_team
from vgc.megas import (STONE_SPECIES, _mega_ability, load_dex, load_stones,
                       mega_forme_id, mega_options, resolve_team)
from vgc.team import Member, load_team
from vgc.typechart import effectiveness



@pytest.fixture(scope="module")
def dex():
    try:
        return load_dex()
    except (FileNotFoundError, LookupError):
        pytest.skip("warehouse not built")


def test_every_unmapped_stone_is_listed(dex):
    unmapped = {k for k, v in load_stones().items() if v is None}
    assert unmapped <= set(STONE_SPECIES)


@pytest.mark.parametrize("holder, stone, expected", [
    ("golisopod", "golisopite", "golisopodmega"),
    ("garchomp", "garchompite", "garchompmega"),
    ("garchomp", "garchompitez", "garchompmegaz"),
    ("meowstic", "meowsticite", "meowsticmmega"),
    ("meowsticf", "meowsticite", "meowsticfmega"),
    ("magearnaoriginal", "magearnite", "magearnaoriginalmega"),
    ("tatsugiri", "tatsugirinite", "tatsugiricurlymega"),
    ("tatsugiridroopy", "tatsugirinite", "tatsugiridroopymega"),
    ("golisopod", "gardevoirite", None),   # wrong species, mapped stone
    ("golisopod", "meowsticite", None),    # wrong species, unmapped stone
    ("golisopod", "focussash", None),
    ("golisopod", None, None),
])
def test_mega_forme_id(dex, holder, stone, expected):
    assert mega_forme_id(holder, stone) == expected


def test_multi_ability_mega_keeps_paste_ability(dex):
    assert _mega_ability(dex["heatranmega"], "flamebody") == "flamebody"
    assert _mega_ability(dex["heatranmega"], "pressure") == "flashfire"


def test_garchomp_z_toggle(dex):
    team = [Member(1, "garchomp", "garchompitez", "roughskin")]
    off, = resolve_team(team, None)
    on, = resolve_team(team, 1)
    assert off.types == ("Dragon", "Ground")
    assert effectiveness("Ground", off.types, off.ability_id) == 1.0
    assert on.forme_id == "garchompmegaz" and on.types == ("Dragon",)
    assert on.ability_id == "levitate"
    assert effectiveness("Ground", on.types, on.ability_id) == 0.0


def test_real_paste(dex):
    """A fixed team of the suite's own: two Mega options, one at a time."""
    team = reference_team()
    assert mega_options(team) == {1: "golisopodmega", 5: "gardevoirmega"}

    base = {f.slot: f for f in resolve_team(team, None)}
    gol = {f.slot: f for f in resolve_team(team, 1)}
    gar = {f.slot: f for f in resolve_team(team, 5)}

    assert base[1].types == ("Bug", "Water") and base[1].ability_id == "emergencyexit"
    assert gol[1].types == ("Bug", "Steel") and gol[1].ability_id == "toughclaws"
    assert gol[5] == base[5]
    assert gar[5].forme_id == "gardevoirmega" and gar[5].ability_id == "pixilate"
    assert gar[1] == base[1]
    assert effectiveness("Fire", gol[1].types, gol[1].ability_id) == 4.0
    assert effectiveness("Fire", base[1].types, base[1].ability_id) == 1.0

    with pytest.raises(ValueError):
        resolve_team(team, 3)  # Sneasler holds Psychic Seed
