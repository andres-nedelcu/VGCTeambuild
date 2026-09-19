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
from vgc.metafilter import MetaFilter
from vgc.stats import CHOICE_SCARF, calc_stat, nature_mod, scarf, sp_from_investment
from vgc.team import Member

OUTSPEED, DEPENDS, OUTSPED = "You outspeed", "Depends", "Outsped"
MOVE_FIRST, MOVE_LAST = "You move first", "They move first"
BUILD_CMD = "uv run python scripts/build_marts.py"

TAILWIND_NONE, TAILWIND_YOURS, TAILWIND_THEIRS, TAILWIND_BOTH = "none", "yours", "theirs", "both"
TAILWIND_OPTIONS = (TAILWIND_NONE, TAILWIND_YOURS, TAILWIND_THEIRS, TAILWIND_BOTH)


@dataclass(frozen=True)
class Field:
    """Field-effect state for a Speed comparison. Defaults to no effects."""
    tailwind: str = TAILWIND_NONE
    trick_room: bool = False

    def __post_init__(self) -> None:
        if self.tailwind not in TAILWIND_OPTIONS:
            raise ValueError(f"tailwind must be one of {TAILWIND_OPTIONS}, got {self.tailwind!r}")

    @property
    def your_tailwind(self) -> bool:
        return self.tailwind in (TAILWIND_YOURS, TAILWIND_BOTH)

    @property
    def their_tailwind(self) -> bool:
        return self.tailwind in (TAILWIND_THEIRS, TAILWIND_BOTH)


def _scale(value: int, doubled: bool) -> int:
    return value * 2 if doubled else value


@dataclass(frozen=True)
class TeamSpeed:
    slot: int
    display_name: str
    base_spe: int
    sp: int
    nature: str | None
    speed: int          # after the item, so this is the number to compare with
    scarfed: bool = False


@lru_cache(maxsize=1)
def base_speeds() -> dict[str, int]:
    with session() as con:
        return dict(con.execute("select pokemon_id, spe from dim_pokemon").fetchall())


def clear_cache() -> None:
    base_speeds.cache_clear()


def team_speeds(team: Sequence[Member], formes: Sequence[Forme]) -> list[TeamSpeed]:
    """Actual Speed for each resolved forme, from that member's nature, SP and item.

    Choice Scarf is applied to your own Pokemon outright, where for a meta threat it
    only sets a flag. That asymmetry is deliberate and is the whole point: your item
    is a fact read from the paste, theirs is inferred from how often the species is
    seen holding one. Applying a known item keeps every number provably correct.

    A Mega-evolved slot holds its stone, not a Scarf, so the two never collide.
    """
    spe = base_speeds()
    by_slot = {m.slot: m for m in team}
    out = []
    for f in formes:
        member = by_slot[f.slot]
        sp = sp_from_investment(member.investment)["spe"]
        base = spe[f.forme_id]
        raw = calc_stat(base, sp, nature_mod(member.nature, "spe"))
        scarfed = member.item_id == CHOICE_SCARF
        out.append(TeamSpeed(f.slot, f.display_name, base, sp, member.nature,
                             scarf(raw) if scarfed else raw, scarfed))
    return out


def meta_speed(regulation: str, top_n: int | None = None,
               filt: MetaFilter | None = None) -> pd.DataFrame:
    """Speed benchmarks for the regulation's threats, most used first, then fastest first."""
    filt = filt or MetaFilter()
    with session() as con:
        try:
            df = con.execute(f"""
                select display_name, base_spe, spe_max_plus, spe_max_neutral,
                       spe_uninvested, spe_uninvested_neg, spe_max_plus_scarf,
                       spe_max_neutral_scarf, scarf_share, scarf_flag, forme_usage_pct
                from {filt.call('meta_speed')}
                order by forme_usage_pct desc
            """, filt.params(regulation)).df()
        except Exception as e:  # noqa: BLE001 - surfaced to the user as a build hint
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e
    if top_n:
        df = df.head(top_n)
    return df.sort_values(["base_spe", "forme_usage_pct"], ascending=False).reset_index(drop=True)


def ceiling(row, field: Field | None = None) -> int:
    """Fastest Speed this threat realistically reaches, Scarf included only when common.

    Modifiers chain Scarf first, then Tailwind, each floored in turn: the mart already
    floors the Scarf multiply, and doubling an integer for Tailwind needs no further
    floor. Reordering them is a real bug, not a cosmetic one — see test_speed.py.
    """
    field = field or Field()
    base = row.spe_max_plus_scarf if row.scarf_flag else row.spe_max_plus
    return _scale(int(base), field.their_tailwind)


def floor_speed(row, field: Field | None = None) -> int:
    """Slowest Speed this threat realistically has — the bound Trick Room wins against."""
    field = field or Field()
    return _scale(int(row.spe_uninvested_neg), field.their_tailwind)


def benchmarks(row, field: Field | None = None) -> tuple[int, ...]:
    field = field or Field()
    values = [row.spe_max_plus, row.spe_max_neutral, row.spe_uninvested, row.spe_uninvested_neg]
    if row.scarf_flag:
        values += [row.spe_max_plus_scarf, row.spe_max_neutral_scarf]
    return tuple(_scale(int(v), field.their_tailwind) for v in values)


def matchup(my_speed: int, row, field: Field | None = None) -> str:
    """Verdict for one of your Pokémon against one threat, flagging exact speed ties.

    Tailwind doubles a side's Speed before the comparison. Trick Room inverts the
    comparison, not the numbers: slower moves first, so winning means being slower
    than the threat's slowest realistic spread, and losing means being faster than
    its fastest.
    """
    field = field or Field()
    my_eff = _scale(my_speed, field.your_tailwind)
    top, bottom = ceiling(row, field), floor_speed(row, field)
    if field.trick_room:
        if my_eff < bottom:
            result = MOVE_FIRST
        elif my_eff > top:
            result = MOVE_LAST
        else:
            result = DEPENDS
    else:
        if my_eff > top:
            result = OUTSPEED
        elif my_eff < bottom:
            result = OUTSPED
        else:
            result = DEPENDS
    return f"{result} · tie" if my_eff in benchmarks(row, field) else result
