"""Visual 2: offensive coverage heatmap, your Pokémon x the meta's threats."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from vgc.offense import BEST_ROW

LEVELS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
LABELS = ["0", "¼", "½", "", "2", "4"]
# Same convention as the defensive grid: green is good for you, so the scale runs the
# other way here (hitting for 4x is good; being immune-walled is not).
COLORS = ["#4b5563", "#dc2626", "#fb923c", "#f3f4f6", "#86efac", "#15803d"]
SUMMARY_COLORS = ["#dc2626", "#bbf7d0"]  # 0 = nothing super effective, 1 = covered


def _discrete_scale(colors: list[str]) -> list[list]:
    n = len(colors)
    scale = []
    for i, c in enumerate(colors):
        scale += [[i / n, c], [(i + 1) / n, c]]
    return scale


def render_coverage_grid(matrix: pd.DataFrame, best: pd.Series, usage: dict[str, float]) -> None:
    columns = [f"{c} {100 * usage.get(c, 0):.0f}%" for c in matrix.columns]
    idx = matrix.map(LEVELS.index)
    text = matrix.map(lambda v: LABELS[LEVELS.index(v)])

    best_frame = best.to_frame().T
    codes = (best_frame > 1).astype(int)

    n = len(matrix)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[n, 1], vertical_spacing=0.06)
    fig.add_trace(go.Heatmap(
        z=idx.values, x=columns, y=list(matrix.index),
        zmin=-0.5, zmax=len(LEVELS) - 0.5, colorscale=_discrete_scale(COLORS),
        showscale=False, text=text.values, texttemplate="%{text}",
        customdata=matrix.values,
        hovertemplate="%{y} vs %{x}: %{customdata}×<extra></extra>",
        xgap=2, ygap=2,
    ), row=1, col=1)
    fig.add_trace(go.Heatmap(
        z=codes.values, x=columns, y=[BEST_ROW],
        zmin=-0.5, zmax=len(SUMMARY_COLORS) - 0.5,
        colorscale=_discrete_scale(SUMMARY_COLORS), showscale=False,
        text=best_frame.values, texttemplate="%{text}",
        hovertemplate="%{x} · best on team: %{text}×<extra></extra>",
        xgap=2, ygap=2,
    ), row=2, col=1)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(showticklabels=True, side="top", tickangle=-55, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)  # threat names are long; once is enough
    fig.update_layout(height=44 * (n + 2) + 200, margin=dict(l=10, r=10, t=160, b=40))

    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Best multiplier each Pokémon has against that threat, from the types of its "
        "damaging moves — type matchup only, not a damage calc. Threat typing uses the "
        "Mega forme where the Mega is common, and its ability is taken into account "
        "(so Levitate shows as 0 against Ground). Red 'Team best' = nothing on the team "
        "hits it super effectively."
    )
