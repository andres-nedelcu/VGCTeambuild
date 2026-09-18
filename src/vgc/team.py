"""Read-only access to my_team. Writes go through scripts/load_paste.py."""

from __future__ import annotations

from dataclasses import dataclass

from vgc.db import session


@dataclass(frozen=True)
class Member:
    slot: int
    pokemon_id: str
    item_id: str | None
    ability_id: str | None
    nickname: str | None = None
    nature: str | None = None
    investment: str | None = None


def list_pastes() -> list[tuple[str, str | None, list[str]]]:
    """(paste_id, team_name, [pokemon_id by slot]) for every loaded paste."""
    with session() as con:
        return con.execute("""
            select paste_id, any_value(team_name), list(pokemon_id order by slot)
            from my_team group by paste_id order by paste_id
        """).fetchall()


def load_team(paste_id: str) -> list[Member]:
    with session() as con:
        rows = con.execute("""
            select slot, pokemon_id, item_id, ability_id, nickname, nature, investment
            from my_team where paste_id = ? order by slot
        """, [paste_id]).fetchall()
    if not rows:
        raise LookupError(f"No paste {paste_id!r} in my_team. Run scripts/load_paste.py first.")
    return [Member(*r) for r in rows]
