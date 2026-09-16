"""Checks the loaded dim_ability_type_modifier and the end-to-end effectiveness path."""

import pytest

from vgc.typechart import clear_cache, effectiveness, load_ability_modifiers


@pytest.fixture(scope="module")
def mods():
    clear_cache()
    try:
        m = load_ability_modifiers()
    except FileNotFoundError:
        pytest.skip("warehouse not built")
    if not m:
        pytest.skip("dim_ability_type_modifier empty; run scripts/load_ability_mods.py")
    return m


def test_seed_rows(mods):
    assert mods[("levitate", "Ground")] == 0.0
    assert mods[("thickfat", "Fire")] == 0.5
    assert mods[("thickfat", "Ice")] == 0.5
    assert set(mods.values()) <= {0.0, 0.5}


def test_end_to_end_real_tables(mods):
    assert effectiveness("Ground", ["Dragon", None], "Levitate") == 0.0     # Garchomp-Mega-Z
    assert effectiveness("Ground", ["Dragon", "Ground"], "Rough Skin") == 1.0  # Garchomp
    assert effectiveness("Ice", ["Ice", "Ground"], "Thick Fat") == 0.5      # Mamoswine
    assert effectiveness("Water", ["Water"], "Water Absorb") == 0.0
