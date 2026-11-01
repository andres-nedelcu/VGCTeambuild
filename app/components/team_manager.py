"""Add and remove teams from inside the app.

This is the half of the tool that used to require the terminal. It is possible now
only because teams are files rather than warehouse rows — the app can write them
without taking the DuckDB writer lock that `refresh.py` needs.

Both routes here end at `vgc.team.validate`, the same check `scripts/load_paste.py`
runs, so a team the script would refuse cannot be saved from the UI either.

Pasting text is offered beside the URL deliberately: it needs no network, which
matters for a tool that is meant to work on a venue's wifi.
"""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

from components.roster import clear as clear_roster
from vgc.ingest import pokepaste
from vgc.team import (Team, delete, get, list_teams, members_from_sets, save,
                      unique_id, validate, variant_of)

URL, TEXT, EMPTY = "Paste link", "Paste text", "Start empty"


def _save(name: str, sets: list[dict], source: dict, dex) -> bool:
    """Validate and write. Returns True if the caller should rerun."""
    if not sets:
        st.error("Nothing to import — no Pokémon found in that paste.")
        return False

    members = members_from_sets(sets)
    unknown = [m.pokemon_id for m in members if m.pokemon_id not in dex]
    problems, warnings = validate(members)

    for w in warnings:
        st.caption(f"⚠︎ {w}")
    if problems:
        st.error("Not saved — these have to resolve first:")
        for p in problems:
            st.caption(f"• {p}")
        return False
    if unknown:
        st.error(f"Not saved — unknown species: {', '.join(unknown)}")
        return False

    # Re-importing the same paste replaces the team it made before rather than
    # stacking up near-duplicates; the paste id is the identity, the slug is the file.
    pid = source.get("paste_id")
    existing = next((t for t in list_teams() if pid and t.source.get("paste_id") == pid), None)
    team = save(Team(
        id=existing.id if existing else unique_id(name),
        name=name, members=members, source=source,
        created_at=existing.created_at if existing else None,
    ))
    st.success(f"{'Replaced' if existing else 'Saved'} “{team.name}” "
               f"({len(team.members)} Pokémon).")
    return True


def render_import(dex) -> None:
    st.markdown("**Add a team**")
    how = st.radio("How", [URL, TEXT, EMPTY], horizontal=True, key="import_how",
                   label_visibility="collapsed")

    if how == EMPTY:
        # Building from nothing is a first-class route, not a degenerate import: a
        # team invented in the Spreads tab never had a paste to come from.
        name = st.text_input("Name", key="import_empty_name", placeholder="required")
        st.caption("Creates an empty team. Add Pokémon from the Spreads tab.")
        if st.button("Create", key="import_empty_go", disabled=not name.strip()):
            team = save(Team(id=unique_id(name.strip()), name=name.strip(),
                             members=[], source={"kind": "scratch"}))
            st.success(f"Created “{team.name}”. Add Pokémon from the Spreads tab.")
            st.rerun()
        return

    if how == URL:
        url = st.text_input("PokePaste link", key="import_url",
                            placeholder="https://pokepast.es/0123456789abcdef")
        name = st.text_input("Name (optional)", key="import_url_name",
                             placeholder="defaults to the paste title")
        if st.button("Import", key="import_url_go", disabled=not url.strip()):
            try:
                pid, payload = pokepaste.fetch(url.strip())
                sets = pokepaste.parse(payload["paste"])
            except Exception as e:                      # network, 404, empty paste
                st.error(f"Could not fetch that paste: {e}")
                return
            source = {"kind": "pokepaste", "paste_id": pid,
                      "url": f"https://pokepast.es/{pid}",
                      "author": payload.get("author") or None}
            if _save(name.strip() or payload.get("title") or pid, sets, source, dex):
                st.rerun()
    else:
        text = st.text_area("Showdown export", key="import_text", height=160,
                            placeholder="Kingambit @ Chople Berry\nAbility: Defiant\n...")
        name = st.text_input("Name", key="import_text_name", placeholder="required")
        ready = bool(text.strip() and name.strip())
        if st.button("Import", key="import_text_go", disabled=not ready):
            try:
                sets = pokepaste.parse(text)
            except Exception as e:
                st.error(f"Could not read that paste: {e}")
                return
            if _save(name.strip(), sets, {"kind": "text"}, dex):
                st.rerun()


def render_save(team_id: str, members, edited: list[int],
                roster_edited: bool = False) -> None:
    """Persist in-session spread edits, or fork them into a variant.

    Editing stays in session state — that is what keeps the slider loop fast, and it
    was never the problem. The problem was that there was nowhere to put the result.
    Saving is therefore explicit, so trying something and backing out still costs
    nothing.

    Both buttons land the team at the top of the picker, because `list_teams` orders
    by modified time and the thing you just saved is the thing you want to look at.
    """
    if not edited and not roster_edited:
        st.caption("No unsaved changes.")
        return

    current = get(team_id)
    what = []
    if edited:
        what.append(f"{len(edited)} spread{'s' if len(edited) > 1 else ''}")
    if roster_edited:
        what.append("the roster")
    st.warning(f"Edited this session — {' and '.join(what)} — not saved yet.")
    keep, fork = st.columns(2)

    if keep.button("Save to this team", key=f"save_{team_id}", type="primary"):
        problems, _ = validate(members)
        if problems:
            st.error("Not saved: " + "; ".join(problems))
            return
        save(replace(current, members=list(members)))
        clear_roster(team_id)
        st.rerun()

    name = st.text_input("Variant name", key=f"variant_name_{team_id}",
                         placeholder=f"{current.name} (variant)")
    if fork.button("Save as variant", key=f"fork_{team_id}"):
        problems, _ = validate(members)
        if problems:
            st.error("Not saved: " + "; ".join(problems))
            return
        fresh = variant_of(current, name.strip() or None)
        save(replace(fresh, members=list(members)))
        clear_roster(team_id)
        st.rerun()


def render_delete(team_id: str, label: str) -> None:
    """Deleting a team deletes the only copy — data/teams/ is gitignored, so there
    is no history to recover it from. Hence the explicit gate."""
    st.markdown("**Remove this team**")
    st.caption(f"{label.split(' · ')[0]} — this cannot be undone.")
    sure = st.checkbox("Yes, delete it", key=f"del_sure_{team_id}")
    if st.button("Delete team", key=f"del_go_{team_id}", disabled=not sure, type="secondary"):
        delete(team_id)
        st.rerun()
