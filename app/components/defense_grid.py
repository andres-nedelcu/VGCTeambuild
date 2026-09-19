"""Visual 1: defensive type heatmap with summary rows."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from components.palette import (BAD_STRONG, DEFENDING, LABELS, LEVELS, NEUTRAL,
                                PALE_CAUTION, PALE_GOOD, discrete_scale)
from components.sprite_axis import add_row_sprites, tick_push
from vgc.defense import RESIST_ROW, WEAK_ROW

COLORS = DEFENDING  # you are taking the hit, so 4x is the bad end
# summary codes: 0 none, 1 some weak, 2 flagged, 3 some resist
SUMMARY_COLORS = [NEUTRAL, PALE_CAUTION, BAD_STRONG, PALE_GOOD]


def render_defense_grid(matrix: pd.DataFrame, summary: pd.DataFrame, flags: list[str],
                        sprites: dict[str, str | None] | None = None) -> None:
    sprites = sprites or {}
    have_sprites = any(sprites.get(r) for r in matrix.index)
    types = list(matrix.columns)
    idx = matrix.map(LEVELS.index)
    text = matrix.map(lambda v: LABELS[LEVELS.index(v)])

    codes = pd.DataFrame(0, index=summary.index, columns=summary.columns)
    codes.loc[WEAK_ROW] = (summary.loc[WEAK_ROW] > 0).astype(int)
    codes.loc[RESIST_ROW] = (summary.loc[RESIST_ROW] > 0).astype(int) * 3
    for t in flags:
        codes.loc[WEAK_ROW, t] = 2

    n = len(matrix)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[n, 2], vertical_spacing=0.04)
    fig.add_trace(go.Heatmap(
        z=idx.values, x=types, y=list(matrix.index),
        zmin=-0.5, zmax=len(LEVELS) - 0.5, colorscale=discrete_scale(COLORS),
        showscale=False, text=text.values, texttemplate="%{text}",
        customdata=matrix.values,
        hovertemplate="%{y} vs %{x}: %{customdata}×<extra></extra>",
        xgap=2, ygap=2,
    ), row=1, col=1)
    fig.add_trace(go.Heatmap(
        z=codes.values, x=types, y=list(summary.index),
        zmin=-0.5, zmax=len(SUMMARY_COLORS) - 0.5,
        colorscale=discrete_scale(SUMMARY_COLORS), showscale=False,
        text=summary.values, texttemplate="%{text}",
        hovertemplate="%{x} · %{y}: %{text}<extra></extra>",
        xgap=2, ygap=2,
    ), row=2, col=1)
    fig.update_yaxes(autorange="reversed")
    fig.update_yaxes(**tick_push(have_sprites), automargin=True, row=1, col=1)
    fig.update_xaxes(showticklabels=True, side="top", row=1, col=1)
    fig.update_layout(height=44 * (n + 2) + 120, margin=dict(l=10, r=10, t=40, b=40))

    add_row_sprites(fig, [sprites.get(r) for r in matrix.index])

    # The floating modebar overlaps the top-right tick labels, and neither grid
    # is usefully pannable or zoomable, so it only ever covered data.
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("0 immune · ¼ / ½ resist · blank neutral · 2 / 4 weak. "
               "Red summary cell = flagged (3+ weak, nothing resists).")
