"""Visual 3: meta Speed benchmarks with your team measured against them."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.palette import (FILL_BAD, FILL_CAUTION, FILL_GOOD, FILL_TIE,
                                SCARF_MARK, UNRELIABLE)
from vgc.sprites import data_uri
from vgc.speed import (AHEAD, BEHIND, DEPENDS, LOW_CONFIDENCE, MOVE_FIRST, MOVE_LAST,
                        OUTSPED, OUTSPEED, TAILWIND_BOTH, TAILWIND_NONE, TAILWIND_THEIRS,
                        TAILWIND_YOURS, TIE, Field, TeamSpeed, against_benchmark, matchup)

VERDICT_BG = {
    # Green always means good for you, in both Speed order and Trick Room (HANDOFF §6.3).
    OUTSPEED: FILL_GOOD,
    MOVE_FIRST: FILL_GOOD,
    DEPENDS: FILL_CAUTION,
    OUTSPED: FILL_BAD,
    MOVE_LAST: FILL_BAD,
}
# Every benchmark cell answers the same question the verdict column does, one number
# at a time, so it takes the same three colours. Reading across a row then shows where
# your Speed actually sits inside that threat's range instead of leaving you to
# compare seven numbers against a header by eye.
BENCHMARK_BG = {AHEAD: FILL_GOOD, BEHIND: FILL_BAD, TIE: FILL_TIE}
SCARF_COLS = ["Max ⚡", "Neu ⚡"]
LIKELY_COL = "Likely"
# Displayed column -> the mart column behind it. These are the cells holding a Speed
# that can be compared with yours; "Base" is deliberately not among them, because it
# is a base stat rather than a Speed and colouring it would invite reading it as one.
# The mapping exists because the comparison reads the RAW value: `against_benchmark`
# applies Tailwind itself, and the displayed column already has their side doubled in.
SPEED_SOURCE = {
    LIKELY_COL: "likely_spe",
    "Max": "spe_max_plus",
    "Neu": "spe_max_neutral",
    "0 SP": "spe_uninvested",
    "Neg": "spe_uninvested_neg",
    SCARF_COLS[0]: "spe_max_plus_scarf",
    SCARF_COLS[1]: "spe_max_neutral_scarf",
}
# Not a colour of its own: a split spread is not good or bad news, and every fill in
# this table now means "good for you", which must keep meaning only that. It rides on
# top of whatever fill the cell already has.
UNSURE = UNRELIABLE


def _speeds(values: pd.Series, multiplier: int) -> list[str]:
    """A Speed column as text, with a missing benchmark shown as an empty cell.

    Text rather than numbers, and converted here rather than left to `Styler.format`:
    a column carrying pandas NA reaches Streamlit's grid as the literal string "None"
    and loses its cell styling on the way, because the styled display values are
    dropped for a column Arrow could not convert cleanly. Every Speed here is an
    integer benchmark that is only ever read, never sorted on as a number, so
    formatting at the source costs nothing and keeps the column styleable.

    A Mega forme is the only source of a missing value: it holds its stone, so a
    Scarfed Speed for it is not a number that was unavailable, it is one that cannot
    exist. The mart says so with a NULL and this turns that into a blank cell.
    """
    return ["" if pd.isna(v) else f"{int(v) * multiplier:.0f}" for v in values]


def render_team_speeds(speeds: list[TeamSpeed]) -> None:
    st.dataframe(pd.DataFrame([
        {"": data_uri(s.forme_id), "Pokémon": s.display_name, "Base": s.base_spe,
         "Nature": (s.nature or "-").title(), "Spe SP": s.sp,
         "⚡": "Scarf" if s.scarfed else "", "Speed": s.speed}
        for s in sorted(speeds, key=lambda s: s.speed, reverse=True)
    ]), hide_index=True, width="stretch",
        column_config={"": st.column_config.ImageColumn()})


def render_speed_tiers(meta: pd.DataFrame, reference: TeamSpeed | None,
                        field: Field | None = None) -> None:
    field = field or Field()
    their_mult = 2 if field.their_tailwind else 1
    view = pd.DataFrame({
        "Threat": meta["display_name"],
        "Usage %": 100 * meta["forme_usage_pct"],
        "Base": meta["base_spe"],
        **{col: _speeds(meta[source], their_mult)
           for col, source in SPEED_SOURCE.items()},
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
        if reference is not None:
            for col, source in SPEED_SOURCE.items():
                # A blank cell — a Mega's Scarf column, or a Likely with no build
                # data behind it — is not a comparison and takes no colour.
                css[col] = [
                    "" if pd.isna(v) else
                    BENCHMARK_BG[against_benchmark(reference.speed, int(v), field)]
                    for v in meta[source]
                ]
            for label, bg in VERDICT_BG.items():
                css.loc[view[verdict_col].str.startswith(label), verdict_col] = bg
        # Appended, not assigned: the Scarf marker and the split-build marker both
        # ride on top of the comparison colour rather than replacing it.
        css.loc[scarf, SCARF_COLS] = css.loc[scarf, SCARF_COLS] + "; " + SCARF_MARK
        css.loc[unsure, LIKELY_COL] = css.loc[unsure, LIKELY_COL] + "; " + UNSURE
        return css

    st.dataframe(view.style.format({"Usage %": "{:.1f}"}).apply(shade, axis=None),
                 hide_index=True, width="stretch")
    st.caption(
        "**Every Speed cell is coloured against the Pokémon you are comparing: "
        "green where you move first, red where they do, yellow on an exact tie.** "
        "Read across a row to see where you sit inside that threat's range, rather "
        "than against the whole band the verdict column judges."
    )
    st.caption(
        "**Likely** is what that threat is actually built as — its most common Speed "
        "investment and nature direction — placed inside the benchmark band beside it. "
        "It is an observation, never a verdict: the columns either side are exact, and "
        "the verdict is still judged against the whole band. Greyed values are split "
        "builds worth distrusting. Likely excludes items, so a bold ⚡ row can also "
        "be running 1.5x this number."
    )
    _likely_detail(meta)
    st.caption(
        "Max / Neu = 32 SP with a +Spe or neutral nature · 0 SP / Neg = uninvested, "
        "neutral or -Spe nature · ⚡ = Choice Scarf. **Bold blue** ⚡ cells mean Scarf "
        "is common enough on that threat to plan around, and those rows are judged "
        "against the Scarfed number — the fill behind the bold still says who moves "
        "first. The ⚡ cells are blank on a Mega Evolution, which is holding its stone "
        "and can never carry a Scarf. 'tie' in the verdict column means you hit one "
        "of its benchmarks exactly."
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
