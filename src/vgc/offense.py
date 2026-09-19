"""Offensive coverage (Visual 2): your damaging move types against the meta's threats.

Type effectiveness only — no damage calc, no base power, no STAB. The question this
answers is "can anyone on this team hit that threat for super effective damage", which
is the first hole worth finding; how hard it hits is a later question.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

import pandas as pd

from vgc.db import session
from vgc.megas import Forme, load_dex
from vgc.metafilter import MetaFilter
from vgc.team import Member
from vgc.typechart import attack_type, effectiveness

BEST_ROW = "Team best"
BUILD_CMD = "uv run python scripts/build_marts.py"
SUPER_EFFECTIVE = 1.0  # a threat with nothing above this is a coverage hole


@dataclass(frozen=True)
class Attacker:
    slot: int
    display_name: str
    move_types: tuple[str, ...]


@dataclass(frozen=True)
class Threat:
    forme_id: str
    display_name: str
    types: tuple[str, ...]
    ability_id: str | None
    usage_pct: float


@lru_cache(maxsize=1)
def damaging_move_types() -> dict[str, str]:
    """move_id -> attacking type, for damaging moves only."""
    with session() as con:
        return dict(con.execute(
            "select move_id, type from dim_move where category <> 'Status'").fetchall())


@lru_cache(maxsize=1)
def common_abilities() -> dict[tuple[str, str], str]:
    """(regulation, species) -> most used ability id, from build data."""
    with session() as con:
        rows = con.execute("""
            select regulation, pokemon_id, detail_value from (
                select regulation, pokemon_id, detail_value,
                       row_number() over (partition by regulation, pokemon_id
                                          order by pct desc) as rn
                from mart_build_detail where detail_type = 'ability')
            where rn = 1
        """).fetchall()
    return {(reg, pid): ability for reg, pid, ability in rows}


def clear_cache() -> None:
    damaging_move_types.cache_clear()
    common_abilities.cache_clear()


def attackers(team: Sequence[Member], formes: Sequence[Forme]) -> list[Attacker]:
    """Each forme with the distinct types of its damaging moves."""
    types = damaging_move_types()
    by_slot = {m.slot: m for m in team}
    out = []
    for f in formes:
        moves = by_slot[f.slot].moves or []
        # The type it attacks as, not the type it is listed as: a Pixilate holder's
        # Normal moves land as Fairy.
        seen = dict.fromkeys(attack_type(types[m], f.ability_id) for m in moves if m in types)
        out.append(Attacker(f.slot, f.display_name, tuple(seen)))
    return out


def _threat_ability(regulation: str, species_id: str, forme_id: str) -> str | None:
    """A Mega's ability is fixed by its forme; otherwise use the most common build."""
    dex = load_dex()
    forme = dex[forme_id]
    if forme.is_mega and len(forme.abilities) == 1:
        return forme.abilities[0]
    common = common_abilities().get((regulation, species_id))
    if common and common in forme.abilities:
        return common
    return forme.abilities[0] if forme.abilities else None


def threats(regulation: str, top_n: int = 20,
            filt: MetaFilter | None = None) -> list[Threat]:
    """The top_n threats under this meta filter. No filter means the whole regulation."""
    filt = filt or MetaFilter()
    with session() as con:
        try:
            rows = con.execute(f"""
                select species_id, forme_id, display_name, type1, type2, forme_usage_pct
                from {filt.call('meta_top')}
                order by forme_usage_pct desc limit ?
            """, filt.params(regulation) + [top_n]).fetchall()
        except Exception as e:  # noqa: BLE001 - surfaced to the user as a build hint
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e
    return [
        Threat(forme_id, name, tuple(t for t in (t1, t2) if t),
               _threat_ability(regulation, species_id, forme_id), usage)
        for species_id, forme_id, name, t1, t2, usage in rows
    ]


def coverage_matrix(attacking: Sequence[Attacker], meta: Sequence[Threat]) -> pd.DataFrame:
    """Rows = your Pokémon, columns = threats, value = best multiplier that Pokémon has."""
    columns = [t.display_name for t in meta]
    data = {}
    for a in attacking:
        data[a.display_name] = [
            max((effectiveness(mt, t.types, t.ability_id) for mt in a.move_types), default=0.0)
            for t in meta
        ]
    return pd.DataFrame.from_dict(data, orient="index", columns=columns)


def team_best(matrix: pd.DataFrame) -> pd.Series:
    return matrix.max().rename(BEST_ROW)


def holes(matrix: pd.DataFrame) -> list[str]:
    """Threats no one on the team hits super effectively."""
    best = team_best(matrix)
    return [t for t in matrix.columns if best[t] <= SUPER_EFFECTIVE]
