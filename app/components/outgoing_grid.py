"""Visual 9: hits to KO each meta threat, and whether the KO survives their build."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.palette import (BAD_SOFT, BAD_STRONG, GOOD_SOFT, GOOD_STRONG, NEUTRAL,
                                discrete_scale)
from components.sprite_axis import add_column_sprites, add_row_sprites, tick_push
from vgc.outgoing import ALWAYS, LIKELY
from vgc.sprites import data_uri

ROW_PX = 44
# Five bands. The top one is deliberately its own colour rather than a shade of the
# second: "kills whatever they invested" is a different kind of fact from "kills the
# common build", and it is the one you can actually rely on in a game.
BANDS = [GOOD_STRONG, GOOD_SOFT, NEUTRAL, BAD_SOFT, BAD_STRONG]
CERTAIN_KO, LIKELY_KO, TWO_HIT, THREE_HIT, SLOWER = range(5)


def _band(hit) -> int:
    if hit.always_kos:
        return CERTAIN_KO
    if hit.likely_kos:
        return LIKELY_KO
    hits = hit.hits_to_ko
    if hits == 2:
        return TWO_HIT
    if hits == 3:
        return THREE_HIT
    return SLOWER


def _cell(hit) -> str:
    if hit.always_kos:
        return "1!"
    hits = hit.hits_to_ko
    return str(hits) if hits and hits <= 5 else "—"


def render_outgoing_grid(rows, team: list[tuple[str, str]]) -> None:
    if not rows:
        st.info("No damage to show at this filter.")
        return
    order = [name for name, _fid in team]
    threats = list(dict.fromkeys(h.threat.display_name for h in rows))
    by_key = {(h.attacker_name, h.threat.display_name): h for h in rows}

    z, text, hover = [], [], []
    for mon in order:
        zr, tr, hr = [], [], []
        for t in threats:
            hit = by_key.get((mon, t))
            if hit is None:
                zr.append(SLOWER); tr.append("—"); hr.append("no damaging move")
                continue
            zr.append(_band(hit)); tr.append(_cell(hit))
            hr.append(f"{hit.likely.move_name}: {hit.likely.low_pct:.0f}% on their "
                      f"common build, {hit.bulkiest.low_pct:.0f}% at max bulk "
                      f"({hit.certainty})")
        z.append(zr); text.append(tr); hover.append(hr)

    height = ROW_PX * (len(order) + 1) + 96
    fig = go.Figure(go.Heatmap(
        z=z, x=threats, y=order, zmin=-0.5, zmax=len(BANDS) - 0.5,
        colorscale=discrete_scale(BANDS), showscale=False,
        text=text, texttemplate="%{text}", customdata=hover,
        hovertemplate="%{y} vs %{x}<br>%{customdata}<extra></extra>", xgap=2, ygap=2))
    fig.update_yaxes(autorange="reversed", **tick_push(True), automargin=True)
    fig.update_xaxes(side="top", showticklabels=False, **tick_push(True))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=96, b=20))

    forme_of = {h.threat.display_name: h.threat.forme_id for h in rows}
    add_column_sprites(fig, [data_uri(forme_of[t]) for t in threats], height)
    add_row_sprites(fig, [data_uri(fid) for _n, fid in team])
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(
        "Guaranteed hits to KO their **common build**. **1!** in the darkest green is "
        "the one that matters: it KOs in one hit even against 32 HP, 32 in that "
        "defence and a boosting nature — the bulkiest thing they could legally be "
        "holding. A plain **1** kills what most people bring and might not kill an "
        "invested one. Their defensive spreads are the softest data in the set "
        "(modal share about two thirds), which is exactly why both are shown."
    )


def render_outgoing_table(rows) -> None:
    if not rows:
        return
    view = pd.DataFrame({
        "": [data_uri(h.threat.forme_id) for h in rows],
        "Threat": [h.threat.display_name for h in rows],
        "Your move": [f"{h.attacker_name}: {h.likely.move_name}" for h in rows],
        "Common build": [f"{h.likely.low_pct:.0f}–{h.likely.high_pct:.0f}%" for h in rows],
        "At max bulk": [f"{h.bulkiest.low_pct:.0f}–{h.bulkiest.high_pct:.0f}%" for h in rows],
        "Hits to KO": [h.hits_to_ko if h.hits_to_ko else "—" for h in rows],
        "Certainty": [h.certainty for h in rows],
    })

    def shade(_: pd.DataFrame) -> pd.DataFrame:
        css = pd.DataFrame("", index=view.index, columns=view.columns)
        for i, h in enumerate(rows):
            if h.certainty == ALWAYS:
                css.iloc[i, view.columns.get_loc("Certainty")] = (
                    f"background-color: {GOOD_STRONG}; color: #ffffff")
            elif h.certainty == LIKELY:
                css.iloc[i, view.columns.get_loc("Certainty")] = (
                    f"background-color: {GOOD_SOFT}; color: #14532d")
        return css

    st.dataframe(
        view.style.apply(shade, axis=None), hide_index=True, width="stretch",
        column_config={
            "": st.column_config.ImageColumn(),
            "Common build": st.column_config.TextColumn(
                help="Against the meta's modal defensive spread and nature"),
            "At max bulk": st.column_config.TextColumn(
                help="Against 32 HP / 32 in that defence with a boosting nature"),
            "Certainty": st.column_config.TextColumn(
                help="Always = KOs through any legal build. Usually = KOs the common "
                     "build only."),
        },
    )
    st.caption(
        "Your side is exact — nature, investment, item and moves from your paste. "
        "Theirs is the meta's common build, so their held item is the one most "
        "people bring. Resist berries, terrain seeds and Focus Sash are modelled. "
        "Same exclusions as everywhere: no crits, no burn, no screens, no sand or "
        "snow; abilities that scale damage go through the stage sliders."
    )
