"""VGC Teambuilding dashboard. Read-only: all writes go through scripts/."""

import time

import pandas as pd
import streamlit as st

from components.cores_view import (render_combos, render_cores, render_item_cores,
                                  render_partners, render_suggestions, render_swaps,
                                  render_uniques)
from components.dex_view import render_dex
from components.damage_grid import (render_damage_grid, render_focus,
                                    render_incoming_table)
from components.outgoing_grid import render_outgoing_grid, render_outgoing_table
from components.spread_editor import render_editor, render_export, stored_spreads
from components.team_manager import (render_delete, render_import, render_save)
from components.roster import clear as clear_roster
from components.roster import is_edited as roster_is_edited
from components.roster import pending as pending_roster
from components.roster import render_add, render_member
from components.coverage_grid import render_coverage_grid
from components.defense_grid import render_defense_grid
from components.speed_view import render_speed_tiers, render_team_speeds
from components.threat_list import render_threat_list
from vgc import regulations
from vgc.cores import cores as meta_cores
from vgc.cores import combos, item_cores, min_support, partners
from vgc.db import load_settings, warehouse_path
from vgc.defense import defense_matrix, flagged_types, mega_comparison, summarize
from vgc.freshness import sources as data_sources
from vgc.megas import load_dex, mega_options, resolve_team
from vgc.metafilter import TEAMS, THIN_SAMPLE, WINS, MetaFilter, extent, sample_size
from vgc.offense import attackers, coverage_matrix, holes, team_best, threats
from vgc.pressure import rank as rank_threats
from vgc.speed import TAILWIND_OPTIONS, Field, meta_speed, team_speeds
from vgc.damage import ELECTRIC_T, GRASSY, PSYCHIC_T, RAIN, SUN
from vgc.edit import apply as apply_spreads
from vgc.edit import read_spread, to_paste
from vgc.incoming import TIERS, against, incoming
from vgc.outgoing import outgoing
from vgc.suggest import suggestions
from vgc.swap import sole_coverage, swaps
from vgc.sprites import data_uri as sprite_data_uri
from vgc.team import list_teams, load_team

LOAD_CMD = "uv run python scripts/load_paste.py <pokepaste-url>"
REFRESH_CMD = "uv run python scripts/refresh.py"
NO_MEGA = 0  # radio sentinel; Streamlit treats None as 'no selection'
# Days of landed events above which the date filter is worth reaching for rather
# than noted as inert. Two weeks is roughly where this meta last took to turn over.
DATE_FILTER_BITES_DAYS = 14

# Two ways of using the tool, not two more tabs. The seven tabs are all facets of one
# question — how does *my team* line up — and the dex view is a different question
# entirely, so making it an eighth peer would have deepened the clutter Andres has
# already flagged on "What to add" rather than paying for itself. A mode switch also
# leaves the tab set free to be reorganised without touching this.
MY_TEAM, DEX = "My team", "Dex"

st.set_page_config(page_title="VGC Teambuilding", page_icon="⚔️", layout="wide")
t0 = time.perf_counter()

try:
    teams = list_teams()
    dex = load_dex()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

