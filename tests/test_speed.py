"""Speed matchup verdicts: outspeed / depends / outsped, Scarf handling and ties."""
from types import SimpleNamespace

import pytest

from vgc.speed import DEPENDS, OUTSPED, OUTSPEED, benchmarks, ceiling, matchup

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
