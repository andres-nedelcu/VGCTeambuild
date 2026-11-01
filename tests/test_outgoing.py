"""Outgoing damage: what your team does to the meta.

The distinction this module exists for is `always_kos` — a KO that lands even against
the bulkiest legal build. It is the only damage claim in the tool that survives not
knowing what the opponent invested, so it has to be exactly right: too loose and it
promises a KO that whiffs, too tight and it is indistinguishable from `likely_kos`.
"""

import pytest

from vgc.megas import resolve_team
from vgc.metafilter import MetaFilter
from vgc.outgoing import ALWAYS, LIKELY, NEVER, outgoing
from vgc.team import list_teams, load_team

REG = "M-C"


@pytest.fixture(scope="module")
def ctx():
    full = [t for t in list_teams() if len(t.members) > 1]
    if not full:
        pytest.skip("no multi-Pokémon team saved")
    team = load_team(full[0].id)
    formes = resolve_team(team, None)
    try:
        rows = outgoing(REG, team, formes, MetaFilter(), 20)
    except LookupError:
        pytest.skip("marts not built")
    if not rows:
        pytest.skip("no meta rows")
    return team, formes, rows


def test_there_is_something_to_report(ctx):
    *_, rows = ctx
    assert rows


def test_a_bulkier_target_never_takes_more(ctx):
    """bulkiest is the maximum legal investment, so it cannot take more damage."""
    *_, rows = ctx
    for h in rows:
        assert h.bulkiest.low <= h.likely.low, f"{h.attacker_name} -> {h.threat.display_name}"
        assert h.bulkiest.defender_hp >= h.likely.defender_hp


def test_always_kos_implies_likely_kos(ctx):
    """Killing through max bulk must also kill the common build. If this ever fails
    the two calculations have diverged."""
    *_, rows = ctx
    for h in rows:
        if h.always_kos:
            assert h.likely_kos, f"{h.attacker_name} -> {h.threat.display_name}"


def test_certainty_is_the_three_stated_states(ctx):
    *_, rows = ctx
    for h in rows:
        assert h.certainty in (ALWAYS, LIKELY, NEVER)
        assert (h.certainty == ALWAYS) == h.always_kos
        assert (h.certainty == NEVER) == (not h.likely_kos)


def test_both_certainty_levels_actually_occur(ctx):
    """Guards the whole feature: if everything is one bucket the distinction is
    invisible and the colour on the grid means nothing."""
    *_, rows = ctx
    seen = {h.certainty for h in rows}
    assert len(seen) >= 2, f"only one certainty level present: {seen}"


def test_hits_to_ko_agrees_with_the_result(ctx):
    """Ceiling division, except where a Focus Sash breaks it on purpose.

    The Sash is the one case where enough damage is not a KO: it triggers at full HP
    and leaves 1, so a hit that outdamages the target still takes two. The exemption
    is narrow and `test_a_sash_turns_a_ohko_into_a_two_hit_ko` pins the behaviour
    rather than leaving this assertion merely relaxed.
    """
    *_, rows = ctx
    for h in rows:
        if h.hits_to_ko is None:
            continue
        assert h.hits_to_ko * h.likely.low >= h.likely.defender_hp
        if h.likely.defender_sash:
            continue
        assert h.hits_to_ko == 1 or (h.hits_to_ko - 1) * h.likely.low < h.likely.defender_hp


def test_a_sash_turns_a_ohko_into_a_two_hit_ko(ctx):
    """Focus Sash is 10.19% of held items, the most of anything in the format, and
    the tool ignored it entirely until now."""
    *_, rows = ctx
    sashed = [h for h in rows if h.likely.defender_sash
              and h.likely.low >= h.likely.defender_hp]
    if not sashed:
        pytest.skip("no threat in this meta slice holds a Focus Sash and dies to one hit")
    for h in sashed:
        assert h.hits_to_ko == 2, "enough damage, but the Sash survives it"


def test_one_row_per_attacker_and_threat(ctx):
    *_, rows = ctx
    keys = [(h.attacker_slot, h.threat.forme_id) for h in rows]
    assert len(keys) == len(set(keys))


def test_rows_are_ordered_by_damage_through_bulk(ctx):
    *_, rows = ctx
    pcts = [h.bulkiest.low_pct for h in rows]
    assert pcts == sorted(pcts, reverse=True)


def test_a_boost_makes_your_hits_harder(ctx):
    team, formes, rows = ctx
    plain = {(h.attacker_slot, h.threat.forme_id): h for h in rows}
    boosted_rows = {(h.attacker_slot, h.threat.forme_id): h for h in
                    outgoing(REG, team, formes, MetaFilter(), 20, atk_stage=2)}
    moved = 0
    for key, hit in plain.items():
        if hit.likely.low == 0:
            continue
        assert boosted_rows[key].likely.low >= hit.likely.low
        moved += boosted_rows[key].likely.low > hit.likely.low
    assert moved, "a +2 attack stage changed nothing"


def test_an_impossible_filter_yields_nothing(ctx):
    team, formes, _rows = ctx
    assert outgoing(REG, team, formes, MetaFilter(min_players=10_000), 20) == []


def test_per_move_keeps_every_move_not_just_the_best(ctx):
    team, formes, rows = ctx
    every = outgoing(REG, team, formes, MetaFilter(), 20, per_move=True)
    assert len(every) > len(rows), "per_move collapsed to one row per matchup"
    keys = {(h.attacker_slot, h.move_id, h.threat.forme_id) for h in every}
    assert len(keys) == len(every), "duplicate (attacker, move, threat) rows"
    # The collapsed view must be a subset of the full one, by damage.
    best = {(h.attacker_slot, h.threat.forme_id): h.bulkiest.low for h in rows}
    for h in every:
        key = (h.attacker_slot, h.threat.forme_id)
        assert h.bulkiest.low <= best[key], "a per-move hit beat the chosen best move"


def test_grassy_terrain_boosts_grass_and_halves_earthquake(ctx):
    from vgc.damage import GRASSY
    team, formes, _rows = ctx
    plain = {(h.attacker_slot, h.move_id, h.threat.forme_id): h
             for h in outgoing(REG, team, formes, MetaFilter(), 20, per_move=True)}
    grassy = {(h.attacker_slot, h.move_id, h.threat.forme_id): h
              for h in outgoing(REG, team, formes, MetaFilter(), 20,
                                terrain=GRASSY, per_move=True)}
    grass_moves = [k for k, h in plain.items() if h.likely.move_type == "Grass"]
    quakes = [k for k in plain if k[1] in ("earthquake", "bulldoze", "magnitude")]
    if not grass_moves and not quakes:
        pytest.skip("team has no Grass move and no Earthquake")
    for key in grass_moves:
        if plain[key].likely.low:
            assert grassy[key].likely.low > plain[key].likely.low
    for key in quakes:
        if plain[key].likely.low:
            assert grassy[key].likely.low < plain[key].likely.low
