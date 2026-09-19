"""Sprites as axis labels on the Plotly grids.

Tick labels and layout images both anchor to the edge of the plot area, so placing a
sprite there without reserving space puts it on top of the text. Plotly has no
tick-label standoff that is portable across versions; a transparent *outside* tick of
the sprite's length reserves exactly the band needed, and the label lands beyond it.

Sizes are in pixels rather than paper fractions because a figure grows with the number
of Pokemon on the team, so a constant fraction shrinks the sprites as the team fills up.
"""

from __future__ import annotations

from typing import Sequence

SPRITE_PX = 44
LABEL_GAP = 8
LABEL_PUSH = SPRITE_PX + LABEL_GAP
TRANSPARENT = "rgba(0,0,0,0)"
# Sprite width as a share of figure width. Unknowable in pixels for a responsive
# chart, so it is set generously and sizing="contain" lets the row height decide.
ROW_SPRITE_WIDTH = 0.06


def tick_push(active: bool) -> dict:
    """Axis kwargs that reserve a sprite-sized band before the tick labels."""
    if not active:
        return {"ticks": "", "ticklen": 0}
    return {"ticks": "outside", "ticklen": LABEL_PUSH, "tickcolor": TRANSPARENT}


def add_column_sprites(fig, uris: Sequence[str | None], fig_height: int) -> None:
    """One sprite above each column, sized against the figure's pixel height."""
    for i, uri in enumerate(uris):
        if uri:
            fig.add_layout_image(
                source=uri, xref="x", yref="paper", x=i, y=1.0,
                sizex=1.0, sizey=SPRITE_PX / fig_height,
                xanchor="center", yanchor="bottom", sizing="contain", layer="above")


def add_row_sprites(fig, uris: Sequence[str | None]) -> None:
    """One sprite beside each row, in the left margin the tick push reserved."""
    for i, uri in enumerate(uris):
        if uri:
            fig.add_layout_image(
                source=uri, xref="paper", yref="y", x=0, y=i,
                sizex=ROW_SPRITE_WIDTH, sizey=1.0,
                xanchor="right", yanchor="middle", sizing="contain", layer="above")
