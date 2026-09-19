"""VGC Teambuilding dashboard. Read-only: all writes go through scripts/."""

import time

import pandas as pd
import streamlit as st

from components.coverage_grid import render_coverage_grid
from components.defense_grid import render_defense_grid
from components.speed_view import render_speed_tiers, render_team_speeds
from components.threat_list import render_threat_list
from vgc import regulations
from vgc.db import load_settings, warehouse_path
from vgc.defense import defense_matrix, flagged_types, mega_comparison, summarize
from vgc.freshness import sources as data_sources
from vgc.megas import load_dex, mega_options, resolve_team
from vgc.metafilter import TEAMS, THIN_SAMPLE, WINS, MetaFilter, extent, sample_size
from vgc.offense import attackers, coverage_matrix, holes, team_best, threats
from vgc.pressure import rank as rank_threats
from vgc.speed import TAILWIND_OPTIONS, Field, meta_speed, team_speeds
from vgc.sprites import data_uri as sprite_data_uri
from vgc.team import list_pastes, load_team

LOAD_CMD = "uv run python scripts/load_paste.py <pokepaste-url>"
REFRESH_CMD = "uv run python scripts/refresh.py"
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

    st.header("Meta")
    st.caption("Which tournament results count as the meta. Applies to all three "
               "meta tabs at once.")
    cut = st.selectbox(
        "Finishers counted", [None, 32, 16, 8],
        format_func=lambda c: "All finishers" if c is None else f"Top {c}",
        help="A top-cut view answers 'what did teams that finished well bring'. "
             "It is the sharpest filter here and the most expensive: the sample "
             "shrinks fast, so small moves inside a cut are noise.")
    weight = st.radio(
        "Weighting", [TEAMS, WINS],
        format_func=lambda w: "Every team equally" if w == TEAMS else "By match wins",
        help="Weighting by wins keeps every team but counts each by how much it won, "
             "so it is much steadier than a cut. Moves that show up under both are "
             "the ones worth trusting.")

    span = extent(reg)
    since = min_players = None
    with st.expander("More meta filters"):
        if span.events:
            st.caption(f"{span.events} events · {span.first} to {span.last} "
                       f"({span.days} days) · {span.smallest}–{span.largest} players")
        st.caption("Both of these work, but today's events span barely a week and "
                   "none of them are majors, so neither separates much yet.")
        if span.first and span.last and span.first < span.last:
            picked = st.date_input("Events from", value=span.first,
                                   min_value=span.first, max_value=span.last)
            since = None if picked == span.first else picked
        if span.smallest and span.largest and span.smallest < span.largest:
            picked = st.slider("Minimum event size", span.smallest, span.largest,
                               span.smallest)
            min_players = None if picked == span.smallest else picked

    meta_filter = MetaFilter(cut=cut, since=since, min_players=min_players, weight=weight)
    teams_counted = sample_size(reg, meta_filter)

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

feeds = data_sources(reg)
st.caption("Data: " + " · ".join(
    f"{s.name} {s.as_of} ({s.age_label()})" if s.as_of else s.name
    for s in feeds))
with st.expander("Data freshness"):
    st.dataframe(pd.DataFrame([
        {"Source": s.name, "As of": s.as_of, "Age": s.age_label(),
         "Loaded": s.loaded_at, "Detail": s.detail} for s in feeds
    ]), hide_index=True, width="stretch")
    st.caption(f"Refresh everything with `{REFRESH_CMD}`")

st.caption(f"Meta: {meta_filter.label()} · {teams_counted:,} teams")
if teams_counted == 0:
    st.error("No tournament teams match these meta filters. Widen them in the sidebar.")
    st.stop()
if teams_counted < THIN_SAMPLE:
    st.warning(
        f"{teams_counted:,} teams is a thin sample — the unfiltered regulation has "
        f"{sample_size(reg):,}. Treat the order as indicative: which names appear "
        "matters more than where they sit.")

if not slots:
    st.info("Select at least one Pokémon.")
    st.stop()

formes = [f for f in resolve_team(team, mega_slot) if f.slot in slots]
matrix = defense_matrix(formes)
summary = summarize(matrix)
flags = flagged_types(summary)

tab_defense, tab_coverage, tab_speed, tab_threats = st.tabs(
    ["Defensive grid", "Offensive coverage", "Speed tiers", "Threat list"])

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
            {"sprite": sprite_data_uri(f.forme_id), "slot": f.slot,
             "forme": f.display_name, "types": " / ".join(f.types),
             "ability": f.ability_id, "mega": "Yes" if f.is_mega else ""}
            for f in formes
        ]), hide_index=True, width="stretch",
            column_config={"sprite": st.column_config.ImageColumn()})

with tab_coverage:
    st.subheader("Offensive coverage vs the meta")
    try:
        top_n = st.slider("Threats shown", 10, 40,
                          int(load_settings()["defaults"]["top_n"]), step=5,
                          key=f"cover_top_{paste_id}")
        meta = threats(reg, top_n, meta_filter)
        cover = coverage_matrix(attackers(team, formes), meta)
        gaps = holes(cover)
        if gaps:
            st.warning(f"No super effective answer to {len(gaps)} of {top_n}: "
                       + ", ".join(gaps))
        else:
            st.success(f"Something on the team hits all {top_n} threats super effectively")
        render_coverage_grid(cover, team_best(cover),
                             {t.display_name: t.usage_pct for t in meta},
                             {t.display_name: sprite_data_uri(t.forme_id) for t in meta})
    except LookupError as e:
        st.warning(str(e))

with tab_speed:
    st.subheader("Your Speed")
    speeds = team_speeds(team, formes)
    render_team_speeds(speeds)

    st.subheader("Meta Speed tiers")
    try:
        default_top = int(load_settings()["defaults"]["top_n"])
        left, tw_col, tr_col, right = st.columns([2, 1, 1, 1])
        by_slot = {s.slot: s for s in speeds}
        fastest = max(speeds, key=lambda s: s.speed).slot
        ref_slot = left.selectbox(
            "Compare against", list(by_slot), index=list(by_slot).index(fastest),
            format_func=lambda s: f"{by_slot[s].display_name} ({by_slot[s].speed})",
            key=f"speed_ref_{paste_id}_{mega_slot}",  # Mega changes the label, not the slot
        )
        tailwind = tw_col.selectbox(
            "Tailwind", TAILWIND_OPTIONS, format_func=str.title, key=f"speed_tw_{paste_id}",
        )
        trick_room = tr_col.checkbox("Trick Room", key=f"speed_tr_{paste_id}")
        top_n = right.slider("Threats shown", 10, 60, default_top, step=5)
        field = Field(tailwind=tailwind, trick_room=trick_room)
        render_speed_tiers(meta_speed(reg, top_n, meta_filter), by_slot[ref_slot], field)
    except LookupError as e:
        st.warning(str(e))

with tab_threats:
    st.subheader("What threatens this team")
    try:
        threat_n = st.slider("Threats ranked", 10, 40,
                             int(load_settings()["defaults"]["top_n"]), step=5,
                             key=f"threat_top_{paste_id}")
        render_threat_list(rank_threats(reg, formes, threat_n, meta_filter), len(formes))
    except LookupError as e:
        st.warning(str(e))

st.caption(f"Rendered in {time.perf_counter() - t0:.2f}s")
