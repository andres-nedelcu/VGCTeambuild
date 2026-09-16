"""Type chart tests (outline section 10). Uses the real dim_type_chart;
ability rows are injected so these don't depend on the seed file."""

import pytest

from vgc.typechart import TYPES, effectiveness, load_type_chart, normalize_type

MODS = {
    ("levitate", "Ground"): 0.0,
    ("thickfat", "Fire"): 0.5,
    ("thickfat", "Ice"): 0.5,
}


@pytest.fixture(scope="module")
def chart():
    try:
        return load_type_chart()
    except FileNotFoundError:
        pytest.skip("warehouse not built")


def test_chart_is_complete(chart):
    assert len(chart) == 18 * 18
    assert set(v for v in chart.values()) <= {0.0, 0.5, 1.0, 2.0}


@pytest.mark.parametrize(
    "atk, defs, expected",
    [
        ("Ground", ["Flying"], 0.0),
        ("Fire", ["Water", "Ground"], 0.5),
        ("Ice", ["Dragon", "Flying"], 4.0),
        ("Ground", ["Dragon", "Ground"], 1.0),   # Garchomp, no Mega
        ("Fire", ["Bug", "Water"], 1.0),         # Golisopod
        ("Fire", ["Bug", "Steel"], 4.0),         # Golisopod-Mega
        ("Electric", ["Bug", "Water"], 2.0),
        ("Electric", ["Bug", "Steel"], 1.0),
    ],
)
def test_type_matchups(chart, atk, defs, expected):
    assert effectiveness(atk, defs, chart=chart, ability_mods={}) == expected


def test_levitate_zeroes_ground(chart):
    # Garchomp-Mega-Z: mono Dragon + Levitate
    assert effectiveness("Ground", ["Dragon", None], "Levitate", chart=chart, ability_mods=MODS) == 0.0
    assert effectiveness("Ground", ["Steel"], "levitate", chart=chart, ability_mods=MODS) == 0.0


@pytest.mark.parametrize("atk", ["Fire", "Ice"])
def test_thick_fat_halves(chart, atk):
    assert effectiveness(atk, ["Normal"], "Thick Fat", chart=chart, ability_mods=MODS) == 0.5


def test_thick_fat_stacks_with_chart(chart):
    assert effectiveness("Fire", ["Grass"], "Thick Fat", chart=chart, ability_mods=MODS) == 1.0


def test_unrelated_ability_is_neutral(chart):
    assert effectiveness("Ground", ["Dragon", "Ground"], "Rough Skin", chart=chart, ability_mods=MODS) == 1.0


def test_input_normalization(chart):
    assert effectiveness("ground", ["FLYING", ""], chart=chart, ability_mods={}) == 0.0
    assert effectiveness("Fire", ["Fire", "Fire"], chart=chart, ability_mods={}) == 0.5  # dedup


def test_unknown_type_raises(chart):
    with pytest.raises(ValueError):
        effectiveness("Stellar", ["Normal"], chart=chart, ability_mods={})
    with pytest.raises(ValueError):
        effectiveness("Fire", [None], chart=chart, ability_mods={})


def test_types_constant():
    assert len(TYPES) == 18
    assert normalize_type(" dRaGoN ") == "Dragon"
