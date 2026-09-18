"""Visual 4: how much type pressure each meta threat puts on your team.

The mirror of vgc.offense: that asks whether you can hit them, this asks how hard
they hit you. Scored as usage x the average best hit a threat gets on your team,
so a threat that is both common and awkward rises to the top.

Type pressure only, as the outline says: no base power, attacking stats, bulk or
items. A 4x hit from a weak move still reads as 4x here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from vgc.db import session
from vgc.megas import Forme
from vgc.offense import Threat, threats
from vgc.typechart import attack_type, effectiveness

STAB = 1.5
SUPER_EFFECTIVE = 1.0


@dataclass(frozen=True)
class Hit:
    """The best a threat's common moves manage against one of your Pokémon."""
    slot: int
    target: str
    move_name: str
    move_type: str
    effectiveness: float
    value: float  # effectiveness x STAB, the scored figure


@dataclass(frozen=True)
class Pressure:
    threat: Threat
    score: float
    super_effective: int
    hits: tuple[Hit, ...]

    @property
    def top_hit(self) -> Hit | None:
        return max(self.hits, key=lambda h: h.value, default=None)


def common_moves(regulation: str) -> dict[str, list[tuple[str, str, str, float]]]:
    """forme_id -> [(move_id, move_name, move_type, share)] for common damaging moves."""
    with session() as con:
        rows = con.execute("""
            select forme_id, move_id, move_name, move_type, move_share
            from mart_meta_common_moves where regulation = ?
            order by forme_id, move_share desc
        """, [regulation]).fetchall()
    out: dict[str, list[tuple[str, str, str, float]]] = {}
    for forme_id, move_id, name, move_type, share in rows:
        out.setdefault(forme_id, []).append((move_id, name, move_type, share))
    return out


def _best_hit(moves, threat: Threat, target: Forme) -> Hit | None:
    best = None
    for _move_id, name, listed_type, _share in moves:
        # Aerilate and friends retype the move before it lands, and it gains STAB.
        move_type = attack_type(listed_type, threat.ability_id)
        eff = effectiveness(move_type, target.types, target.ability_id)
        stab = STAB if move_type in threat.types else 1.0
        hit = Hit(target.slot, target.display_name, name, move_type, eff, eff * stab)
        if best is None or hit.value > best.value:
            best = hit
    return best


def rank(regulation: str, team: Sequence[Forme], top_n: int = 20) -> list[Pressure]:
    """Meta threats scored by the pressure they put on this team, worst first."""
    moves_by_forme = common_moves(regulation)
    out = []
    for threat in threats(regulation, top_n):
        moves = moves_by_forme.get(threat.forme_id, [])
        hits = tuple(h for h in (_best_hit(moves, threat, t) for t in team) if h)
        mean_hit = sum(h.value for h in hits) / len(hits) if hits else 0.0
        out.append(Pressure(
            threat=threat,
            score=100 * threat.usage_pct * mean_hit,
            super_effective=sum(1 for h in hits if h.effectiveness > SUPER_EFFECTIVE),
            hits=hits,
        ))
    return sorted(out, key=lambda p: p.score, reverse=True)
