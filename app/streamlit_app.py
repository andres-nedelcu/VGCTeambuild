"""VGC Teambuilding dashboard. Read-only: all writes go through scripts/."""

import time

import pandas as pd
import streamlit as st

from components.coverage_grid import render_coverage_grid
from components.defense_grid import render_defense_grid
from components.speed_view import render_speed_tiers, render_team_speeds
from vgc import regulations
from vgc.db import load_settings, warehouse_path
from vgc.defense import defense_matrix, flagged_types, mega_comparison, summarize
from vgc.megas import load_dex, mega_options, resolve_team
from vgc.offense import attackers, coverage_matrix, holes, team_best, threats
from vgc.speed import meta_speed, team_speeds
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

tab_defense, tab_coverage, tab_speed = st.tabs(
    ["Defensive grid", "Offensive coverage", "Speed tiers"])

with tab_defense:
    st.subheader("Defensive type grid")
    st.caption("Type chart plus type-changing abilities (immunities and resistances only). "
               "Static data, so the grid is the same across regulations.")
    if flags:
        st.warning("Flagged: " + ", ".join(flags) + " (3+ weak, nothing resists)")
    else:
        st.success("No flagged types")

    render_defense_grid(matrix, summary, flags)

    comparison = mega_comparison(team, slots)
    if len(comparison) > 1:
        st.subheader("Mega options compared")
        st.caption("Totals across the selected Pokémon. Δ is versus No Mega: "
                   "negative Δ Weak and positive Δ Resist/Immune are better.")
        st.dataframe(comparison, hide_index=True, width="stretch")

    with st.expander("Formes and abilities used"):
        st.dataframe(pd.DataFrame([
            {"slot": f.slot, "forme": f.display_name, "types": " / ".join(f.types),
             "ability": f.ability_id, "mega": "Yes" if f.is_mega else ""}
            for f in formes
        ]), hide_index=True, width="stretch")

with tab_coverage:
    st.subheader("Offensive coverage vs the meta")
    try:
        top_n = st.slider("Threats shown", 10, 40,
                          int(load_settings()["defaults"]["top_n"]), step=5,
                          key=f"cover_top_{paste_id}")
        meta = threats(reg, top_n)
        cover = coverage_matrix(attackers(team, formes), meta)
        gaps = holes(cover)
        if gaps:
            st.warning(f"No super effective answer to {len(gaps)} of {top_n}: "
                       + ", ".join(gaps))
        else:
            st.success(f"Something on the team hits all {top_n} threats super effectively")
        render_coverage_grid(cover, team_best(cover),
                             {t.display_name: t.usage_pct for t in meta})
    except LookupError as e:
        st.warning(str(e))

with tab_speed:
    st.subheader("Your Speed")
    speeds = team_speeds(team, formes)
    render_team_speeds(speeds)

    st.subheader("Meta Speed tiers")
    try:
        default_top = int(load_settings()["defaults"]["top_n"])
        left, right = st.columns([2, 1])
        by_slot = {s.slot: s for s in speeds}
        fastest = max(speeds, key=lambda s: s.speed).slot
        ref_slot = left.selectbox(
            "Compare against", list(by_slot), index=list(by_slot).index(fastest),
            format_func=lambda s: f"{by_slot[s].display_name} ({by_slot[s].speed})",
            key=f"speed_ref_{paste_id}_{mega_slot}",  # Mega changes the label, not the slot
        )
        top_n = right.slider("Threats shown", 10, 60, default_top, step=5)
        render_speed_tiers(meta_speed(reg, top_n), by_slot[ref_slot])
    except LookupError as e:
        st.warning(str(e))

st.caption(f"Rendered in {time.perf_counter() - t0:.2f}s")
