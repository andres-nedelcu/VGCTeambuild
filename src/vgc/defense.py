"""Defensive type grid (Visual 1): selected formes x 18 attacking types."""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from vgc.megas import Forme
from vgc.typechart import TYPES, effectiveness

WEAK_ROW = "Weak (>1x)"
RESIST_ROW = "Resist/Immune (<1x)"
FLAG_MIN_WEAK = 3


def row_label(f: Forme) -> str:
    return f"{f.slot}. {f.display_name}"


def defense_matrix(formes: Sequence[Forme]) -> pd.DataFrame:
    """Rows = formes (slot order), columns = TYPES, values = multiplier."""
    data = {
        row_label(f): [effectiveness(t, f.types, f.ability_id) for t in TYPES]
        for f in formes
    }
    return pd.DataFrame.from_dict(data, orient="index", columns=list(TYPES))


def summarize(matrix: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {WEAK_ROW: (matrix > 1).sum(), RESIST_ROW: (matrix < 1).sum()}
    ).T.astype(int)


def flagged_types(summary: pd.DataFrame) -> list[str]:
    """Types with weak >= 3 and no resist/immune."""
    weak, resist = summary.loc[WEAK_ROW], summary.loc[RESIST_ROW]
    return [t for t in summary.columns if weak[t] >= FLAG_MIN_WEAK and resist[t] == 0]


def mega_comparison(team, slots) -> pd.DataFrame:
    """One row per Mega option (No Mega + selected stone holders) for the selected slots."""
    from vgc.megas import mega_options, resolve_team

    options = [None] + [s for s in mega_options(team) if s in slots]
    rows = []
    for opt in options:
        formes = [f for f in resolve_team(team, opt) if f.slot in slots]
        s = summarize(defense_matrix(formes))
        label = "No Mega" if opt is None else next(
            row_label(f) for f in formes if f.slot == opt)
        rows.append({
            "Option": label,
            "Weak": int(s.loc[WEAK_ROW].sum()),
            "Resist/Immune": int(s.loc[RESIST_ROW].sum()),
            "Flagged": ", ".join(flagged_types(s)) or "—",
        })
    df = pd.DataFrame(rows)
    df["Δ Weak"] = df["Weak"] - df.loc[0, "Weak"]
    df["Δ Resist/Immune"] = df["Resist/Immune"] - df.loc[0, "Resist/Immune"]
    return df
