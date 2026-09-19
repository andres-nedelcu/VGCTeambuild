"""Visual 2: offensive coverage heatmap, your Pokémon x the meta's threats."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from components.palette import (ATTACKING, BAD_STRONG, LABELS, LEVELS, PALE_GOOD,
                                discrete_scale)
from vgc.offense import BEST_ROW

COLORS = ATTACKING  # you are landing the hit, so 4x is the good end
SUMMARY_COLORS = [BAD_STRONG, PALE_GOOD]  # 0 = nothing super effective, 1 = covered
SPRITE_PX = 44   # sprite edge in pixels; converted to a paper fraction per figure,
                 # because a fixed fraction would shrink as the team adds rows
LABEL_GAP = 8    # clear air between the sprite row and the usage numbers above it
# Tick labels and layout images both anchor to the top of the plot area, so they land
# in the same band and the numbers get clipped. Pushing the labels out with a
# transparent outside tick is what reserves the sprite row underneath them.
LABEL_PUSH = SPRITE_PX + LABEL_GAP
TRANSPARENT = "rgba(0,0,0,0)"


def render_coverage_grid(matrix: pd.DataFrame, best: pd.Series, usage: dict[str, float],
                         sprites: dict[str, str | None] | None = None) -> None:
    """Sprites identify the columns; without them the names have to be angled to fit.

    At 20+ threats a name like "Salamence-Mega" cannot sit horizontally in a column
    about 50px wide, so it used to be rotated 55 degrees and still collided with its
    neighbours. A sprite reads instantly at that size, which lets the tick label drop
    to the usage figure alone. The full name stays in the hover, and every sprite
    falls back to an angled name if it is missing.
    """
    sprites = sprites or {}
    names = list(matrix.columns)
    have_sprites = any(sprites.get(n) for n in names)
    # x stays the display names, which are unique. Rounding usage to whole percents
    # is not: three of the top 20 sit at 10%, and duplicate category values make
    # Plotly fold those columns into one. Only the tick TEXT carries the short label.
    columns = names
    # No "%" suffix in the sprite layout: three characters per tick collide at 20+
    # columns. The caption says the number is a usage percentage.
    ticktext = ([f"{100 * usage.get(c, 0):.0f}" for c in names] if have_sprites
                else [f"{c} {100 * usage.get(c, 0):.0f}%" for c in names])
    idx = matrix.map(LEVELS.index)
    text = matrix.map(lambda v: LABELS[LEVELS.index(v)])

    best_frame = best.to_frame().T
    codes = (best_frame > 1).astype(int)

    n = len(matrix)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[n, 1], vertical_spacing=0.06)
    fig.add_trace(go.Heatmap(
        z=idx.values, x=columns, y=list(matrix.index),
        zmin=-0.5, zmax=len(LEVELS) - 0.5, colorscale=discrete_scale(COLORS),
        showscale=False, text=text.values, texttemplate="%{text}",
        customdata=matrix.values,
        hovertemplate="%{y} vs %{x}: %{customdata}×<extra></extra>",
        xgap=2, ygap=2,
    ), row=1, col=1)
    fig.add_trace(go.Heatmap(
        z=codes.values, x=columns, y=[BEST_ROW],
        zmin=-0.5, zmax=len(SUMMARY_COLORS) - 0.5,
        colorscale=discrete_scale(SUMMARY_COLORS), showscale=False,
        text=best_frame.values, texttemplate="%{text}",
        hovertemplate="%{x} · best on team: %{text}×<extra></extra>",
        xgap=2, ygap=2,
    ), row=2, col=1)
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(showticklabels=True, side="top",
                     tickangle=0 if have_sprites else -55,
                     tickmode="array", tickvals=columns, ticktext=ticktext,
                     tickfont=dict(size=10) if have_sprites else None,
                     ticks="outside" if have_sprites else "",
                     ticklen=LABEL_PUSH if have_sprites else 0,
                     tickcolor=TRANSPARENT,
                     row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)  # threat names are long; once is enough
    # Room for the sprite row, the gap, and the number sitting above both.
    top_margin = (LABEL_PUSH + 34) if have_sprites else 160
    height = 44 * (n + 2) + top_margin + 40
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=top_margin, b=40))

    for i, name in enumerate(names):
        uri = sprites.get(name)
        if not uri:
            continue
        fig.add_layout_image(
            source=uri, xref="x", yref="paper", x=i, y=1.0,
            sizex=1.0, sizey=SPRITE_PX / height, xanchor="center", yanchor="bottom",
            sizing="contain", layer="above",
        )

    st.plotly_chart(fig, width="stretch")
    st.caption(
        ("Sprites label the columns; the number above each is that threat's usage %. "
         if have_sprites else "") +
        "Best multiplier each Pokémon has against that threat, from the types of its "
        "damaging moves — type matchup only, not a damage calc. Threat typing uses the "
        "Mega forme where the Mega is common, and its ability is taken into account "
        "(so Levitate shows as 0 against Ground). Red 'Team best' = nothing on the team "
        "hits it super effectively."
    )
