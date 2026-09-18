"""Speed benchmarks for the meta, and where your own team sits against them.

Every meta number comes from mart_meta_speed, which derives them from base Speed
alone. Choice Scarf is only taken into account for a threat when the mart flags it
as common, so the verdicts stay grounded in what people actually run.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

import pandas as pd

from vgc.db import session
from vgc.megas import Forme
from vgc.stats import calc_stat, nature_mod, sp_from_investment
from vgc.team import Member

OUTSPEED, DEPENDS, OUTSPED = "You outspeed", "Depends", "Outsped"
BUILD_CMD = "uv run python scripts/build_marts.py"


@dataclass(frozen=True)
class TeamSpeed:
    slot: int
    display_name: str
    base_spe: int
    sp: int
    nature: str | None
    speed: int


@lru_cache(maxsize=1)
def base_speeds() -> dict[str, int]:
    with session() as con:
        return dict(con.execute("select pokemon_id, spe from dim_pokemon").fetchall())


def clear_cache() -> None:
    base_speeds.cache_clear()


def team_speeds(team: Sequence[Member], formes: Sequence[Forme]) -> list[TeamSpeed]:
    """Actual Speed for each resolved forme, using that member's nature and SP."""
    spe = base_speeds()
    by_slot = {m.slot: m for m in team}
    out = []
    for f in formes:
        member = by_slot[f.slot]
        sp = sp_from_investment(member.investment)["spe"]
        base = spe[f.forme_id]
        out.append(TeamSpeed(f.slot, f.display_name, base, sp, member.nature,
                             calc_stat(base, sp, nature_mod(member.nature, "spe"))))
    return out


def meta_speed(regulation: str, top_n: int | None = None) -> pd.DataFrame:
    """Speed benchmarks for the regulation's threats, most used first, then fastest first."""
    with session() as con:
        try:
            df = con.execute("""
                select display_name, base_spe, spe_max_plus, spe_max_neutral,
                       spe_uninvested, spe_uninvested_neg, spe_max_plus_scarf,
                       spe_max_neutral_scarf, scarf_share, scarf_flag, forme_usage_pct
                from mart_meta_speed where regulation = ?
                order by forme_usage_pct desc
            """, [regulation]).df()
        except Exception as e:  # noqa: BLE001 - surfaced to the user as a build hint
            raise LookupError(f"mart_meta_speed is not built. Run: {BUILD_CMD}") from e
    if top_n:
        df = df.head(top_n)
    return df.sort_values(["base_spe", "forme_usage_pct"], ascending=False).reset_index(drop=True)


def ceiling(row) -> int:
    """Fastest Speed this threat realistically reaches, Scarf included only when common."""
    return int(row.spe_max_plus_scarf if row.scarf_flag else row.spe_max_plus)


def benchmarks(row) -> tuple[int, ...]:
    values = [row.spe_max_plus, row.spe_max_neutral, row.spe_uninvested, row.spe_uninvested_neg]
    if row.scarf_flag:
        values += [row.spe_max_plus_scarf, row.spe_max_neutral_scarf]
    return tuple(int(v) for v in values)


def matchup(my_speed: int, row) -> str:
    """Verdict for one of your Pokémon against one threat, flagging exact speed ties."""
    if my_speed > ceiling(row):
        result = OUTSPEED
    elif my_speed < int(row.spe_uninvested_neg):
        result = OUTSPED
    else:
        result = DEPENDS
    return f"{result} · tie" if my_speed in benchmarks(row) else result
