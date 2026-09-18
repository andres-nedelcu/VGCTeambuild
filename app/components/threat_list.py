"""Visual 4: meta threats ranked by the type pressure they put on your team."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vgc.pressure import Pressure


def render_threat_list(rows: list[Pressure], team_size: int) -> None:
    table = pd.DataFrame([{
        "Threat": p.threat.display_name,
        "Usage %": 100 * p.threat.usage_pct,
        "Threat score": p.score,
        "Hits SE": p.super_effective,
        "Driver": (f"{p.top_hit.move_name} as {p.top_hit.move_type} "
                   f"{p.top_hit.value:g}× vs {p.top_hit.target}") if p.top_hit else "—",
    } for p in rows])

    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "Usage %": st.column_config.NumberColumn(format="%.1f"),
            "Threat score": st.column_config.ProgressColumn(
                format="%.0f", min_value=0.0,
                max_value=float(max(table["Threat score"].max(), 1))),
            "Hits SE": st.column_config.NumberColumn(
                f"Hits SE (of {team_size})",
                help="How many of your Pokémon it hits super effectively"),
        },
    )
    st.caption(
        "Score = usage × the average best hit it gets on your team, so it rewards "
        "threats that are both common and awkward for you. STAB is included and "
        "abilities that retype moves are applied (Salamence-Mega's Hyper Voice "
        "attacks as Flying). Type pressure only — it ignores base power, attacking "
        "stats, bulk and items, so it measures matchup, not damage."
    )

    by_name = {p.threat.display_name: p for p in rows}
    chosen = st.selectbox("Break down a threat", list(by_name))
    picked = by_name[chosen]
    st.dataframe(pd.DataFrame([{
        "Your Pokémon": h.target,
        "Its best move": h.move_name,
        "Attacks as": h.move_type,
        "Type matchup": f"{h.effectiveness:g}×",
        "With STAB": f"{h.value:g}×",
    } for h in sorted(picked.hits, key=lambda h: h.value, reverse=True)]),
        hide_index=True, width="stretch")
    if not picked.hits:
        st.info(f"{chosen} has no damaging move above the common-move threshold.")
