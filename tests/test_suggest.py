"""What-to-add candidates: the claims each row makes must be independently true.

This is the most prescriptive thing the tool does, so every column is re-derived here
from the underlying type chart rather than trusted. A suggestion that claims to cover
a hole it does not cover is worse than no suggestion at all.
"""

import pytest

from vgc.defense import defense_matrix, flagged_types, summarize
from vgc.megas import resolve_team
from vgc.metafilter import MetaFilter
from vgc.offense import attackers, coverage_matrix, holes, threats
from vgc.suggest import suggestions
from vgc.team import load_team
from vgc.typechart import effectiveness

REG = "M-C"
PASTE = "b58a4fb249fb3cbf"
TOP_N = 20


@pytest.fixture(scope="module")
def ctx():
    try:
        team = load_team(PASTE)
    except FileNotFoundError:
        pytest.skip("paste not loaded")
    formes = resolve_team(team, None)
    try:
        meta = threats(REG, TOP_N)
    except LookupError:
        pytest.skip("marts not built")
    if not meta:
        pytest.skip("no meta rows")
    gaps = set(holes(coverage_matrix(attackers(team, formes), meta)))
    flags = set(flagged_types(summarize(defense_matrix(formes))))
    picks = suggestions(REG, team, formes, MetaFilter(), TOP_N)
    return team, formes, meta, gaps, flags, picks


def test_there_is_something_to_suggest(ctx):
    *_, picks = ctx
    assert picks, "no candidates at all — the pool or the filters are wrong"


def test_nothing_already_on_the_team_is_suggested(ctx):
    team, *_, picks = ctx
    mine = {m.pokemon_id for m in team}
    for s in picks:
        assert s.species_id not in mine and s.forme_id not in mine, s.display_name


def test_claimed_holes_are_real_holes(ctx):
    _team, _formes, _meta, gaps, _flags, picks = ctx
    for s in picks:
        assert set(s.holes_covered) <= gaps, f"{s.display_name} invented a hole"


def test_claimed_flags_are_real_flags(ctx):
    *_, flags, picks = ctx
    for s in picks:
        assert set(s.flags_answered) <= flags, f"{s.display_name} invented a flag"


def test_a_claimed_resist_really_resists(ctx):
    """Re-derive from the type chart: 'Resists' must mean below 1x, ability included."""
    _team, _formes, meta, _gaps, _flags, picks = ctx
    by_forme = {t.forme_id: t for t in meta}
    checked = 0
    for s in picks:
        threat = by_forme.get(s.forme_id)
        if threat is None:
            continue
        for flag in s.flags_answered:
            assert effectiveness(flag, threat.types, threat.ability_id) < 1.0, \
                f"{s.display_name} does not resist {flag}"
            checked += 1
    assert checked, "no resist claims were exercised"


def test_a_claimed_cover_really_hits_super_effectively(ctx):
    """The strongest claim on the tab, re-derived from that candidate's own moves."""
    from vgc.pressure import common_moves
    from vgc.typechart import attack_type

    _team, _formes, meta, _gaps, _flags, picks = ctx
    by_forme = {t.forme_id: t for t in meta}
    by_name = {t.display_name: t for t in meta}
    moves = common_moves(REG)
    checked = 0
    for s in picks:
        attacker = by_forme[s.forme_id]
        types = {attack_type(listed, attacker.ability_id)
                 for _i, _n, listed, _sh in moves.get(s.forme_id, [])}
        for hole in s.holes_covered:
            target = by_name[hole]
            best = max((effectiveness(t, target.types, target.ability_id)
                        for t in types), default=0.0)
            assert best > 1.0, f"{s.display_name} does not cover {hole}"
            checked += 1
    assert checked, "no coverage claims were exercised"


def test_ranking_is_the_stated_lexicographic_order(ctx):
    """Holes, then flags, then synergy — and no hidden composite score."""
    *_, picks = ctx
    keys = [s.rank_key for s in picks]
    assert keys == sorted(keys, reverse=True)


def test_a_candidate_offering_nothing_is_left_out(ctx):
    *_, picks = ctx
    for s in picks:
        assert s.holes_covered or s.flags_answered or s.lift > 0, s.display_name


def test_an_impossible_filter_yields_no_candidates(ctx):
    team, formes, *_ = ctx
    assert suggestions(REG, team, formes, MetaFilter(min_players=10_000), TOP_N) == []


def test_build_specific_synergy_beats_the_species_average(ctx):
    """The paste knows which item each Pokémon holds, and that can rescue a
    partnership the species-level average cancels out.

    The loaded team runs Sneasler @ Psychic Seed, which is a terrain-seed Unburden
    build: the seed is consumed by Psychic Terrain and Sneasler's Speed doubles. That
    build wants Indeedee specifically, but averaged against the Grassy Seed builds —
    which want Rillaboom instead — the association vanishes at species level.
    """
    from vgc.cores import partners

    team, formes, *_, picks = ctx
    if not any(m.pokemon_id == "sneasler" and m.item_id == "psychicseed" for m in team):
        pytest.skip("loaded paste is not the Psychic Seed Sneasler build")

    indeedee = [s for s in picks if s.species_id == "indeedee"]
    if not indeedee:
        pytest.skip("Indeedee is not a candidate at this top_n")

    species_level = partners(REG, [m.pokemon_id for m in team], MetaFilter())
    row = species_level[species_level["partner_id"] == "indeedee"]
    flat = float(row["lift"].iloc[0]) if not row.empty else 0.0

    assert indeedee[0].lift > flat, "item-conditioned synergy is not being applied"
    assert "@" in (indeedee[0].partner or ""), "the build is not named in the label"
