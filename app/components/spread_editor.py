"""Spread editor: set SP and natures in the app, without writing to the warehouse.

Ordering note, because it is the one tricky part. Streamlit runs the script top to
bottom, and the visuals are built before the tabs render — so the edits cannot simply
be read from the widgets' return values. Instead `stored_spreads` reads them out of
`st.session_state` by key early in the run, and the widgets below render with those
same keys. Streamlit persists a widget's value by key across reruns, so an edit
lands, triggers a rerun, and is picked up by the early read on the way through.
"""

from __future__ import annotations

import streamlit as st

from vgc.edit import ALL_NATURES, LABELS, Spread, problem, read_spread
from vgc.sprites import data_uri
from vgc.stats import SP_MAX_PER_STAT, SP_MAX_TOTAL, STATS, calc_stat, nature_mod


def _sp_key(paste_id: str, slot: int, stat: str) -> str:
    return f"sp_{paste_id}_{slot}_{stat}"


def _nature_key(paste_id: str, slot: int) -> str:
    return f"nat_{paste_id}_{slot}"


def stored_spreads(paste_id: str, team) -> dict[int, Spread]:
    """Read edits out of session state. Call this BEFORE building the visuals."""
    out = {}
    for member in team:
        base = read_spread(member)
        sp = {s: int(st.session_state.get(_sp_key(paste_id, member.slot, s), base.sp[s]))
              for s in STATS}
        nature = st.session_state.get(_nature_key(paste_id, member.slot), base.nature)
        out[member.slot] = Spread(nature, sp)
    return out


def render_editor(paste_id: str, team, formes, spreads: dict[int, Spread]) -> None:
    st.caption(
        f"{SP_MAX_PER_STAT} SP per stat, {SP_MAX_TOTAL} total. Edits apply to every "
        "tab immediately and are **not** saved to the warehouse — copy the export "
        "below if you want to keep a spread past a browser refresh."
    )
    by_slot = {f.slot: f for f in formes}
    base = {m.slot: m for m in team}

    for member in sorted(team, key=lambda m: m.slot):
        forme = by_slot.get(member.slot)
        spread = spreads[member.slot]
        err = problem(spread)

        head, natcol = st.columns([2, 2])
        with head:
            img, name = st.columns([1, 4])
            if forme is not None:
                uri = data_uri(forme.forme_id)
                if uri:
                    img.image(uri, width=44)
            name.markdown(f"**{forme.display_name if forme else member.pokemon_id}**")
        # None is a real option: a team locked in the game arrives without natures,
        # and defaulting the box to the first entry would silently apply Adamant.
        options = (None, *ALL_NATURES)
        current = spread.nature.lower() if spread.nature else None
        natcol.selectbox(
            "Nature", options,
            index=options.index(current) if current in options else 0,
            key=_nature_key(paste_id, member.slot),
            format_func=lambda n: "— no nature —" if n is None else n.title(),
            label_visibility="collapsed")

        cols = st.columns(6)
        for col, stat in zip(cols, STATS):
            col.number_input(
                LABELS[stat], min_value=0, max_value=SP_MAX_PER_STAT, step=1,
                value=spread.sp[stat], key=_sp_key(paste_id, member.slot, stat))

        if err:
            st.error(err)
        else:
            st.caption(_stat_line(forme, spread) +
                       f"  ·  {spread.remaining} SP left")
        st.divider()


def _stat_line(forme, spread: Spread) -> str:
    """The resulting stat line, so the cost of a choice is visible as it is made."""
    if forme is None:
        return ""
    from vgc.db import session
    with session() as con:
        row = con.execute(
            'select hp, atk, "def", spa, spd, spe from dim_pokemon where pokemon_id = ?',
            [forme.forme_id]).fetchone()
    if not row:
        return ""
    parts = []
    for base, stat in zip(row, STATS):
        value = calc_stat(base, spread.sp[stat],
                          nature_mod(spread.nature, stat), stat=stat)
        parts.append(f"{LABELS[stat]} {value}")
    return " · ".join(parts)


def render_export(text: str) -> None:
    st.markdown("**Export**")
    st.caption("Showdown format, readable by `scripts/load_paste.py` and pokepast.es. "
               "Paste it into a note to keep a spread you like.")
    st.code(text, language="text")
