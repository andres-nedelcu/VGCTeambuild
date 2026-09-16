"""Type effectiveness, including ability overrides.

The type chart and ability modifiers are read from the warehouse once per
process and cached. Both can be injected (chart=, ability_mods=) for tests.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Mapping

from vgc.db import session
from vgc.ids import to_id

# Canonical order; also the column order for the defensive grid.
TYPES: tuple[str, ...] = (
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
)

Chart = Mapping[tuple[str, str], float]
AbilityMods = Mapping[tuple[str, str], float]

_TYPE_LOOKUP = {t.lower(): t for t in TYPES}


def normalize_type(name: str) -> str:
    """'ground' / ' GROUND ' -> 'Ground'. Raises ValueError for anything else."""
    try:
        return _TYPE_LOOKUP[name.strip().lower()]
    except (KeyError, AttributeError):
        raise ValueError(f"Unknown type: {name!r}") from None


@lru_cache(maxsize=1)
def load_type_chart() -> dict[tuple[str, str], float]:
    with session() as con:
        rows = con.execute(
            "select atk_type, def_type, multiplier from dim_type_chart"
        ).fetchall()
    chart = {(a, d): m for a, d, m in rows}
    expected = len(TYPES) ** 2
    if len(chart) != expected:
        raise RuntimeError(f"dim_type_chart has {len(chart)} rows, expected {expected}")
    return chart


@lru_cache(maxsize=1)
def load_ability_modifiers() -> dict[tuple[str, str], float]:
    with session() as con:
        rows = con.execute(
            "select ability_id, atk_type, multiplier from dim_ability_type_modifier"
        ).fetchall()
    return {(a, t): m for a, t, m in rows}


def clear_cache() -> None:
    load_type_chart.cache_clear()
    load_ability_modifiers.cache_clear()


def effectiveness(
    atk_type: str,
    def_types: Iterable[str | None],
    ability: str | None = None,
    *,
    chart: Chart | None = None,
    ability_mods: AbilityMods | None = None,
) -> float:
    """Multiplier for an attack of atk_type against a defender.

    def_types: the defender's types; None/empty entries (e.g. type2) are ignored.
    ability: display name or id; its modifier (if any) is applied after the chart.
    """
    chart = load_type_chart() if chart is None else chart
    atk = normalize_type(atk_type)
    defs = list(dict.fromkeys(normalize_type(t) for t in def_types if t))
    if not defs:
        raise ValueError("def_types has no valid types")

    mult = 1.0
    for d in defs:
        mult *= chart[(atk, d)]

    if ability:
        mods = load_ability_modifiers() if ability_mods is None else ability_mods
        mult *= mods.get((to_id(ability), atk), 1.0)

    return mult
