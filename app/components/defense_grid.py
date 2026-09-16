"""Visual 1: defensive type heatmap with summary rows."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from vgc.defense import RESIST_ROW, WEAK_ROW

LEVELS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
LABELS = ["0", "¼", "½", "", "2", "4"]
COLORS = ["#4b5563", "#15803d", "#86efac", "#f3f4f6", "#fb923c", "#dc2626"]
# summary codes: 0 none, 1 some weak, 2 flagged, 3 some resist
SUMMARY_COLORS = ["#f3f4f6", "#fed7aa", "#dc2626", "#bbf7d0"]


def _discrete_scale(colors: list[str]) -> list[list]:
    n = len(colors)
    scale = []
    for i, c in enumerate(colors):
        scale += [[i / n, c], [(i + 1) / n, c]]
    return scale


def render_defense_grid(matrix: pd.DataFrame, summary: pd.DataFrame, flags: list[str]) -> None:
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
        zmin=-0.5, zmax=len(LEVELS) - 0.5, colorscale=_discrete_scale(COLORS),
        showscale=False, text=text.values, texttemplate="%{text}",
        customdata=matrix.values,
        hovertemplate="%{y} vs %{x}: %{customdata}×<extra></extra>",
        xgap=2, ygap=2,
    ), row=1, col=1)
    fig.add_trace(go.Heatmap(
        z=codes.values, x=types, y=list(summary.index),
        zmin=-0.5, zmax=len(SUMMARY_COLORS) - 0.5,
        colorscale=_discrete_scale(SUMMARY_COLORS), showscale=False,
        text=summary.values, texttemplate="%{text}",
        hovertemplate="%{x} · %{y}: %{text}<extra></extra>",
        xgap=2, ygap=2,
    ), row=2, col=1)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(showticklabels=True, side="top", row=1, col=1)
    fig.update_layout(height=44 * (n + 2) + 120, margin=dict(l=10, r=10, t=40, b=40))

    st.plotly_chart(fig, width="stretch")
    st.caption("0 immune · ¼ / ½ resist · blank neutral · 2 / 4 weak. "
               "Red summary cell = flagged (3+ weak, nothing resists).")