with st.sidebar:
    st.header("Team")
    if not teams:
        st.info("No teams yet. Import one below, or from the repo root run:")
        st.code(LOAD_CMD, language="bash")

    labels = {
        t.id: f"{t.name} · " + " / ".join(dex[p].display_name for p in t.pokemon_ids)
        + (" ↳variant" if t.derived_from else "")
        for t in teams
    }
    team_id = st.selectbox("Team", list(labels), format_func=labels.get) if teams else None

    with st.expander("Manage teams"):
        render_import(dex)
        if team_id:
            render_delete(team_id, labels[team_id])

    if not team_id:
        st.stop()

    saved_members = load_team(team_id)
    # Roster edits (who is on the team, what they hold) and spread edits both live in
    # session state and both land with the same Save, so the team is only ever in one
    # of two states: as saved, or as edited this session. Roster first — a spread is
    # read per slot, so the slots have to be settled before spreads are looked up.
    loaded = pending_roster(team_id, saved_members)
    spread_edits = stored_spreads(team_id, loaded)
    team = apply_spreads(loaded, spread_edits)
    roster_edited = roster_is_edited(team_id, saved_members)
    # Compare parsed spreads: apply() turns the stored JSON string into a dict, so
    # comparing `investment` directly reports every member as edited on first load.
    _before = {m.slot: read_spread(m) for m in loaded}
    edited = [m.slot for m in team if read_spread(m) != _before[m.slot]]
    names = {m.slot: dex[m.pokemon_id].display_name for m in team}
    all_slots = [m.slot for m in team]
    slots = st.multiselect(
        "Pokémon", all_slots, default=all_slots,
        format_func=lambda s: names[s], key=f"slots_{team_id}",
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
        # Derived from the landed extent rather than asserted. The previous copy here
        # claimed the events "span barely a week", which was true when it was written
        # and silently stopped being true as events accumulated -- telling the reader a
        # control was inert at exactly the point it became the most useful one.
        if span.days >= DATE_FILTER_BITES_DAYS:
            st.caption(f"**Events from** is worth reaching for now: the landed events "
                       f"span {span.days} days and the meta has moved inside that "
                       f"window, so an unfiltered view averages across the change. "
                       f"**Minimum event size** still separates less — the largest "
                       f"community events here are not majors.")
        else:
            st.caption(f"Both of these work, but the landed events span only "
                       f"{span.days} days and none of them are majors, so neither "
                       f"separates much yet.")
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
        key=f"mega_{team_id}",
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

if edited:
    st.info(f"Showing edited spreads for {len(edited)} Pokémon — session only, not "
            "saved. The Spreads tab has an export you can copy.")
st.caption(f"Meta: {meta_filter.label()} · {teams_counted:,} teams")

mode = st.segmented_control(
    "View", [MY_TEAM, DEX], default=MY_TEAM, key="view_mode",
    label_visibility="collapsed",
    help="**My team** is every tab below — how the loaded paste lines up against the "
         "meta. **Dex** is one Pokémon at a time: look anything up and calculate "
         "against it.")

if teams_counted == 0:
    st.error("No tournament teams match these meta filters. Widen them in the sidebar.")
    if mode == MY_TEAM:
        st.stop()
elif teams_counted < THIN_SAMPLE:
    st.warning(
        f"{teams_counted:,} teams is a thin sample — the unfiltered regulation has "
        f"{sample_size(reg):,}. Treat the order as indicative: which names appear "
        "matters more than where they sit.")

if mode == DEX:
    # st.stop() ends the whole script run, which is exactly what is wanted here and
    # is the opposite of the trap it was inside the Damage tab: nothing below this
    # should be built. The footer is repeated rather than reindenting every tab.
    render_dex(reg, meta_filter, team,
               [f for f in resolve_team(team, mega_slot) if f.slot in slots])
    st.caption(f"Rendered in {time.perf_counter() - t0:.2f}s")
    st.stop()

if not team:
    # An empty team is a legitimate starting point now, so this is a build prompt
    # rather than an error. Every visual below reads a move list, so there is nothing
    # to show until there is at least one Pokémon.
    st.subheader("Start building")
    st.caption(f"**{labels[team_id].split(' · ')[0]}** has no Pokémon yet. Add one "
               "to bring the rest of the tool to life — it will arrive with the "
               "meta's most common build, which you can edit from there.")
    render_add(team_id, team, reg, meta_filter)
    st.caption(f"Rendered in {time.perf_counter() - t0:.2f}s")
    st.stop()

if not slots:
    st.info("Select at least one Pokémon.")
    st.stop()

formes = [f for f in resolve_team(team, mega_slot) if f.slot in slots]
matrix = defense_matrix(formes)
summary = summarize(matrix)
flags = flagged_types(summary)

(tab_spreads, tab_defense, tab_coverage, tab_speed, tab_threats, tab_damage,
 tab_cores) = st.tabs(["Spreads", "Defensive grid", "Offensive coverage",
                       "Speed tiers", "Threat list", "Damage", "What to add"])

with tab_spreads:
    st.subheader("Set SP and natures")
    render_editor(team_id, loaded, resolve_team(team, mega_slot), spread_edits)

    with st.expander("Change who is on the team, and what they hold"):
        st.caption("Item, ability and moves per slot, plus adding and removing "
                   "Pokémon. These are held for this session like spreads are, and "
                   "land with the same Save below.")
        for member in sorted(team, key=lambda m: m.slot):
            st.markdown(f"**{dex[member.pokemon_id].display_name}**")
            render_member(team_id, member, dex.get(member.pokemon_id), reg,
                          meta_filter, team)
            st.divider()
        render_add(team_id, team, reg, meta_filter)

    render_save(team_id, team, edited, roster_edited)
    render_export(to_paste(team))

with tab_defense:
    st.subheader("Defensive type grid")
    st.caption("Type chart plus type-changing abilities (immunities and resistances only). "
               "Static data, so the grid is the same across regulations.")
    if flags:
        st.warning("Flagged: " + ", ".join(flags) + " (3+ weak, nothing resists)")
    else:
        st.success("No flagged types")

    render_defense_grid(matrix, summary, flags,
                        {f.display_name: sprite_data_uri(f.forme_id) for f in formes})

    comparison = mega_comparison(team, slots)
    if len(comparison) > 1:
        st.subheader("Mega options compared")
        st.caption("Totals across the selected Pokémon. Δ is versus No Mega: "
                   "negative Δ Weak and positive Δ Resist/Immune are better.")
        st.dataframe(comparison, hide_index=True, width="stretch")

    with st.expander("Formes and abilities used"):
        st.dataframe(pd.DataFrame([
            {"sprite": sprite_data_uri(f.forme_id),
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
                          key=f"cover_top_{team_id}")
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
                             {t.display_name: sprite_data_uri(t.forme_id) for t in meta},
                             {f.display_name: sprite_data_uri(f.forme_id) for f in formes})
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
            key=f"speed_ref_{team_id}_{mega_slot}",  # Mega changes the label, not the slot
        )
        tailwind = tw_col.selectbox(
            "Tailwind", TAILWIND_OPTIONS, format_func=str.title, key=f"speed_tw_{team_id}",
        )
        trick_room = tr_col.checkbox("Trick Room", key=f"speed_tr_{team_id}")
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
                             key=f"threat_top_{team_id}")
        render_threat_list(rank_threats(reg, formes, threat_n, meta_filter), len(formes),
                           {f.display_name: sprite_data_uri(f.forme_id) for f in formes})
    except LookupError as e:
        st.warning(str(e))

with tab_damage:
    st.subheader("What actually KOs you")
    st.caption("The threat list ranks by type pressure and says so — it ignores base "
               "power, stats, bulk and items. This answers what that leaves open: "
               "whether the hit actually kills.")
    try:
        left, mid, right = st.columns([1, 1, 2])
        weather = left.selectbox(
            "Weather", [None, RAIN, SUN],
            format_func=lambda w: {None: "None", RAIN: "Rain", SUN: "Sun"}[w],
            key=f"dmg_weather_{team_id}",
            help="Rain halves Fire damage and boosts Water; Sun is the mirror. It is "
                 "often the whole story — rain turns a 4x Fire hit into 2x.")
        terrain = mid.selectbox(
            "Terrain", [None, GRASSY, PSYCHIC_T, ELECTRIC_T],
            format_func=lambda t: {None: "None", GRASSY: "Grassy",
                                   PSYCHIC_T: "Psychic", ELECTRIC_T: "Electric"}[t],
            key=f"dmg_terrain_{team_id}",
            help="Boosts the matching type by 5325/4096 for a grounded attacker, and "
                 "Grassy halves Earthquake. Assumes both sides are grounded.")
        dmg_n = right.slider("Threats shown", 10, 30,
                             int(load_settings()["defaults"]["top_n"]), step=5,
                             key=f"dmg_top_{team_id}")
        acol, dcol = st.columns(2)
        atk_stage = acol.slider(
            "Their attack stage", -6, 6, 0, key=f"dmg_atk_{team_id}",
            help="How this models abilities instead of hardcoding them: Intimidate "
                 "is -1, Swords Dance or Nasty Plot is +2.")
        def_stage = dcol.slider(
            "Your defence stage", -6, 6, 0, key=f"dmg_def_{team_id}",
            help="Stamina is +1 per hit taken; screens are not modelled, so this is "
                 "also the honest way to approximate one.")
        direction = st.radio(
            "Direction", ["What hits me", "What I hit"], horizontal=True,
            key=f"dmg_dir_{team_id}",
            help="The stage sliders read from the attacker's side either way: on "
                 "'What I hit' they are your boosts and their defence.")

        if direction == "What I hit":
            out = outgoing(reg, team, formes, meta_filter, dmg_n, weather,
                           atk_stage, def_stage, terrain)
            if not out:
                st.warning("No threats at this filter.")
            else:
                render_outgoing_grid(out, [(f.display_name, f.forme_id) for f in formes])
                certain = [h for h in out if h.always_kos]
                if certain:
                    st.success(f"{len(certain)} of {len(out)} matchups KO in one hit "
                               "no matter what they invested.")
                names = {f.slot: f.display_name for f in formes}
                st.subheader("One attacker, one move")
                pcol, mcol = st.columns([1, 1])
                pick = pcol.selectbox(
                    "Attacker", [f.slot for f in formes],
                    format_func=lambda s: names[s], key=f"out_focus_{team_id}")

                every = outgoing(reg, team, formes, meta_filter, dmg_n, weather,
                                 atk_stage, def_stage, terrain, per_move=True)
                mine = [h for h in every if h.attacker_slot == pick]
                move_names = list(dict.fromkeys(h.likely.move_name for h in mine))
                if not move_names:
                    st.info(f"{names[pick]} has no damaging move.")
                else:
                    move = mcol.selectbox("Move", move_names,
                                          key=f"out_move_{team_id}_{pick}")
                    render_outgoing_table(
                        sorted([h for h in mine if h.likely.move_name == move],
                               key=lambda h: h.bulkiest.low_pct, reverse=True))

        # st.stop() would end the whole script run, not this tab, and the tabs below
        # would never be built — so the incoming path is an else, not a fallthrough.
        elif not (hits := incoming(reg, team, formes, meta_filter, dmg_n, weather,
                                   atk_stage, def_stage, terrain)):
            st.warning("No threats at this filter.")
        else:
            order = [(f.display_name, f.forme_id) for f in formes]
            render_damage_grid(hits, order)

            killers = [h for h in hits if h.kos]
            if killers:
                st.warning(f"{len(killers)} of {len(hits)} matchups are a guaranteed "
                           "KO at the worst case.")
            st.subheader("One Pokémon at a time")
            st.caption("The grid shows the shape; this answers the question you ask "
                       "in a game — can I leave this one in?")
            worst_slot = hits[0].target_slot
            slots = [f.slot for f in formes]
            names = {f.slot: f.display_name for f in formes}
            fcol, tcol = st.columns([1, 2])
            focus = fcol.selectbox(
                "Pokémon", slots, index=slots.index(worst_slot),
                format_func=lambda s: names[s], key=f"dmg_focus_{team_id}")
            show = tcol.multiselect(
                "Show", list(TIERS), default=[TIERS[0], TIERS[1]],
                key=f"dmg_tiers_{team_id}",
                help="Defaults to the brackets that change a decision. Add the rest "
                     "to see what this Pokémon can safely come in on.")
            render_focus(against(hits, focus), names[focus], show)

            with st.expander("Every matchup, hardest first"):
                render_incoming_table(hits[:60])
    except LookupError as e:
        st.warning(str(e))

with tab_cores:
    try:
        add_n = st.slider("Meta considered", 10, 40,
                          int(load_settings()["defaults"]["top_n"]), step=5,
                          key=f"add_top_{team_id}",
                          help="Both the candidate pool and the holes being fixed come "
                               "from this many threats.")
        meta_for_gaps = threats(reg, add_n, meta_filter)
        gaps = holes(coverage_matrix(attackers(team, formes), meta_for_gaps))

        ADD_ONLY, ANY_SLOT = "add", "any"
        slot_names = {f.slot: f.display_name for f in formes}
        mode = st.selectbox(
            "Replace", [ANY_SLOT, ADD_ONLY, *sorted(slot_names)],
            format_func=lambda m: {ANY_SLOT: "Best swap — consider every slot",
                                   ADD_ONLY: "Nothing — show additions for a free slot"
                                   }.get(m, f"Swap out {slot_names.get(m, m)}"),
            key=f"swap_mode_{team_id}",
            help="A full team has no free slot, so an addition is really a swap — and "
                 "whoever leaves takes their coverage with them.")

        if mode == ADD_ONLY:
            st.subheader("Candidates for a free slot")
            render_suggestions(suggestions(reg, team, formes, meta_filter, add_n),
                               gaps, flags)
        else:
            st.subheader("What you would lose by removing each Pokémon")
            sole = sole_coverage(reg, team, formes, meta_filter, add_n)
            render_uniques([(f.forme_id, f.display_name, sole.get(f.slot, ()))
                            for f in formes])

            st.subheader("Swaps")
            picked = None if mode == ANY_SLOT else int(mode)
            render_swaps(swaps(reg, team, formes, meta_filter, add_n, picked),
                         gaps, flags)

        floor = min_support(reg, meta_filter)
        st.subheader("What the meta pairs together")
        st.caption("Co-occurrence across tournament teams. Read **Lift**, not Share: "
                   "Rillaboom is on over half of all teams, so almost everything pairs "
                   "with it at a high share. Lift divides that out. A lift near 1 is "
                   "usually chance — but check the item view below before concluding "
                   "that, because a species with two opposing builds cancels itself "
                   f"out here. Pairs need at least {floor} teams at this filter.")

        st.markdown("**Partners for this team**")
        render_partners(partners(reg, [m.pokemon_id for m in team], meta_filter))

        st.markdown("**The meta's strongest cores**")
        render_cores(meta_cores(reg, meta_filter).head(25))

        st.markdown("**What you will face together**")
        st.caption("The three-Pokémon combinations people actually bring. Good for "
                   "drafting a plan against a field rather than a single threat.")
        only_mine = st.checkbox(
            "Only combinations involving my team", key=f"combo_mine_{team_id}",
            help="Shows what the meta pairs your own picks with.")
        render_combos(combos(reg, meta_filter, 20,
                             [m.pokemon_id for m in team] if only_mine else None))

        st.markdown("**Builds that choose their own partner**")
        st.caption("Where the item a Pokémon holds decides who it is brought with. "
                   "These partnerships are invisible above, because averaging a "
                   "species' builds together hides them.")
        mine_ids = [m.pokemon_id for m in team]
        yours = item_cores(reg, meta_filter, holders=mine_ids)
        if not yours.empty:
            st.caption("**On this team:**")
            render_item_cores(yours.head(10))
            st.caption("**Across the meta:**")
        render_item_cores(item_cores(reg, meta_filter).head(15))
    except LookupError as e:
        st.warning(str(e))

st.caption(f"Rendered in {time.perf_counter() - t0:.2f}s")
