"""Incoming damage against the real team: the layer between the marts and the formula.

vgc.damage is pinned against Showdown itself in test_damage.py. What this covers is
everything around it — that the right stats, moves, items and assumptions reach it,
and that the two figures it reports mean what the app says they mean.
"""

import pytest

from vgc.damage import RAIN
from vgc.incoming import MAX_SP, SHAKY, incoming, team_bulk
from vgc.megas import resolve_team
from vgc.metafilter import MetaFilter
from vgc.stats import calc_stat, nature_mod, sp_from_investment
from vgc.team import load_team

REG = "M-C"
PASTE = "b58a4fb249fb3cbf"


@pytest.fixture(scope="module")
def ctx():
    try:
        team = load_team(PASTE)
    except FileNotFoundError:
        pytest.skip("paste not loaded")
    formes = resolve_team(team, None)
    try:
        rows = incoming(REG, team, formes, MetaFilter(), 20)
    except LookupError:
        pytest.skip("marts not built")
    if not rows:
        pytest.skip("no meta rows")
    return team, formes, rows


def test_bulk_is_the_pastes_own_numbers(ctx):
    """Your side is exact, not a meta assumption — recompute it independently."""
    team, formes, _rows = ctx
    bulk = team_bulk(team, formes)
    by_slot = {m.slot: m for m in team}
    for f in formes:
        member = by_slot[f.slot]
        sp = sp_from_investment(member.investment)
        got = bulk[f.slot]
        assert got["hp"] == calc_stat(
            _base(f.forme_id, "hp"), sp["hp"], 1.0, stat="hp")
        assert got["spd"] == calc_stat(
            _base(f.forme_id, "spd"), sp["spd"], nature_mod(member.nature, "spd"), stat="spd")
        assert got["item"] == member.item_id


def _base(forme_id, stat):
    from vgc.db import session
    with session() as con:
        return con.execute(
            f'select "{stat}" from dim_pokemon where pokemon_id = ?', [forme_id]).fetchone()[0]


def test_worst_case_never_hits_softer_than_likely(ctx):
    """worst is the legal maximum, so it cannot come out below the modal build."""
    *_, rows = ctx
    for h in rows:
        assert h.worst.low >= h.likely.low, f"{h.threat.display_name} -> {h.target_name}"
        assert h.worst.high >= h.likely.high


def test_a_maxed_out_threat_has_the_two_figures_agree(ctx):
    """When the meta already runs max investment AND a boosting nature, the two
    calculations must coincide — otherwise 'worst' is adding something invented."""
    *_, rows = ctx
    same = [h for h in rows if h.likely.rolls == h.worst.rolls]
    assert same, "no threat runs a maximal offensive build, which is implausible"


def test_confidence_is_reported_and_bounded(ctx):
    *_, rows = ctx
    for h in rows:
        assert 0.0 <= h.investment_share <= 1.0
        assert h.confident == (h.investment_share >= SHAKY)


def test_shaky_assumptions_exist_and_are_flagged(ctx):
    """Guards the flag: per-slot modal investment is genuinely split for some
    species, and the app must be able to say so rather than quoting one number."""
    *_, rows = ctx
    assert any(not h.confident for h in rows), "nothing flagged — is share being read?"


def test_one_row_per_threat_and_target(ctx):
    *_, rows = ctx
    keys = [(h.threat.forme_id, h.target_slot) for h in rows]
    assert len(keys) == len(set(keys))


def test_rows_are_ordered_by_worst_case(ctx):
    *_, rows = ctx
    pcts = [h.worst.low_pct for h in rows]
    assert pcts == sorted(pcts, reverse=True)


def test_ko_flag_uses_the_worst_case(ctx):
    *_, rows = ctx
    for h in rows:
        assert h.kos == (h.worst.low >= h.worst.defender_hp)


def test_rain_only_softens_fire_and_never_hardens_it(ctx):
    """Weather is modelled because it is often the whole story."""
    team, formes, _rows = ctx
    dry = {(h.threat.forme_id, h.target_slot): h for h in incoming(REG, team, formes, MetaFilter(), 20)}
    wet = {(h.threat.forme_id, h.target_slot): h for h in
           incoming(REG, team, formes, MetaFilter(), 20, weather=RAIN)}
    fire = [k for k, h in dry.items() if h.worst.move_type == "Fire" and k in wet]
    if not fire:
        pytest.skip("no Fire move in the current meta sample")
    for key in fire:
        assert wet[key].worst.low < dry[key].worst.low, "rain did not soften a Fire hit"


def test_max_sp_is_the_documented_cap():
    assert MAX_SP == 32


def test_tiers_partition_every_hit(ctx):
    """Grouping must lose nothing — every hit lands in exactly one bracket."""
    from vgc.incoming import TIERS, against, tier
    *_, rows = ctx
    slot = rows[0].target_slot
    buckets = against(rows, slot)
    assert set(buckets) == set(TIERS)
    flat = [h for bucket in buckets.values() for h in bucket]
    assert len(flat) == len([h for h in rows if h.target_slot == slot])
    assert len(flat) == len({(h.threat.forme_id, h.target_slot) for h in flat})
    for name, bucket in buckets.items():
        for h in bucket:
            assert tier(h) == name


def test_tier_matches_the_ko_verdict(ctx):
    """A hit in the OHKO bracket must actually be a guaranteed one-hit KO."""
    from vgc.incoming import OHKO, TWO, against
    *_, rows = ctx
    buckets = against(rows, rows[0].target_slot)
    for h in buckets[OHKO]:
        assert h.worst.low >= h.worst.defender_hp
    for h in buckets[TWO]:
        assert h.worst.low < h.worst.defender_hp
        assert 2 * h.worst.low >= h.worst.defender_hp


def test_each_bucket_is_ordered_hardest_first(ctx):
    from vgc.incoming import against
    *_, rows = ctx
    for bucket in against(rows, rows[0].target_slot).values():
        pcts = [h.worst.low_pct for h in bucket]
        assert pcts == sorted(pcts, reverse=True)
