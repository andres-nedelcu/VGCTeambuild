"""Visual 3: meta Speed benchmarks with your team measured against them."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.palette import FILL_BAD, FILL_CAUTION, FILL_GOOD, MUTED
from vgc.speed import (DEPENDS, LOW_CONFIDENCE, MOVE_FIRST, MOVE_LAST, OUTSPED, OUTSPEED,
                        TAILWIND_BOTH, TAILWIND_NONE, TAILWIND_THEIRS, TAILWIND_YOURS,
                        Field, TeamSpeed, matchup)

SCARF_BG = FILL_GOOD   # Choice Scarf is common enough on this threat to plan around
VERDICT_BG = {
    # Green always means good for you, in both Speed order and Trick Room (HANDOFF §6.3).
    OUTSPEED: FILL_GOOD,
    MOVE_FIRST: FILL_GOOD,
    DEPENDS: FILL_CAUTION,
    OUTSPED: FILL_BAD,
    MOVE_LAST: FILL_BAD,
}
SCARF_COLS = ["Max ⚡", "Neu ⚡"]
LIKELY_COL = "Likely"
# Muted rather than coloured: a split spread is not good or bad news, and the fills in
# this table already mean "good for you", which must keep meaning only that.
UNSURE = MUTED


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
        LIKELY_COL: meta["likely_spe"] * their_mult,
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
    unsure = (meta["likely_confidence"].fillna(0) < LOW_CONFIDENCE).to_numpy(dtype=bool)

    def shade(_: pd.DataFrame) -> pd.DataFrame:
        css = pd.DataFrame("", index=view.index, columns=view.columns)
        css.loc[scarf, SCARF_COLS] = SCARF_BG
        css.loc[unsure, LIKELY_COL] = UNSURE
        if verdict_col:
            for label, bg in VERDICT_BG.items():
                css.loc[view[verdict_col].str.startswith(label), verdict_col] = bg
        return css

    st.dataframe(view.style.format({"Usage %": "{:.1f}", LIKELY_COL: "{:.0f}"})
                 .apply(shade, axis=None), hide_index=True, width="stretch")
    st.caption(
        "**Likely** is what that threat is actually built as — its most common Speed "
        "investment and nature direction — placed inside the benchmark band beside it. "
        "It is an observation, never a verdict: the columns either side are exact, and "
        "the verdict is still judged against the whole band. Greyed values are split "
        "builds worth distrusting. Likely excludes items, so a green ⚡ row can also be "
        "running 1.5x this number."
    )
    _likely_detail(meta)
    st.caption(
        "Max / Neu = 32 SP with a +Spe or neutral nature · 0 SP / Neg = uninvested, "
        "neutral or -Spe nature · ⚡ = Choice Scarf. Green ⚡ cells mean Scarf is common "
        "enough on that threat to plan around, and those rows are judged against the "
        "Scarfed number. 'tie' means you hit one of its benchmarks exactly."
    )
    notes = []
    if field.tailwind != TAILWIND_NONE:
        notes.append("Tailwind is already applied: their side in the columns above, "
                     "your Speed in the verdict header.")
    if field.trick_room:
        notes.append("Under Trick Room the verdict is who moves first, not who is faster.")
    st.caption(f"**Field: {_field_caption(field)}.** "
               + (" ".join(notes) or "Numbers above are unmodified."))


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


def _likely_detail(meta: pd.DataFrame) -> None:
    """The evidence behind the Likely column, for someone planning a matchup properly."""
    detail = pd.DataFrame({
        "Threat": meta["display_name"],
        "Spe SP": meta["likely_spe_sp"],
        "of builds": 100 * meta["likely_spe_sp_share"],
        "Nature": meta["likely_nature_dir"].map(
            {"plus": "+Spe", "minus": "-Spe", "neutral": "neutral"}),
        "of builds ": 100 * meta["likely_nature_share"],
        LIKELY_COL: meta["likely_spe"],
    }).dropna(subset=[LIKELY_COL])
    with st.expander("Where “Likely” comes from"):
        st.dataframe(detail.style.format(
            {"of builds": "{:.0f}%", "of builds ": "{:.0f}%",
             "Spe SP": "{:.0f}", LIKELY_COL: "{:.0f}"}),
            hide_index=True, width="stretch")
        st.caption(
            "The two percentages are independent: Champions Battle Data publishes "
            "nature and spread distributions separately and never pairs them, so "
            "they are not multiplied into a single confidence. The Likely column is "
            "greyed when the weaker of the two falls below "
            f"{LOW_CONFIDENCE:.0%}."
        )
