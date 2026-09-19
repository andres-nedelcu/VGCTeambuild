"""Visual 6: what to add — meta Pokémon that answer this team's specific problems.

The tool already says Golisopod-Mega is a coverage hole and Electric is a flagged
weakness. The natural next question is "so what fixes that", and HANDOFF §6.7 flagged
the risk in answering it: a recommender that emits a single number feels prescriptive
and hides its reasoning.

So this does not score. It measures three independent things a candidate can do for
you, shows all three, and sorts lexicographically by them:

  1. holes covered   — threats nothing on your team hits super effectively, that this
                       candidate does, using its own commonly-run damaging moves
  2. flags answered  — types where 3+ of your Pokémon are weak and none resist, that
                       this candidate resists or is immune to
  3. synergy         — the lift between this candidate and what you already run

There are no weights to tune and no composite to defend: a candidate that covers two
holes ranks above one that covers one, and synergy only breaks ties. Every column is
the evidence for the row, not a summary of it.

The candidate pool is the meta itself — Pokémon people actually bring — minus what
you already run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from vgc.cores import item_cores, partners
from vgc.defense import defense_matrix, flagged_types, summarize
from vgc.megas import Forme
from vgc.metafilter import MetaFilter
from vgc.offense import Threat, attackers, coverage_matrix, holes, threats
from vgc.pressure import common_moves
from vgc.team import Member
from vgc.typechart import attack_type, effectiveness

SUPER_EFFECTIVE = 1.0
RESISTS = 1.0


@dataclass(frozen=True)
class Suggestion:
    forme_id: str
    species_id: str
    display_name: str
    usage_pct: float
    holes_covered: tuple[str, ...]
    flags_answered: tuple[str, ...]
    partner: str | None      # which of yours it pairs with most strongly
    lift: float              # 0 when the meta shows no association

    @property
    def rank_key(self) -> tuple:
        return (len(self.holes_covered), len(self.flags_answered), self.lift,
                self.usage_pct)


def _move_types(threat: Threat, moves_by_forme) -> tuple[str, ...]:
    """The types this Pokémon actually attacks with, after retyping abilities."""
    moves = moves_by_forme.get(threat.forme_id, [])
    seen = dict.fromkeys(
        attack_type(listed, threat.ability_id) for _id, _n, listed, _s in moves)
    return tuple(seen)


def suggestions(regulation: str, team: Sequence[Member], formes: Sequence[Forme],
                filt: MetaFilter | None = None, top_n: int = 20) -> list[Suggestion]:
    """Candidates ranked by what they fix for this team, best first."""
    filt = filt or MetaFilter()
    meta = threats(regulation, top_n, filt)
    if not meta:
        return []

    gaps = set(holes(coverage_matrix(attackers(team, formes), meta)))
    flags = set(flagged_types(summarize(defense_matrix(formes))))
    by_name = {t.display_name: t for t in meta}
    moves_by_forme = common_moves(regulation, filt)

    mine = {m.pokemon_id for m in team}
    synergy: dict[str, tuple[str, float]] = {}
    for row in partners(regulation, sorted(mine), filt).itertuples():
        # partners() is already sorted by lift, so the first hit per candidate wins.
        synergy.setdefault(row.partner_id, (row.yours, float(row.lift)))

    # Species-level synergy averages a species' builds together, which can cancel a
    # real partnership out entirely — Sneasler's two terrain seeds want opposite
    # partners. The paste says which item this team actually runs, so where that is
    # known the build-specific association is used instead when it is stronger.
    held = [(m.pokemon_id, m.item_id) for m in team if m.item_id]
    if held:
        for row in item_cores(regulation, filt, min_delta=0.0, items=held).itertuples():
            label = f"{row.holder_name} @ {row.item_name or row.item_id}"
            best = synergy.get(row.partner_id)
            if best is None or float(row.lift) > best[1]:
                synergy[row.partner_id] = (label, float(row.lift))

    out = []
    for c in meta:
        if c.species_id in mine or c.forme_id in mine:
            continue
        types = _move_types(c, moves_by_forme)
        covered = tuple(
            h for h in gaps
            if h in by_name
            and max((effectiveness(mt, by_name[h].types, by_name[h].ability_id)
                     for mt in types), default=0.0) > SUPER_EFFECTIVE)
        answered = tuple(
            f for f in sorted(flags)
            if effectiveness(f, c.types, c.ability_id) < RESISTS)
        partner, lift = synergy.get(c.species_id, (None, 0.0))
        if not covered and not answered and lift == 0.0:
            continue   # nothing to say about this one
        out.append(Suggestion(c.forme_id, c.species_id, c.display_name, c.usage_pct,
                              covered, answered, partner, lift))

    return sorted(out, key=lambda s: s.rank_key, reverse=True)
