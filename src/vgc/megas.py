"""Mega forme resolution: (holder, stone, toggle) -> forme, types, ability.

pokemon_id stays the species as listed; the Mega forme comes from the held
stone (dim_item.mega_forme_id). Stones with no mapping are resolved from the
holder's forme. Only one Mega per team is active at a time.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Sequence

from vgc.db import session
from vgc.ids import to_id
from vgc.team import Member

# Stones with no mega_forme_id (multi-forme species): stone -> base species.
STONE_SPECIES = {
    "meowsticite": "meowstic",
    "magearnite": "magearna",
    "tatsugirinite": "tatsugiri",
}


@dataclass(frozen=True)
class Species:
    pokemon_id: str
    display_name: str
    base_species_id: str
    is_mega: bool
    types: tuple[str, ...]
    abilities: tuple[str, ...]  # ability ids


@dataclass(frozen=True)
class Forme:
    slot: int
    pokemon_id: str       # species as listed in the paste
    forme_id: str         # dim_pokemon row used for types
    display_name: str
    types: tuple[str, ...]
    ability_id: str | None
    is_mega: bool


Dex = Mapping[str, Species]
Stones = Mapping[str, "str | None"]


@lru_cache(maxsize=1)
def load_dex() -> dict[str, Species]:
    with session() as con:
        rows = con.execute("""
            select pokemon_id, display_name, base_species_id, is_mega, type1, type2, abilities
            from dim_pokemon
        """).fetchall()
    return {
        pid: Species(pid, name, base, bool(mega),
                     tuple(t for t in (t1, t2) if t),
                     tuple(to_id(a) for a in (abil or [])))
        for pid, name, base, mega, t1, t2, abil in rows
    }


@lru_cache(maxsize=1)
def load_stones() -> dict[str, str | None]:
    with session() as con:
        return dict(con.execute(
            "select item_id, mega_forme_id from dim_item where is_mega_stone"
        ).fetchall())


def clear_cache() -> None:
    load_dex.cache_clear()
    load_stones.cache_clear()


def _resolve_by_holder(holder: Species, dex: Dex) -> str:
    direct = holder.pokemon_id + "mega"
    if direct in dex and dex[direct].is_mega:
        return direct
    megas = [s.pokemon_id for s in dex.values()
             if s.is_mega and s.base_species_id == holder.base_species_id]
    if holder.pokemon_id == holder.base_species_id:
        orphans = [m for m in megas if m.endswith("mega") and m[:-4] not in dex]
        if len(orphans) == 1:
            return orphans[0]
    raise LookupError(f"Can't resolve Mega forme for {holder.pokemon_id}; candidates {megas}")


def mega_forme_id(pokemon_id: str, item_id: str | None, *,
                  dex: Dex | None = None, stones: Stones | None = None) -> str | None:
    """Mega forme this holder becomes with this item, or None if it can't Mega Evolve."""
    dex = load_dex() if dex is None else dex
    stones = load_stones() if stones is None else stones
    if not item_id or item_id not in stones:
        return None
    holder = dex[pokemon_id]
    if stones[item_id]:
        forme = stones[item_id]
    else:
        species = STONE_SPECIES.get(item_id)
        if species is None:
            raise LookupError(f"Unmapped Mega stone {item_id!r}: add it to STONE_SPECIES")
        if holder.base_species_id != species:
            return None
        forme = _resolve_by_holder(holder, dex)
    return forme if dex[forme].base_species_id == holder.base_species_id else None


def _mega_ability(forme: Species, paste_ability: str | None) -> str | None:
    if len(forme.abilities) == 1:
        return forme.abilities[0]
    if paste_ability in forme.abilities:
        return paste_ability
    return forme.abilities[0] if forme.abilities else None


def mega_options(team: Sequence[Member], *, dex: Dex | None = None,
                 stones: Stones | None = None) -> dict[int, str]:
    """slot -> Mega forme id, for members holding their own stone."""
    out = {}
    for m in team:
        f = mega_forme_id(m.pokemon_id, m.item_id, dex=dex, stones=stones)
        if f:
            out[m.slot] = f
    return out


def resolve_team(team: Sequence[Member], mega_slot: int | None = None, *,
                 dex: Dex | None = None, stones: Stones | None = None) -> list[Forme]:
    """Battle formes for the team with at most one Mega active (mega_slot)."""
    dex = load_dex() if dex is None else dex
    options = mega_options(team, dex=dex, stones=stones)
    if mega_slot is not None and mega_slot not in options:
        raise ValueError(f"Slot {mega_slot} can't Mega Evolve; options: {options}")
    out = []
    for m in team:
        if m.slot == mega_slot:
            s = dex[options[m.slot]]
            ability = _mega_ability(s, m.ability_id)
        else:
            s = dex[m.pokemon_id]
            ability = m.ability_id
        out.append(Forme(m.slot, m.pokemon_id, s.pokemon_id, s.display_name,
                         s.types, ability, s.is_mega))
    return out
