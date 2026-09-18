"""Visual 3: meta Speed benchmarks with your team measured against them."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vgc.speed import DEPENDS, OUTSPED, OUTSPEED, TeamSpeed, matchup

# Explicit text colour: these light fills also have to read on the dark theme.
SCARF_BG = "background-color: #bbf7d0; color: #14532d"  # Choice Scarf is common here
VERDICT_BG = {
    OUTSPEED: "background-color: #bbf7d0; color: #14532d",
    DEPENDS: "background-color: #fed7aa; color: #7c2d12",
    OUTSPED: "background-color: #fecaca; color: #7f1d1d",
}
SCARF_COLS = ["Max ⚡", "Neu ⚡"]


def render_team_speeds(speeds: list[TeamSpeed]) -> None:
    st.dataframe(pd.DataFrame([
        {"Slot": s.slot, "Pokémon": s.display_name, "Base": s.base_spe,
         "Nature": (s.nature or "-").title(), "Spe SP": s.sp, "Speed": s.speed}
        for s in sorted(speeds, key=lambda s: s.speed, reverse=True)
    ]), hide_index=True, width="stretch")


def render_speed_tiers(meta: pd.DataFrame, reference: TeamSpeed | None) -> None:
    view = pd.DataFrame({
        "Threat": meta["display_name"],
        "Usage %": 100 * meta["forme_usage_pct"],
        "Base": meta["base_spe"],
        "Max": meta["spe_max_plus"],
        "Neu": meta["spe_max_neutral"],
        "0 SP": meta["spe_uninvested"],
        "Neg": meta["spe_uninvested_neg"],
        SCARF_COLS[0]: meta["spe_max_plus_scarf"],
        SCARF_COLS[1]: meta["spe_max_neutral_scarf"],
    })
    verdict_col = None
    if reference is not None:
        # Second column, not last: it is the answer the table exists to give, and a
        # trailing column falls off the right edge of the grid.
        verdict_col = f"vs {reference.display_name} ({reference.speed})"
        view.insert(1, verdict_col, [matchup(reference.speed, r) for r in meta.itertuples()])

    scarf = meta["scarf_flag"].fillna(False).to_numpy(dtype=bool)

    def shade(_: pd.DataFrame) -> pd.DataFrame:
        css = pd.DataFrame("", index=view.index, columns=view.columns)
        css.loc[scarf, SCARF_COLS] = SCARF_BG
        if verdict_col:
            for label, bg in VERDICT_BG.items():
                css.loc[view[verdict_col].str.startswith(label), verdict_col] = bg
        return css

    st.dataframe(view.style.format({"Usage %": "{:.1f}"}).apply(shade, axis=None),
                 hide_index=True, width="stretch")
    st.caption(
        "Max / Neu = 32 SP with a +Spe or neutral nature · 0 SP / Neg = uninvested, "
        "neutral or -Spe nature · ⚡ = Choice Scarf. Green ⚡ cells mean Scarf is common "
        "enough on that threat to plan around, and those rows are judged against the "
        "Scarfed number. 'tie' means you hit one of its benchmarks exactly."
    )
