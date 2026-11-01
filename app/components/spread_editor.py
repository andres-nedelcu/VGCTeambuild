"""Spread editor: set SP and natures in the app, without writing to the warehouse.

The controls themselves live in `components/build_panel`, because the dex view needs
the same three pieces — nature box, SP inputs, resulting stat line — around a
different layout. What is specific to this tab is the loop over team members, the
sprite beside each one, and the export.

Ordering note, because it is the one tricky part. Streamlit runs the script top to
bottom, and the visuals are built before the tabs render — so the edits cannot simply
be read from the widgets' return values. Instead `stored_spreads` reads them out of
`st.session_state` by key early in the run, and the widgets below render with those
same keys. Streamlit persists a widget's value by key across reruns, so an edit
lands, triggers a rerun, and is picked up by the early read on the way through.
"""

from __future__ import annotations

import streamlit as st

from components.build_panel import (caps_caption, render_feedback, render_nature,
                                    render_sp, stored_spread)
from vgc.edit import Spread, read_spread
from vgc.sprites import data_uri


def _prefix(team_id: str, slot: int) -> str:
    return f"{team_id}_{slot}"


def stored_spreads(team_id: str, team) -> dict[int, Spread]:
    """Read edits out of session state. Call this BEFORE building the visuals."""
    return {m.slot: stored_spread(_prefix(team_id, m.slot), read_spread(m))
            for m in team}


def render_editor(team_id: str, team, formes, spreads: dict[int, Spread]) -> None:
    st.caption(
        caps_caption() + " Edits apply to every tab immediately and are held for this "
        "session only — **Save** below keeps them, or **Save as variant** forks them "
        "into a second team so two spreads can be compared."
    )
    by_slot = {f.slot: f for f in formes}

    for member in sorted(team, key=lambda m: m.slot):
        forme = by_slot.get(member.slot)
        spread = spreads[member.slot]
        prefix = _prefix(team_id, member.slot)

        head, natcol = st.columns([2, 2])
        with head:
            img, name = st.columns([1, 4])
            if forme is not None:
                uri = data_uri(forme.forme_id)
                if uri:
                    img.image(uri, width=44)
            name.markdown(f"**{forme.display_name if forme else member.pokemon_id}**")
        render_nature(prefix, spread, natcol)
        render_sp(prefix, spread)
        render_feedback(forme.forme_id if forme else None, spread)
        st.divider()


def render_export(text: str) -> None:
    st.markdown("**Export**")
    st.caption("Showdown format, readable by `scripts/load_paste.py` and pokepast.es. "
               "Paste it into a note to keep a spread you like.")
    st.code(text, language="text")
