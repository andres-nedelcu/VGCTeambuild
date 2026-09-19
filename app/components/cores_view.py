"""Visual 5: teammate cores — what the meta actually pairs together."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vgc.sprites import data_uri

LIFT_HELP = ("How much more often the pair appears together than independent picks "
             "would predict. Well above 1 means they are chosen for each other. Near 1 "
             "usually means chance — but not always: if a species has two builds that "
             "want opposite partners, they cancel out here. Two ceilings also apply: "
             "lift cannot exceed 1 / the more common member's usage, so a Pokémon on "
             "54% of teams can never show more than 1.85 with anything.")


def _sprite_col(ids: pd.Series) -> list[str | None]:
    return [data_uri(i) for i in ids]


def render_partners(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No partner appears often enough alongside this team to be worth "
                "reading. Widen the meta filter, or lower the support floor.")
        return
    view = pd.DataFrame({
        "": _sprite_col(df["partner_id"]),
        "Partner": df["partner"],
        "Pairs with": df["yours"],
        "Teams": df["together"],
        "Share": 100 * df["share"],
        "Lift": df["lift"],
    })
    st.dataframe(
        view, hide_index=True, width="stretch",
        column_config={
            "": st.column_config.ImageColumn(),
            "Teams": st.column_config.NumberColumn(format="%.0f",
                                                   help="Teams running both"),
            "Share": st.column_config.NumberColumn(
                format="%.0f%%", help="Of the teams running YOUR Pokémon, the share "
                                      "that also run this partner"),
            "Lift": st.column_config.NumberColumn(format="%.1f", help=LIFT_HELP),
        },
    )


def render_cores(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No pair clears the support floor under this meta filter.")
        return
    view = pd.DataFrame({
        "": _sprite_col(df["a_id"]),
        "Pokémon": df["a_name"],
        " ": _sprite_col(df["b_id"]),
        "Partner": df["b_name"],
        "Teams": df["together"],
        "Share of A": 100 * df["share_of_a"],
        "Share of B": 100 * df["share_of_b"],
        "Lift": df["lift"],
    })
    st.dataframe(
        view, hide_index=True, width="stretch",
        column_config={
            "": st.column_config.ImageColumn(),
            " ": st.column_config.ImageColumn(),
            "Teams": st.column_config.NumberColumn(format="%.0f"),
            "Share of A": st.column_config.NumberColumn(format="%.0f%%"),
            "Share of B": st.column_config.NumberColumn(format="%.0f%%"),
            "Lift": st.column_config.NumberColumn(format="%.1f", help=LIFT_HELP),
        },
    )


MAX_NAMES = 3  # a full list of ten holes truncates in the cell and reads as noise


def _listing(names: tuple[str, ...]) -> str:
    """Up to MAX_NAMES, then a count. The count is the number that ranks the row."""
    if not names:
        return "—"
    if len(names) <= MAX_NAMES:
        return f"{len(names)} · " + ", ".join(names)
    shown = ", ".join(names[:MAX_NAMES])
    return f"{len(names)} · {shown} +{len(names) - MAX_NAMES}"


def render_suggestions(rows, gaps: list[str], flags: list[str]) -> None:
    """Candidates ranked by what they fix. Every column is evidence, not a score."""
    problems = []
    if gaps:
        problems.append(f"**{len(gaps)} coverage hole{'s' if len(gaps) > 1 else ''}**: "
                        + ", ".join(gaps))
    if flags:
        problems.append(f"**flagged weakness{'es' if len(flags) > 1 else ''}**: "
                        + ", ".join(flags))
    st.caption("Fixing " + " · ".join(problems) if problems
               else "This team has no coverage holes and no flagged weaknesses at "
                    "the current settings, so these are partners rather than fixes.")

    if not rows:
        st.info("Nothing in the meta answers this team's gaps at the current filter.")
        return

    view = pd.DataFrame({
        "": [data_uri(s.forme_id) for s in rows],
        "Candidate": [s.display_name for s in rows],
        "Usage %": [100 * s.usage_pct for s in rows],
        "Covers": [_listing(s.holes_covered) for s in rows],
        "Resists": [_listing(s.flags_answered) for s in rows],
        "Pairs with": [s.partner or "—" for s in rows],
        "Lift": [s.lift for s in rows],
    })
    st.dataframe(
        view, hide_index=True, width="stretch",
        column_config={
            "": st.column_config.ImageColumn(),
            "Usage %": st.column_config.NumberColumn(format="%.1f"),
            "Covers": st.column_config.TextColumn(
                help="Threats nothing on your team hits super effectively, that this "
                     "one does with its commonly-run moves"),
            "Resists": st.column_config.TextColumn(
                help="Flagged types (3+ of yours weak, none resist) this one resists "
                     "or is immune to"),
            "Lift": st.column_config.NumberColumn(format="%.1f", help=LIFT_HELP),
        },
    )
    st.caption(
        "Sorted by holes covered, then flagged types answered, then synergy — no "
        "weights and no combined score, so the order is the columns you can see. "
        "Coverage is type matchup only, the same limit the coverage grid carries."
    )


def render_item_cores(df: pd.DataFrame) -> None:
    """Partnerships that only appear once you condition on the holder's item."""
    if df.empty:
        st.info("No build in scope changes its partners enough to be worth separating.")
        return
    view = pd.DataFrame({
        "": _sprite_col(df["holder_id"]),
        "Holder": df["holder_name"],
        "Item": df["item_name"].fillna(df["item_id"]),
        " ": _sprite_col(df["partner_id"]),
        "Partner": df["partner_name"],
        "Teams": df["holder_teams_with_item"],
        "With item": 100 * df["share"],
        "Normally": 100 * df["base_share"],
    })
    st.dataframe(
        view, hide_index=True, width="stretch",
        column_config={
            "": st.column_config.ImageColumn(),
            " ": st.column_config.ImageColumn(),
            "Teams": st.column_config.NumberColumn(
                format="%.0f", help="Teams running the holder with this item"),
            "With item": st.column_config.NumberColumn(
                format="%.0f%%", help="Share of those teams that also run the partner"),
            "Normally": st.column_config.NumberColumn(
                format="%.0f%%", help="Share across all of the holder's builds"),
        },
    )
    st.caption(
        "Sorted by the gap between the two percentages. A species is not always one "
        "thing: Sneasler runs Unburden on 89% of builds and a terrain seed on 58%, "
        "split almost evenly between Grassy and Psychic — the seed is consumed by the "
        "terrain and Unburden then doubles its Speed. Those two builds want different "
        "partners, so averaged together they cancel out and the pair looks like chance."
    )
