"""Visual 4 logic: type pressure the meta puts on your team."""

import pytest

from helpers import full_team_id
from vgc.megas import Forme
from vgc.offense import Threat
from vgc.pressure import STAB, _best_hit, rank
from vgc.team import load_team
from vgc.typechart import MOVE_TYPE_ABILITIES, attack_type

PASTE = full_team_id()

# (move_id, display name, listed type, share) as mart_meta_common_moves returns them
HYPER_VOICE = ("hypervoice", "Hyper Voice", "Normal", 0.92)
DRACO = ("dracometeor", "Draco Meteor", "Dragon", 0.54)

SALAMENCE_MEGA = Threat("salamencemega", "Salamence-Mega", ("Dragon", "Flying"), "aerilate", 0.38)
PLAIN_DRAGON = Threat("dragonite", "Dragonite", ("Dragon", "Flying"), "innerfocus", 0.10)

GOLISOPOD = Forme(1, "golisopod", "golisopod", "Golisopod", ("Bug", "Water"), "emergencyexit", False)
LEVITATOR = Forme(2, "rotomheat", "rotomheat", "Rotom-Heat", ("Electric", "Fire"), "levitate", False)


def test_attack_type_retypes_normal_moves_only():
    assert attack_type("Normal", "aerilate") == "Flying"
    assert attack_type("Dragon", "aerilate") == "Dragon"   # only Normal converts
    assert attack_type("Normal", "intimidate") == "Normal"  # unrelated ability
    assert attack_type("Normal", None) == "Normal"


@pytest.mark.parametrize("ability,expected", sorted(MOVE_TYPE_ABILITIES.items()))
def test_every_retyping_ability_is_wired_up(ability, expected):
    assert attack_type("Normal", ability) == expected


def test_aerilate_hyper_voice_hits_as_flying_with_stab():
    """Regression: scored as Normal (1x) before, which understated Salamence-Mega badly."""
    hit = _best_hit([HYPER_VOICE], SALAMENCE_MEGA, GOLISOPOD)
    assert hit.move_type == "Flying"
    assert hit.effectiveness == 2.0            # Flying is 2x into Bug/Water
    assert hit.stab is True                    # Salamence-Mega is part Flying
    assert hit.value == 2.0 * STAB             # scoring only; never shown as "3x"


def test_same_move_without_the_ability_stays_normal():
    hit = _best_hit([HYPER_VOICE], PLAIN_DRAGON, GOLISOPOD)
    assert hit.move_type == "Normal"
    assert hit.stab is False
    assert hit.effectiveness == 1.0 and hit.value == 1.0  # no retype, no STAB


def test_best_move_wins_and_defender_ability_applies():
    """Ground-immunity style abilities on your side still count for the defender."""
    ground = ("earthquake", "Earthquake", "Ground", 0.5)
    assert _best_hit([ground], PLAIN_DRAGON, LEVITATOR).value == 0.0
    best = _best_hit([HYPER_VOICE, DRACO], SALAMENCE_MEGA, GOLISOPOD)
    assert best.move_name == "Hyper Voice"  # 3.0x beats Draco Meteor's 1.5x


def test_ranking_is_sorted_and_scored_against_the_real_team():
    try:
        team = load_team(PASTE)
    except (FileNotFoundError, LookupError):
        pytest.skip("warehouse not built")
    from vgc.megas import resolve_team
    rows = rank("M-C", resolve_team(team, None), 10)
    if not rows:
        pytest.skip("marts not built")
    assert [p.score for p in rows] == sorted((p.score for p in rows), reverse=True)
    assert all(0 <= p.super_effective <= len(team) for p in rows)
