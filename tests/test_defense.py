"""Visual 1 logic against the real paste."""

import pytest

from vgc.defense import RESIST_ROW, WEAK_ROW, defense_matrix, flagged_types, summarize
from vgc.megas import resolve_team
from vgc.team import load_team
from vgc.typechart import TYPES

PASTE = "b58a4fb249fb3cbf"


@pytest.fixture(scope="module")
def team():
    try:
        return load_team(PASTE)
    except FileNotFoundError:
        pytest.skip("warehouse not built")


def grid(team, mega_slot):
    m = defense_matrix(resolve_team(team, mega_slot))
    return m, summarize(m)


def test_shape(team):
    m, s = grid(team, None)
    assert m.shape == (6, 18) and list(m.columns) == list(TYPES)
    assert list(s.index) == [WEAK_ROW, RESIST_ROW]
    assert set(m.values.flatten()) <= {0, 0.25, 0.5, 1, 2, 4}


def test_base_team(team):
    m, s = grid(team, None)
    assert flagged_types(s) == ["Electric"]
    assert s.loc[WEAK_ROW, "Electric"] == 3 and s.loc[RESIST_ROW, "Electric"] == 0
    assert m.loc["4. Pelipper", "Electric"] == 4
    assert m.loc["4. Pelipper", "Ground"] == 0


def test_golisopod_mega(team):
    m, s = grid(team, 1)
    assert m.loc["1. Golisopod-Mega", "Fire"] == 4
    assert m.loc["1. Golisopod-Mega", "Electric"] == 1
    assert s.loc[WEAK_ROW, "Electric"] == 2
    assert flagged_types(s) == []


def test_gardevoir_mega_matches_base_values(team):
    base, _ = grid(team, None)
    gar, _ = grid(team, 5)
    assert (base.values == gar.values).all()
    assert "5. Gardevoir-Mega" in gar.index


def test_subset_selection(team):
    formes = [f for f in resolve_team(team, None) if f.slot in (1, 4)]
    _, s = grid_from(formes)
    assert s.loc[WEAK_ROW, "Electric"] == 2
    assert flagged_types(s) == []


def grid_from(formes):
    m = defense_matrix(formes)
    return m, summarize(m)
