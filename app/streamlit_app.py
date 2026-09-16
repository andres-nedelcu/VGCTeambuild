"""VGC Teambuilding dashboard. Read-only: all writes go through scripts/."""

import time

import pandas as pd
import streamlit as st

from components.defense_grid import render_defense_grid
from vgc import regulations
from vgc.db import warehouse_path
from vgc.defense import defense_matrix, flagged_types, summarize
from vgc.megas import load_dex, mega_options, resolve_team
from vgc.team import list_pastes, load_team

LOAD_CMD = "uv run python scripts/load_paste.py <pokepaste-url>"
NO_MEGA = 0  # radio sentinel; Streamlit treats None as 'no selection'

st.set_page_config(page_title="VGC Teambuilding", page_icon="⚔️", layout="wide")
t0 = time.perf_counter()

try:
    pastes = list_pastes()
    dex = load_dex()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

with st.sidebar:
    st.header("Team")
    if not pastes:
        st.info("No teams loaded yet. From the repo root, run:")
        st.code(LOAD_CMD, language="bash")
        st.stop()

    labels = {
        pid: f"{name or pid} · " + " / ".join(dex[p].display_name for p in mons)
        for pid, name, mons in pastes
    }
    paste_id = st.selectbox("Team", list(labels), format_func=labels.get)
    with st.expander("Add a new paste"):
        st.caption("The app is read-only. From the repo root, run:")
        st.code(LOAD_CMD, language="bash")
        st.caption("Then refresh this page.")

    team = load_team(paste_id)
    names = {m.slot: dex[m.pokemon_id].display_name for m in team}
    all_slots = [m.slot for m in team]
    slots = st.multiselect(
        "Pokémon", all_slots, default=all_slots,
        format_func=lambda s: f"{s}. {names[s]}", key=f"slots_{paste_id}",
    )

    regs = list(regulations.load()["regulations"])
    reg = st.selectbox("Regulation", regs, index=regs.index(regulations.current()))

    options = mega_options(team)
    choice = st.radio(
        "Mega Evolution", [NO_MEGA, *options],
        format_func=lambda s: "No Mega" if s == NO_MEGA
        else f"{names[s]} → {dex[options[s]].display_name}",
        key=f"mega_{paste_id}",
    )
    mega_slot = None if choice == NO_MEGA else choice

st.title("VGC Teambuilding Dashboard")
st.caption(f"Pokémon Champions VGC Doubles · Regulation {reg} · `{warehouse_path().name}`")

if not slots:
    st.info("Select at least one Pokémon.")
    st.stop()

formes = [f for f in resolve_team(team, mega_slot) if f.slot in slots]
matrix = defense_matrix(formes)
summary = summarize(matrix)
flags = flagged_types(summary)

st.subheader("Defensive type grid")
st.caption("Type chart plus type-changing abilities (immunities and resistances only). "
           "Static data, so the grid is the same across regulations.")
if flags:
    st.warning("Flagged: " + ", ".join(flags) + " (3+ weak, nothing resists)")
else:
    st.success("No flagged types")

render_defense_grid(matrix, summary, flags)

with st.expander("Formes and abilities used"):
    st.dataframe(pd.DataFrame([
        {"slot": f.slot, "forme": f.display_name, "types": " / ".join(f.types),
         "ability": f.ability_id, "mega": "Yes" if f.is_mega else ""}
        for f in formes
    ]), hide_index=True, width="stretch")

st.caption(f"Rendered in {time.perf_counter() - t0:.2f}s")
