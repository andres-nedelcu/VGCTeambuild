"""The single-Pokémon view: pick anything in the dex, then calculate against it.

Every other page in this app is anchored to the loaded paste. That is the right
default and it is not what you want when an unfamiliar name is across from you and
the question is "what is that, and does it kill me". This page answers that, and it
is the direction the tool is heading: a damage calculator with search bars where you
can use all the settings.

Four parts, in the order you use them:

  PICK IT        394 legal entries, ordered so the picker opens on the meta.
  WHAT IT RUNS   usage, rank, and the item / ability / move / nature / spread
                 breakdowns. Presentation only — all of it is already in the marts.
  SET IT UP      the same nature and SP controls the Spreads tab uses, plus its item,
                 ability and a stat stage. Seeded with the meta's most common build,
                 and editable from there.
  CALCULATE      both directions against your team, or against a second Pokémon you
                 build the same way.

THE SEED IS A REAL SPREAD, not the per-stat modes `vgc.incoming` and `vgc.outgoing`
use. Those are marginals: correct for damage, where only one stat is read per hit,
and not a build anybody runs — Farigiraf's sum to 71 against a cap of 66. A panel
that shows six numbers together and lets you edit them has to start from something
legal, so it starts from the most common full spread. `vgc.dex.marginal_spread` has
the argument at length.

GREEN MEANS GOOD FOR ANDRES, so the two directions shade in opposite directions: a
KO is green when he lands it and red when he takes it.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.build_panel import (caps_caption, render_feedback, render_nature,
                                    render_sp, stored_spread)
from components.palette import FILL_BAD, FILL_CAUTION, FILL_GOOD, MUTED
from vgc.damage import ELECTRIC_T, GRASSY, PSYCHIC_T, RAIN, SUN
from vgc.db import session
from vgc.dex import (MOVE, ability_names, format_spread, meta_build, picker_order,
                     profile)
from vgc.edit import Spread
from vgc.matchup import (ATTACKER, DEFENDER, Build, damaging, move_data, team_builds,
                         versus, with_spread)
from vgc.sprites import data_uri
from vgc.stats import STATS

DETAIL_LABELS = {
    "item": "Items", "ability": "Abilities", "move": "Moves",
    "nature": "Natures", "spread": "Spreads",
}
TOP_ROWS = 8
NO_ITEM = ""


@st.cache_data(show_spinner=False)
def _item_names() -> dict[str, str]:
    with session() as con:
        return dict(con.execute(
            "select item_id, display_name from dim_item order by display_name").fetchall())


@st.cache_data(show_spinner=False)
def _move_names() -> dict[str, str]:
    return {mid: info[0] for mid, info in move_data().items()}


# --- part 1: pick it ------------------------------------------------------------

def _pick(reg: str, meta_filter, key: str, label: str, default: str | None = None):
    entries = picker_order(reg, meta_filter)
    ids = [e.pokemon_id for e in entries]
    names = {e.pokemon_id: e.display_name for e in entries}
    index = ids.index(default) if default in ids else 0
    return st.selectbox(label, ids, index=index, format_func=names.get, key=key)


# --- part 2: what the meta runs -------------------------------------------------

def _render_headline(prof) -> None:
    e = prof.entry
    uri = data_uri(e.pokemon_id)
    if uri:
        img, head = st.columns([1, 6])
        img.image(uri, width=88)
    else:
        # Sprites are cached for the meta only, so an off-meta pick has none. Dropping
        # the column entirely beats leaving a blank one the name is indented past.
        head = st.container()
    with head:
        st.subheader(e.display_name)
        st.caption(" / ".join(e.types) + f"  ·  BST {e.bst}")

    cols = st.columns(4)
    if prof.in_meta:
        cols[0].metric("Usage", f"{prof.usage_pct * 100:.1f}%")
        cols[1].metric("Rank", f"#{prof.rank}")
        cols[2].metric("Of", f"{prof.sample_size:,} teams")
    else:
        cols[0].metric("Usage", "—")
        cols[1].caption("Not in the tournament data for this meta filter. Its build "
                        "numbers below, if any, come from the ladder snapshot.")

    st.dataframe(
        pd.DataFrame([{k.upper(): v for k, v in e.base.items()}]),
        hide_index=True, width="stretch")


def _render_meta(prof) -> None:
    if not prof.has_builds():
        st.info("No build data for this Pokémon — nobody in the ladder snapshot has "
                "brought it. You can still set it up and calculate below.")
        return
    tabs = st.tabs([DETAIL_LABELS[d] for d in DETAIL_LABELS if prof.details.get(d)])
    present = [d for d in DETAIL_LABELS if prof.details.get(d)]
    for tab, detail in zip(tabs, present):
        rows = prof.details[detail][:TOP_ROWS]
        with tab:
            st.dataframe(
                pd.DataFrame({
                    DETAIL_LABELS[detail][:-1]: [_pretty(detail, v) for v, _ in rows],
                    "Share": [f"{pct * 100:.1f}%" for _, pct in rows],
                }), hide_index=True, width="stretch")
    st.caption(
        "Builds come from the Champions ladder snapshot, so they are what people run "
        "rather than what the player across from you brought — and unlike usage above, "
        "they do not move with the meta filter. Spreads are SP in HP/Atk/Def/SpA/SpD/Spe "
        "order."
    )


def _pretty(detail: str, value: str) -> str:
    if detail == "item":
        return _item_names().get(value, value)
    if detail == "move":
        return _move_names().get(value, value)
    if detail == "ability":
        return ability_names().get(value, value.title())
    if detail == "nature":
        return value.title()
    return value


# --- part 3: set it up ----------------------------------------------------------

def _render_build(prefix: str, seed: Build, prof, *, compact: bool = False) -> Build:
    """The build panel. Returns the Build the rest of the page should calculate with.

    Widget keys carry the Pokémon's id, so switching Pokémon reseeds every control
    from that one's common build rather than leaving the previous one's numbers
    behind — and switching back remembers what you had typed.
    """
    e = prof.entry
    items = _item_names()
    item_ids = [NO_ITEM, *items]
    abilities = list(e.abilities) or [None]

    icol, acol, ncol = st.columns([2, 2, 1.4])
    item = icol.selectbox(
        "Item", item_ids,
        index=item_ids.index(seed.item_id) if seed.item_id in item_ids else 0,
        format_func=lambda i: "— no item —" if i == NO_ITEM else items.get(i, i),
        key=f"item_{prefix}")
    ability = acol.selectbox(
        "Ability", abilities,
        index=abilities.index(seed.ability_id) if seed.ability_id in abilities else 0,
        format_func=lambda a: "— none —" if a is None else _pretty("ability", a),
        key=f"abil_{prefix}",
        help="Only abilities that change type effectiveness are modelled here. "
             "Damage-scaling ones go through the stage control instead.")
    with ncol:
        st.caption("Nature")
        render_nature(prefix, Spread(seed.nature, seed.sp))

    spread = stored_spread(prefix, Spread(seed.nature, seed.sp))
    render_sp(prefix, spread)
    err = render_feedback(e.pokemon_id, spread)
    if err:
        # Fall back to the seed rather than raising inside calc_stat halfway through
        # a render — the editor has already said loudly what is wrong.
        spread = Spread(seed.nature, seed.sp)

    observed = [v for v, _ in (prof.details.get(MOVE) or ())]
    known = _move_names()
    options = list(dict.fromkeys([*observed, *sorted(known, key=known.get)]))
    shares = {v: pct for v, pct in (prof.details.get(MOVE) or ())}
    moves = st.multiselect(
        "Moves", options,
        default=[m for m in seed.moves if m in options],
        format_func=lambda m: (f"{known.get(m, m)} — {shares[m] * 100:.0f}%"
                               if m in shares else known.get(m, m)),
        key=f"moves_{prefix}",
        help="The species' observed moves come first, with how often they are run; "
             "every other move in the game is below them.")
    if not compact:
        st.caption(caps_caption() + f"  Current spread: `{format_spread(spread.sp)}`. "
                   "Nothing here is written to the warehouse.")

    return Build(
        forme_id=e.pokemon_id, display_name=e.display_name, types=e.types,
        base=dict(e.base), ability_id=ability, item_id=item or None,
        nature=spread.nature, sp=dict(spread.sp), moves=tuple(moves))


# --- part 4: calculate ----------------------------------------------------------

def _field_controls(prefix: str):
    wcol, tcol = st.columns(2)
    weather = wcol.selectbox(
        "Weather", [None, RAIN, SUN],
        format_func=lambda w: {None: "None", RAIN: "Rain", SUN: "Sun"}[w],
        key=f"dexw_{prefix}",
        help="Rain halves Fire damage and boosts Water; Sun is the mirror.")
    terrain = tcol.selectbox(
        "Terrain", [None, GRASSY, PSYCHIC_T, ELECTRIC_T],
        format_func=lambda t: {None: "None", GRASSY: "Grassy", PSYCHIC_T: "Psychic",
                               ELECTRIC_T: "Electric"}[t],
        key=f"dext_{prefix}",
        help="Boosts the matching type for a grounded attacker, and Grassy halves "
             "Earthquake. Assumes both sides are grounded.")
    acol, dcol = st.columns(2)
    atk_stage = acol.slider(
        "Attacker's stage", -6, 6, 0, key=f"dexa_{prefix}",
        help="How abilities are modelled instead of hardcoded: Intimidate is -1, "
             "Swords Dance or Nasty Plot is +2.")
    def_stage = dcol.slider(
        "Defender's stage", -6, 6, 0, key=f"dexd_{prefix}",
        help="Stamina is +1 per hit taken. Screens are not modelled, so this is also "
             "the honest way to approximate one.")
    return weather, terrain, atk_stage, def_stage


def _best_rows(attackers: list[Build], defenders: list[Build], *, unknown, **field):
    """One row per (attacker, defender): its hardest hit, by the figure you can rely on."""
    out = []
    for a in attackers:
        for d in defenders:
            rows = versus(a, d, unknown=unknown, **field)
            if rows:
                out.append(rows[0])
    return sorted(out, key=lambda m: m.worst.low_pct, reverse=True)


ATTACKER_COL, DEFENDER_COL = "attacker", "defender"


def _table(rows, *, second_label: str, second_help: str, mine_attacking: bool,
           who: str, show: str) -> None:
    """One row per matchup. `show` names which side gets the sprite and the name.

    It is passed rather than derived from `mine_attacking`, because the two are not
    the same question and tying them together put a Rillaboom sprite on every row of
    a table headed "Your Pokémon". `mine_attacking` decides only which way the
    colours run: green when Andres lands the KO, red when he takes it.
    """
    if not rows:
        st.info("No damaging move to report — check the Moves box above.")
        return
    side = (lambda m: m.attacker) if show == ATTACKER_COL else (lambda m: m.defender)
    view = pd.DataFrame({
        # `or ""`: only meta species have a cached sprite, and ImageColumn renders a
        # bare None as the literal text "None".
        "": [data_uri(side(m).forme_id) or "" for m in rows],
        who: [side(m).display_name for m in rows],
        "Move": [m.move_name for m in rows],
        "As set": [f"{m.as_set.low_pct:.0f}–{m.as_set.high_pct:.0f}%" for m in rows],
        second_label: [f"{m.worst.low_pct:.0f}–{m.worst.high_pct:.0f}%" for m in rows],
        "Verdict": [m.worst.verdict() for m in rows],
    })

    def shade(_: pd.DataFrame) -> pd.DataFrame:
        css = pd.DataFrame("", index=view.index, columns=view.columns)
        col = view.columns.get_loc("Verdict")
        for i, m in enumerate(rows):
            if m.kos:
                css.iloc[i, col] = FILL_GOOD if mine_attacking else FILL_BAD
            elif m.as_set_kos:
                css.iloc[i, col] = FILL_CAUTION
            elif m.worst.high <= 0:
                css.iloc[i, col] = MUTED
        return css

    st.dataframe(
        view.style.apply(shade, axis=None), hide_index=True, width="stretch",
        column_config={
            "": st.column_config.ImageColumn(),
            "As set": st.column_config.TextColumn(
                help="Both builds exactly as the panels above have them"),
            second_label: st.column_config.TextColumn(help=second_help),
            "Verdict": st.column_config.TextColumn(
                help=f"Reads the **{second_label}** column, not 'As set' — it is the "
                     "figure that survives not knowing what they invested."),
        })


def _render_calculator(reg: str, meta_filter, team, formes, target: Build,
                       prof) -> None:
    st.subheader(f"Damage, both directions")
    weather, terrain, atk_stage, def_stage = _field_controls(target.forme_id)
    field = dict(weather=weather, terrain=terrain,
                 atk_stage=atk_stage, def_stage=def_stage)

    custom = st.toggle(
        "Attack it with a Pokémon that is not on my team", key="dex_custom",
        help="The other half of the calculator: build any attacker rather than only "
             "comparing against the loaded team.")

    if custom:
        other = _pick(reg, meta_filter, "dex_other", "Attacker",
                      default=prof.entry.pokemon_id)
        other_prof = profile(other, reg, meta_filter)
        attacker = _render_build(f"other_{other}",
                                 meta_build(other, reg, meta_filter, prof=other_prof),
                                 other_prof, compact=True)
        st.markdown(f"**{attacker.display_name} → {target.display_name}**")
        # Both sides are now explicit, so a second figure would be inventing a range
        # nobody asked for.
        _table(versus(attacker, target, unknown=None, **field),
               second_label="Same", second_help="Nothing is being guessed here",
               mine_attacking=True, who="Into", show=DEFENDER_COL)
        st.caption("Both builds are exactly as set, so there is one number rather "
                   "than two — the uncertainty the second figure carries elsewhere "
                   "is what you have just typed in.")
        return

    mine = team_builds(team, formes)
    if not mine:
        st.info("Select at least one of your Pokémon in the sidebar.")
        return

    st.markdown(f"**Your team → {target.display_name}**")
    _table(_best_rows(mine, [target], unknown=DEFENDER, **field),
           second_label="At max bulk",
           second_help="32 HP / 32 in that defence with a boosting nature — the "
                       "bulkiest thing it could legally be",
           mine_attacking=True, who="Your Pokémon", show=ATTACKER_COL)
    st.caption("Your side is exact, from the paste. Its side is whatever the panel "
               "above says — and because defensive investment is the softest data in "
               "the set (modal share about two thirds), the second column is the one "
               "a KO can be relied on from.")

    st.markdown(f"**{target.display_name} → your team**")
    _table(_best_rows([target], mine, unknown=ATTACKER, **field),
           second_label="At max offence",
           second_help="32 SP and a boosting nature — the most it could legally carry. "
                       "It matches 'As set' when the build above is already maxed.",
           mine_attacking=False, who="Your Pokémon", show=DEFENDER_COL)
    st.caption("The stage sliders read from the attacker's side in both tables, so on "
               "this one they are its boosts and your defence.")

    with st.expander("Every move, both directions"):
        st.markdown(f"**Your team → {target.display_name}**, every move")
        _table(sorted((m for a in mine for m in versus(a, target, unknown=DEFENDER, **field)),
                      key=lambda m: m.worst.low_pct, reverse=True),
               second_label="At max bulk", second_help="Its bulkiest legal build",
               mine_attacking=True, who="Your Pokémon", show=ATTACKER_COL)
        st.markdown(f"**{target.display_name} → your team**, every move")
        _table(sorted((m for d in mine for m in versus(target, d, unknown=ATTACKER, **field)),
                      key=lambda m: m.worst.low_pct, reverse=True),
               second_label="At max offence", second_help="Its heaviest legal offence",
               mine_attacking=False, who="Your Pokémon", show=DEFENDER_COL)


# --- the page -------------------------------------------------------------------

def render_dex(reg: str, meta_filter, team, formes) -> None:
    st.caption(
        "Pick any Pokémon, see what the meta runs on it, change anything you like, "
        "and calculate both ways. Nothing here touches your team or the warehouse."
    )
    pokemon_id = _pick(reg, meta_filter, "dex_pick", "Pokémon")
    prof = profile(pokemon_id, reg, meta_filter)

    _render_headline(prof)
    st.divider()
    st.subheader("What the meta runs")
    _render_meta(prof)
    st.divider()
    st.subheader("Set it up")
    st.caption(
        "Seeded with its most common build. Every control is yours to change; the "
        "damage below follows whatever is here."
        if prof.has_builds() else
        "Nothing in the data to seed this from, so it starts empty — give it a spread "
        "and at least one move. The damage below follows whatever is here.")
    seed = meta_build(pokemon_id, reg, meta_filter, prof=prof)
    target = _render_build(pokemon_id, seed, prof)
    st.divider()
    _render_calculator(reg, meta_filter, team, formes, target, prof)
