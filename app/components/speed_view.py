"""Visual 3: meta Speed benchmarks with your team measured against them."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vgc.speed import (DEPENDS, MOVE_FIRST, MOVE_LAST, OUTSPED, OUTSPEED, TAILWIND_BOTH,
                        TAILWIND_NONE, TAILWIND_THEIRS, TAILWIND_YOURS, Field, TeamSpeed,
                        matchup)

# Explicit text colour: these light fills also have to read on the dark theme.
SCARF_BG = "background-color: #bbf7d0; color: #14532d"  # Choice Scarf is common here
GOOD_BG = "background-color: #bbf7d0; color: #14532d"
DEPENDS_BG = "background-color: #fed7aa; color: #7c2d12"
BAD_BG = "background-color: #fecaca; color: #7f1d1d"
VERDICT_BG = {
    # Green always means good for you, in both Speed order and Trick Room (HANDOFF §6.3).
    OUTSPEED: GOOD_BG,
    MOVE_FIRST: GOOD_BG,
    DEPENDS: DEPENDS_BG,
    OUTSPED: BAD_BG,
    MOVE_LAST: BAD_BG,
}
SCARF_COLS = ["Max ⚡", "Neu ⚡"]


def render_team_speeds(speeds: list[TeamSpeed]) -> None:
    st.dataframe(pd.DataFrame([
        {"Slot": s.slot, "Pokémon": s.display_name, "Base": s.base_spe,
         "Nature": (s.nature or "-").title(), "Spe SP": s.sp,
         "⚡": "Scarf" if s.scarfed else "", "Speed": s.speed}
        for s in sorted(speeds, key=lambda s: s.speed, reverse=True)
    ]), hide_index=True, width="stretch")


def render_speed_tiers(meta: pd.DataFrame, reference: TeamSpeed | None,
                        field: Field | None = None) -> None:
    field = field or Field()
    their_mult = 2 if field.their_tailwind else 1
    view = pd.DataFrame({
        "Threat": meta["display_name"],
        "Usage %": 100 * meta["forme_usage_pct"],
        "Base": meta["base_spe"],
        "Max": meta["spe_max_plus"] * their_mult,
        "Neu": meta["spe_max_neutral"] * their_mult,
        "0 SP": meta["spe_uninvested"] * their_mult,
        "Neg": meta["spe_uninvested_neg"] * their_mult,
        SCARF_COLS[0]: meta["spe_max_plus_scarf"] * their_mult,
        SCARF_COLS[1]: meta["spe_max_neutral_scarf"] * their_mult,
    })
    verdict_col = None
    if reference is not None:
        # Second column, not last: it is the answer the table exists to give, and a
        # trailing column falls off the right edge of the grid.
        ref_speed = reference.speed * 2 if field.your_tailwind else reference.speed
        verdict_col = f"vs {reference.display_name} ({ref_speed})"
        view.insert(1, verdict_col, [matchup(reference.speed, r, field) for r in meta.itertuples()])

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
    st.caption(f"**Field: {_field_caption(field)}.** " + (
        "Numbers above are unmodified." if field.tailwind == TAILWIND_NONE and not field.trick_room
        else "Threat columns and the verdict already include Tailwind where it applies "
             "(their side's numbers here, your Speed in the header), and Trick Room's "
             "verdicts mean who moves first, not who is faster."
    ))


def _field_caption(field: Field) -> str:
    bits = []
    if field.tailwind == TAILWIND_NONE:
        bits.append("no Tailwind")
    elif field.tailwind == TAILWIND_YOURS:
        bits.append("Tailwind on your side")
    elif field.tailwind == TAILWIND_THEIRS:
        bits.append("Tailwind on theirs")
    elif field.tailwind == TAILWIND_BOTH:
        bits.append("Tailwind on both sides")
    bits.append("Trick Room" if field.trick_room else "no Trick Room")
    return ", ".join(bits)
