"""Champions stat formula (level 50). Single source of truth for stat math."""
from __future__ import annotations

import json
from typing import Any

STATS = ("hp", "atk", "def", "spa", "spd", "spe")
SP_MAX_PER_STAT = 32
SP_MAX_TOTAL = 66

# nature -> (boosted stat, lowered stat); neutral natures omitted
NATURES: dict[str, tuple[str, str]] = {
    "adamant": ("atk", "spa"), "bold": ("def", "atk"), "brave": ("atk", "spe"),
    "calm": ("spd", "atk"), "careful": ("spd", "spa"), "gentle": ("spd", "def"),
    "hasty": ("spe", "def"), "impish": ("def", "spa"), "jolly": ("spe", "spa"),
    "lax": ("def", "spd"), "lonely": ("atk", "def"), "mild": ("spa", "def"),
    "modest": ("spa", "atk"), "naive": ("spe", "spd"), "naughty": ("atk", "spd"),
    "quiet": ("spa", "spe"), "rash": ("spa", "spd"), "relaxed": ("def", "spe"),
    "sassy": ("spd", "spe"), "timid": ("spe", "atk"),
}
NEUTRAL = {"bashful", "docile", "hardy", "quirky", "serious"}


def nature_mod(nature: str | None, stat: str) -> float:
    """1.1 / 0.9 / 1.0. Missing nature is treated as neutral."""
    if nature is None:
        return 1.0
    n = nature.strip().lower()
    if n in NEUTRAL:
        return 1.0
    if n not in NATURES:
        raise ValueError(f"Unknown nature: {nature!r}")
    plus, minus = NATURES[n]
    return 1.1 if stat == plus else 0.9 if stat == minus else 1.0


def sp_from_investment(inv: dict[str, Any] | str | None) -> dict[str, int]:
    """Normalize my_team.investment to SP per stat.

    unit 'sp' -> validated as SP.
    unit 'ev' -> treated as SP if within SP limits; real EVs are rejected.
    """
    if inv is None:
        return dict.fromkeys(STATS, 0)
    if isinstance(inv, str):
        inv = json.loads(inv)
    unit = (inv.get("unit") or "").lower()
    if unit not in ("sp", "ev"):
        raise ValueError(f"Unknown investment unit: {unit!r}")

    raw = {str(k).lower(): int(v) for k, v in (inv.get("values") or {}).items()}
    bad = set(raw) - set(STATS)
    if bad:
        raise ValueError(f"Unknown stat keys: {sorted(bad)}")
    sp = {s: raw.get(s, 0) for s in STATS}

    total = sum(sp.values())
    fits = all(0 <= v <= SP_MAX_PER_STAT for v in sp.values()) and total <= SP_MAX_TOTAL
    if not fits:
        hint = " Looks like mainline EVs; re-export from Champions." if unit == "ev" else ""
        raise ValueError(f"Investment exceeds SP limits (32/stat, 66 total): {sp}.{hint}")
    return sp


def calc_stat(base: int, investment: int, nature_mod: float = 1.0,
              level: int = 50, stat: str = "spe") -> int:
    """HP = base + SP + 75. Others = floor((base + SP + 20) * nature)."""
    if level != 50:
        raise ValueError("Champions formula is only defined for level 50")
    if stat not in STATS:
        raise ValueError(f"Unknown stat: {stat!r}")
    if not 0 <= investment <= SP_MAX_PER_STAT:
        raise ValueError(f"SP out of range: {investment}")
    if stat == "hp":
        return base + investment + 75
    pct = round(nature_mod * 100)          # integer math, matches Showdown
    if pct not in (90, 100, 110):
        raise ValueError(f"Invalid nature modifier: {nature_mod}")
    return (base + investment + 20) * pct // 100
