"""In-app spread editing: overrides held in memory, never written to the warehouse.

The app is read-only by design and stays that way — `DECISIONS.md` has the reason
(DuckDB allows one writer and VFC xV reads the same file). Nothing here touches it.
An edit produces a modified copy of the Member list, which is all the visuals need:
every one of them already takes `team` and `formes` as arguments rather than reading
`my_team` itself.

Why it exists: a team locked in the game arrives without spreads, and the decisions
that actually matter — what survives what — *are* the spread decisions. Until they
are set, every damage figure in the tool is computed at 0 SP with a neutral nature,
which is not the team being played.

Edits live for the session. `to_paste` exists so a spread worth keeping can be copied
out to a note or to pokepast.es rather than lost to a browser refresh.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from vgc.db import session
from vgc.stats import (NATURES, NEUTRAL, SP_MAX_PER_STAT, SP_MAX_TOTAL, STATS,
                       sp_from_investment)
from vgc.team import Member

ALL_NATURES = tuple(sorted(set(NATURES) | NEUTRAL))
LABELS = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}


@dataclass(frozen=True)
class Spread:
    nature: str | None
    sp: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.sp.values())

    @property
    def remaining(self) -> int:
        return SP_MAX_TOTAL - self.total


def read_spread(member: Member) -> Spread:
    """The spread a paste arrived with. Missing investment reads as all zeroes."""
    try:
        sp = sp_from_investment(member.investment)
    except ValueError:
        sp = dict.fromkeys(STATS, 0)
    return Spread(member.nature, dict(sp))


def problem(spread: Spread) -> str | None:
    """Why this spread is illegal, or None. Checked before it reaches calc_stat,
    so the editor can refuse a value rather than raise halfway through a render."""
    for stat, value in spread.sp.items():
        if value < 0 or value > SP_MAX_PER_STAT:
            return f"{LABELS[stat]} must be between 0 and {SP_MAX_PER_STAT}"
    if spread.total > SP_MAX_TOTAL:
        return f"{spread.total} SP spent, {SP_MAX_TOTAL} allowed"
    if spread.nature is not None and spread.nature.lower() not in (
            set(NATURES) | NEUTRAL):
        return f"unknown nature {spread.nature!r}"
    return None


def apply(team: Sequence[Member], edits: dict[int, Spread]) -> list[Member]:
    """A copy of the team with the edited spreads substituted in."""
    out = []
    for member in team:
        spread = edits.get(member.slot)
        if spread is None or problem(spread):
            out.append(member)
            continue
        out.append(replace(
            member, nature=spread.nature,
            investment={"unit": "sp", "values": dict(spread.sp)}))
    return out


def to_paste(team: Sequence[Member]) -> str:
    """Showdown export text, so an edited spread can leave the session.

    Investment is written as `EVs:` because that is what the format uses and what
    scripts/load_paste.py reads back — as SP, within the Champions caps.
    """
    with session() as con:
        names = dict(con.execute(
            "select pokemon_id, display_name from dim_pokemon").fetchall())
        items = dict(con.execute(
            "select item_id, display_name from dim_item").fetchall())
        moves = dict(con.execute(
            "select move_id, display_name from dim_move").fetchall())

    blocks = []
    for m in sorted(team, key=lambda x: x.slot):
        head = names.get(m.pokemon_id, m.pokemon_id)
        if m.item_id:
            head += f" @ {items.get(m.item_id, m.item_id)}"
        lines = [head]
        if m.ability_id:
            lines.append(f"Ability: {m.ability_id}")
        lines.append("Level: 50")
        sp = read_spread(m).sp
        spent = [f"{v} {LABELS[s]}" for s, v in sp.items() if v]
        if spent:
            lines.append("EVs: " + " / ".join(spent))
        if m.nature:
            lines.append(f"{m.nature.title()} Nature")
        for move in (m.moves or []):
            lines.append(f"- {moves.get(move, move)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"
