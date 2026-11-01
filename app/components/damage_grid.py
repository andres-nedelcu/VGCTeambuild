"""Visual 8: what the meta does to you in HP, not type multipliers."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.palette import (BAD_SOFT, BAD_STRONG, GOOD_SOFT, GOOD_STRONG, NEUTRAL,
                                discrete_scale)
from components.sprite_axis import add_column_sprites, add_row_sprites, tick_push
from vgc.sprites import data_uri

# Bands of guaranteed damage. Green is good for you here as everywhere else, so the
# ramp runs from "shrugs it off" to "dies outright".
CUTS = [25, 50, 75, 100]
BAND_COLORS = [GOOD_STRONG, GOOD_SOFT, NEUTRAL, BAD_SOFT, BAD_STRONG]
ROW_PX = 44


def _band(pct: float) -> int:
    for i, cut in enumerate(CUTS):
        if pct < cut:
            return i
    return len(CUTS)


def render_damage_grid(rows, team: list[tuple[str, str]]) -> None:
    """rows = Incoming records; team = [(display_name, forme_id)] top to bottom."""
    if not rows:
        st.info("No damage to show at this filter.")
        return

    order = [name for name, _fid in team]

    threats = list(dict.fromkeys(h.threat.display_name for h in rows))
    pct = {(h.target_name, h.threat.display_name): h.worst.low_pct for h in rows}
    move = {(h.target_name, h.threat.display_name): h.worst.move_name for h in rows}

    z, text, hover = [], [], []
    for mon in order:
        z.append([_band(pct.get((mon, t), 0.0)) for t in threats])
        text.append([f"{pct.get((mon, t), 0.0):.0f}" for t in threats])
        hover.append([f"{move.get((mon, t), '—')}: {pct.get((mon, t), 0.0):.0f}% guaranteed"
                      for t in threats])

    height = ROW_PX * (len(order) + 1) + 96
    fig = go.Figure(go.Heatmap(
        z=z, x=threats, y=order, zmin=-0.5, zmax=len(BAND_COLORS) - 0.5,
        colorscale=discrete_scale(BAND_COLORS), showscale=False,
        text=text, texttemplate="%{text}", customdata=hover,
        hovertemplate="%{y} vs %{x}<br>%{customdata}<extra></extra>", xgap=2, ygap=2))
    fig.update_yaxes(autorange="reversed", **tick_push(True), automargin=True)
    fig.update_xaxes(side="top", tickangle=0, showticklabels=False, **tick_push(True))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=96, b=20))

    forme_of = {h.threat.display_name: h.threat.forme_id for h in rows}
    add_column_sprites(fig, [data_uri(forme_of[t]) for t in threats], height)
    add_row_sprites(fig, [data_uri(fid) for _name, fid in team])
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Guaranteed damage as a percentage of your HP — the **worst roll** against the "
        "**heaviest legal investment** that threat could be carrying, because survival "
        "is planned against the worst case, not the median. 100 or more means it dies. "
        "Numbers come from the same formula Showdown uses, pinned against its simulator."
    )


def render_incoming_table(rows) -> None:
    if not rows:
        return
    view = pd.DataFrame({
        "": [data_uri(h.threat.forme_id) for h in rows],
        "Threat": [h.threat.display_name for h in rows],
        "Move": [h.worst.move_name for h in rows],
        "Into": [h.target_name for h in rows],
        "Likely": [f"{h.likely.low_pct:.0f}–{h.likely.high_pct:.0f}%" for h in rows],
        "Worst case": [f"{h.worst.low_pct:.0f}–{h.worst.high_pct:.0f}%" for h in rows],
        "Verdict": [h.worst.verdict() for h in rows],
        "Build known": ["" if h.confident else "split" for h in rows],
    })
    st.dataframe(
        view, hide_index=True, width="stretch",
        column_config={
            "": st.column_config.ImageColumn(),
            "Likely": st.column_config.TextColumn(
                help="The meta's most common offensive investment for that species"),
            "Worst case": st.column_config.TextColumn(
                help="32 SP and a boosting nature — the most it could legally carry"),
            "Build known": st.column_config.TextColumn(
                help="'split' means that species' investment is close to a coin flip, "
                     "so lean on the worst case rather than the likely one"),
        },
    )
    st.caption(
        "Your side is exact — species, nature, investment and item from your paste. "
        "Their side is the meta's common build, and the item and moves are what most "
        "people bring rather than what the player across from you brought. "
        "**Modelled:** weather, terrain, stat stages, and held items — including "
        "resist berries, terrain seeds and Focus Sash. "
        "**Not modelled:** abilities that scale damage, screens (Reflect, Light "
        "Screen, Aurora Veil), critical hits, burn, multi-hit and fixed-damage "
        "moves, and any weather beyond rain and sun."
    )


TIER_STYLE = {
    "OHKO": ("🔴", "dies to a single hit — do not leave it in against these"),
    "2HKO": ("🟠", "dies to two — it can come in once, not twice"),
    "3HKO": ("🟡", "three hits; it can take a turn here"),
    "Cannot threaten it": ("🟢", "cannot KO it inside three hits"),
}


def render_focus(buckets: dict, target_name: str, show: list[str]) -> None:
    """One of your Pokémon, and what each threat does to it, grouped by KO tier."""
    counts = {t: len(v) for t, v in buckets.items()}
    st.caption(" · ".join(
        f"{TIER_STYLE[t][0]} **{counts[t]}** {t}" for t in buckets if counts[t]))

    shown = [t for t in buckets if t in show]
    if not shown or not any(counts[t] for t in shown):
        st.info("Nothing in the selected brackets.")
        return

    for t in shown:
        rows = buckets[t]
        if not rows:
            continue
        icon, blurb = TIER_STYLE[t]
        st.markdown(f"**{icon} {t}** — {blurb}")
        st.dataframe(
            pd.DataFrame({
                "": [data_uri(h.threat.forme_id) for h in rows],
                "Threat": [h.threat.display_name for h in rows],
                "Move": [h.worst.move_name for h in rows],
                "Worst case": [f"{h.worst.low_pct:.0f}–{h.worst.high_pct:.0f}%" for h in rows],
                "Likely": [f"{h.likely.low_pct:.0f}–{h.likely.high_pct:.0f}%" for h in rows],
                "Verdict": [h.worst.verdict() for h in rows],
                "Build known": ["" if h.confident else "split" for h in rows],
            }),
            hide_index=True, width="stretch",
            column_config={"": st.column_config.ImageColumn()},
        )
