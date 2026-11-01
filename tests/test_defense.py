"""Visual 1 logic against the real paste."""

import pytest

from helpers import full_team_id
from vgc.defense import RESIST_ROW, WEAK_ROW, defense_matrix, flagged_types, summarize
from vgc.megas import resolve_team
from vgc.team import load_team
from vgc.typechart import TYPES

PASTE = full_team_id()


@pytest.fixture(scope="module")
def team():
    try:
        return load_team(PASTE)
    except (FileNotFoundError, LookupError):
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
    assert m.loc["Pelipper", "Electric"] == 4
    assert m.loc["Pelipper", "Ground"] == 0


def test_golisopod_mega(team):
    m, s = grid(team, 1)
    assert m.loc["Golisopod-Mega", "Fire"] == 4
    assert m.loc["Golisopod-Mega", "Electric"] == 1
    assert s.loc[WEAK_ROW, "Electric"] == 2
    assert flagged_types(s) == []


def test_gardevoir_mega_matches_base_values(team):
    base, _ = grid(team, None)
    gar, _ = grid(team, 5)
    assert (base.values == gar.values).all()
    assert "Gardevoir-Mega" in gar.index


def test_subset_selection(team):
    formes = [f for f in resolve_team(team, None) if f.slot in (1, 4)]
    _, s = grid_from(formes)
    assert s.loc[WEAK_ROW, "Electric"] == 2
    assert flagged_types(s) == []


def grid_from(formes):
    m = defense_matrix(formes)
    return m, summarize(m)


def test_mega_comparison(team):
    from vgc.defense import mega_comparison

    df = mega_comparison(team, [1, 2, 3, 4, 5, 6]).set_index("Option")
    assert list(df.index) == ["No Mega", "Golisopod-Mega", "Gardevoir-Mega"]
    assert df.loc["No Mega", "Flagged"] == "Electric"
    assert df.loc["Golisopod-Mega", "Flagged"] == "—"
    assert df.loc["Golisopod-Mega", "Δ Weak"] == -2
    assert df.loc["Golisopod-Mega", "Δ Resist/Immune"] == 4
    assert df.loc["Gardevoir-Mega", ["Δ Weak", "Δ Resist/Immune"]].tolist() == [0, 0]

    # deselected holder drops out
    assert list(mega_comparison(team, [2, 3, 4, 5, 6])["Option"]) == ["No Mega", "Gardevoir-Mega"]
