"""Visual 2 logic: offensive coverage against the meta."""

import pytest

from helpers import full_team_id
from vgc.megas import resolve_team
from vgc.offense import (Attacker, Threat, attackers, coverage_matrix, holes,
                         team_best, threats)
from vgc.team import load_team

PASTE = full_team_id()

# Synthetic threats keep the logic tests independent of whatever the meta looks like.
BUG_STEEL = Threat("golisopodmega", "Bug/Steel", ("Bug", "Steel"), None, 0.2)
LEVITATOR = Threat("rotomheat", "Levitator", ("Electric", "Fire"), "levitate", 0.1)
PLAIN = Threat("furret", "Normal", ("Normal",), None, 0.05)

FIRE = Attacker(1, "Fire mon", ("Fire",))
GROUND = Attacker(2, "Ground mon", ("Ground",))
NO_MOVES = Attacker(3, "Support mon", ())


@pytest.fixture(scope="module")
def team():
    try:
        return load_team(PASTE)
    except (FileNotFoundError, LookupError):
        pytest.skip("warehouse not built")


def test_best_of_several_move_types_is_used():
    both = Attacker(1, "Mixed", ("Fire", "Water"))
    matrix = coverage_matrix([both], [BUG_STEEL])
    assert matrix.iloc[0, 0] == 4.0  # Fire is 4x into Bug/Steel; Water would be 0.5x


def test_ability_immunity_is_applied():
    """A Ground move does nothing to Levitate, however good the type chart looks."""
    matrix = coverage_matrix([GROUND], [LEVITATOR])
    assert matrix.iloc[0, 0] == 0.0


def test_pokemon_with_no_damaging_moves_covers_nothing():
    matrix = coverage_matrix([NO_MOVES], [PLAIN])
    assert matrix.iloc[0, 0] == 0.0


def test_team_best_and_holes_agree():
    matrix = coverage_matrix([FIRE, GROUND], [BUG_STEEL, LEVITATOR, PLAIN])
    best = team_best(matrix)
    assert best["Bug/Steel"] == 4.0          # Fire mon answers it
    assert best["Normal"] == 1.0             # neither is super effective
    assert holes(matrix) == [t for t in matrix.columns if best[t] <= 1.0]
    assert "Normal" in holes(matrix)
    assert "Bug/Steel" not in holes(matrix)


def test_matrix_shape_against_the_real_team(team):
    meta = threats("M-C", 12)
    if not meta:
        pytest.skip("marts not built")
    matrix = coverage_matrix(attackers(team, resolve_team(team, None)), meta)
    assert matrix.shape == (len(team), len(meta))
    assert set(matrix.values.flatten()) <= {0, 0.25, 0.5, 1, 2, 4}


def test_mega_formes_use_their_own_ability(team):
    meta = {t.forme_id: t for t in threats("M-C", 40)}
    if "salamencemega" not in meta:
        pytest.skip("Salamence-Mega not in the current meta sample")
    assert meta["salamencemega"].ability_id == "aerilate"
