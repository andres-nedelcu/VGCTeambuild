"""Who is on the team, and what they hold: add, remove, item, ability, moves.

Roster edits are held in `st.session_state` exactly like spread edits, and land with
the same Save button. The alternative — writing structural changes straight to the
file while spreads waited for Save — was rejected because it splits one team across
two save models: change an item, hit "Save as variant", and the item change is
already on the parent. One pending team, one Save.

MOVE LEGALITY IS NOT CHECKED, and the caption says so. There is no learnset in the
warehouse: `scripts/export_showdown.js` exports species, moves, items, abilities,
typechart and natures, and `vendor/pokemon-showdown/data/learnsets.ts` is sitting
right there unexported. Until it is, the picker defaults to the moves the species is
*actually seen running in the meta*, which are legal by construction because real
players brought them. The full move list is behind a toggle, labelled.
"""

from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from vgc.db import session
from vgc.dex import (ITEM, MOVE, ability_names, meta_build, picker_order, profile)
from vgc.team import MAX_SLOTS, Member

NO_ITEM = ""
MAX_MOVES = 4


def _key(team_id: str) -> str:
    return f"roster_{team_id}"


def pending(team_id: str, saved: list[Member]) -> list[Member]:
    """The roster as edited this session, or the saved one if untouched."""
    held = st.session_state.get(_key(team_id))
    if held is None:
        return list(saved)
    return [Member(**m) for m in held]


def _store(team_id: str, members: list[Member]) -> None:
    st.session_state[_key(team_id)] = [asdict(m)
                                       for m in sorted(members, key=lambda m: m.slot)]


def clear(team_id: str) -> None:
    """Forget roster edits — after a save, or when they are abandoned."""
    st.session_state.pop(_key(team_id), None)


def is_edited(team_id: str, saved: list[Member]) -> bool:
    held = st.session_state.get(_key(team_id))
    return held is not None and held != [asdict(m) for m in
                                         sorted(saved, key=lambda m: m.slot)]


@st.cache_data(show_spinner=False)
def _item_names() -> dict[str, str]:
    with session() as con:
        return dict(con.execute(
            "select item_id, display_name from dim_item order by display_name").fetchall())


@st.cache_data(show_spinner=False)
def _move_names() -> dict[str, str]:
    with session() as con:
        return dict(con.execute(
            "select move_id, display_name from dim_move order by display_name").fetchall())


def _free_slot(members: list[Member]) -> int:
    """Lowest unused slot, so removing the third and adding one does not make a
    slot 7 — slots are identity, but they are also what the user reads."""
    used = {m.slot for m in members}
    return next(n for n in range(1, MAX_SLOTS + 1) if n not in used)


def _seeded(pokemon_id: str, slot: int, reg: str, filt) -> Member:
    """A new member, seeded from the meta's most common build where there is one.

    A blank Pokémon with no moves is useless to every visual in the app — coverage,
    damage and pressure all read the move list — so adding one should produce a
    build that already works and can be edited from there.
    """
    try:
        build = meta_build(pokemon_id, reg, filt)
    except (LookupError, KeyError):
        return Member(slot=slot, pokemon_id=pokemon_id, item_id=None,
                      ability_id=None, investment={"unit": "sp", "values": {}})
    return Member(
        slot=slot, pokemon_id=pokemon_id, item_id=build.item_id or None,
        ability_id=build.ability_id, nature=build.nature,
        investment={"unit": "sp", "values": {k: v for k, v in build.sp.items() if v}},
        moves=list(build.moves),
    )


def render_add(team_id: str, members: list[Member], reg: str, filt) -> None:
    if len(members) >= MAX_SLOTS:
        st.caption(f"Six Pokémon is the limit — remove one to add another.")
        return
    entries = picker_order(reg, filt)
    names = {e.pokemon_id: e.display_name for e in entries}
    pick = st.selectbox(
        "Add a Pokémon", [e.pokemon_id for e in entries], format_func=names.get,
        key=f"add_pick_{team_id}", index=0,
        help="Ordered by usage, so the meta is at the top. Typing filters the whole "
             "dex.")
    if st.button("Add to team", key=f"add_go_{team_id}"):
        new = _seeded(pick, _free_slot(members), reg, filt)
        _store(team_id, [*members, new])
        st.rerun()


def render_member(team_id: str, member: Member, entry, reg: str, filt,
                  members: list[Member]) -> None:
    """Item, ability and moves for one slot, plus removal."""
    items, moves = _item_names(), _move_names()
    abilities = ability_names()

    try:
        prof = profile(member.pokemon_id, reg, filt)
    except (LookupError, KeyError):
        prof = None

    # Items this species is actually seen holding, then everything else. Same reason
    # as the dex picker: the list opens on what you are most likely to want.
    seen = [i for i, _pct in (prof.details.get(ITEM) or ())] if prof else []
    ordered = [i for i in seen if i in items] + [i for i in items if i not in seen]
    options = [NO_ITEM, *ordered]
    index = options.index(member.item_id) if member.item_id in options else 0

    icol, acol = st.columns(2)
    item = icol.selectbox(
        "Item", options, index=index, key=f"item_{team_id}_{member.slot}",
        format_func=lambda i: "— no item —" if i == NO_ITEM else items.get(i, i))

    # An explicit "— none —", exactly like the nature selector: a member with no
    # ability must not land on index 0 and have it silently applied. DECISIONS
    # 2026-09-19 records this bug for natures; reintroducing it one field over was
    # a near miss, caught by opening the app rather than by the suite.
    legal = list(entry.abilities) if entry else []
    a_options = legal if member.ability_id in legal else [None, *legal]
    a_index = a_options.index(member.ability_id) if member.ability_id in a_options else 0
    ability = acol.selectbox(
        "Ability", a_options, index=a_index,
        key=f"ability_{team_id}_{member.slot}",
        format_func=lambda a: abilities.get(a, a) if a else "— none —")

    run = [m for m, _pct in (prof.details.get(MOVE) or ())] if prof else []
    pool = [m for m in run if m in moves]
    if st.toggle("Show every move", key=f"allmoves_{team_id}_{member.slot}",
                 help="Legality is not checked — there is no learnset in the data, "
                      "so this list includes moves this Pokémon cannot learn."):
        pool = pool + [m for m in moves if m not in pool]
    for m in (member.moves or []):          # keep what is already set, always
        if m not in pool:
            pool.insert(0, m)

    picked = st.multiselect(
        "Moves", pool, default=[m for m in (member.moves or []) if m in pool],
        key=f"moves_{team_id}_{member.slot}", max_selections=MAX_MOVES,
        format_func=lambda m: moves.get(m, m))

    changed = (item or None) != member.item_id or ability != member.ability_id \
        or picked != (member.moves or [])
    if changed:
        updated = [m if m.slot != member.slot else
                   Member(**{**asdict(m), "item_id": item or None,
                             "ability_id": ability, "moves": list(picked)})
                   for m in members]
        _store(team_id, updated)
        st.rerun()

    if st.button("Remove from team", key=f"rm_{team_id}_{member.slot}"):
        _store(team_id, [m for m in members if m.slot != member.slot])
        st.rerun()
