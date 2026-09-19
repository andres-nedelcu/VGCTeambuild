"""The build controls, shared by the Spreads tab and the dex view.

Both places ask the same question — nature, SP, and what that produces — so this
holds the three pieces they have in common and neither owns the layout. The Spreads
tab puts the nature box beside a sprite and loops over six team members; the dex view
puts it beside an item and an ability for one arbitrary Pokémon. Nothing here knows
about either arrangement.

Two details are load-bearing and were both found by opening the app rather than by a
test, so they live here once instead of being re-derived:

  THE NATURE BOX CARRIES AN EXPLICIT "no nature". A team locked in the game arrives
  without natures. Letting the selectbox default to index 0 silently applied
  **Adamant** to every unnatured Pokémon and flagged the team as edited.

  READ BY KEY, NOT BY RETURN VALUE. Streamlit runs the script top to bottom, and the
  Spreads tab's widgets render below the visuals that consume them, so their return
  values arrive too late. `stored_spread` reads session state by key on the way
  through; Streamlit persists a widget's value by key across reruns, so an edit
  lands, triggers a rerun, and is picked up on the next pass. The dex view renders
  its widgets above what consumes them and does not need this, but it costs nothing
  to use the same path in both.
"""

from __future__ import annotations

import streamlit as st

from vgc.edit import ALL_NATURES, LABELS, Spread, problem
from vgc.matchup import base_stats
from vgc.stats import SP_MAX_PER_STAT, SP_MAX_TOTAL, STATS, calc_stat, nature_mod

# None is a real option, not a missing one — see the module docstring.
NATURE_OPTIONS = (None, *ALL_NATURES)


def sp_key(prefix: str, stat: str) -> str:
    return f"sp_{prefix}_{stat}"


def nature_key(prefix: str) -> str:
    return f"nat_{prefix}"


def stored_spread(prefix: str, base: Spread) -> Spread:
    """The spread currently in the widgets, falling back to `base` before first render."""
    sp = {s: int(st.session_state.get(sp_key(prefix, s), base.sp.get(s, 0)))
          for s in STATS}
    return Spread(st.session_state.get(nature_key(prefix), base.nature), sp)


def render_nature(prefix: str, spread: Spread, container=None,
                  label: str = "Nature", collapsed: bool = True) -> None:
    box = container if container is not None else st
    current = spread.nature.lower() if spread.nature else None
    box.selectbox(
        label, NATURE_OPTIONS,
        index=NATURE_OPTIONS.index(current) if current in NATURE_OPTIONS else 0,
        key=nature_key(prefix),
        format_func=lambda n: "— no nature —" if n is None else n.title(),
        label_visibility="collapsed" if collapsed else "visible")


def render_sp(prefix: str, spread: Spread) -> None:
    """Six SP inputs, one per stat, in the order a spread string is written."""
    cols = st.columns(len(STATS))
    for col, stat in zip(cols, STATS):
        col.number_input(
            LABELS[stat], min_value=0, max_value=SP_MAX_PER_STAT, step=1,
            value=spread.sp.get(stat, 0), key=sp_key(prefix, stat))


def stat_line(forme_id: str, spread: Spread) -> str:
    """The resulting stat line, so the cost of a choice is visible as it is made."""
    try:
        base = base_stats(forme_id)
    except LookupError:
        return ""
    return " · ".join(
        f"{LABELS[stat]} {calc_stat(base[stat], spread.sp.get(stat, 0), nature_mod(spread.nature, stat), stat=stat)}"
        for stat in STATS)


def render_feedback(forme_id: str | None, spread: Spread) -> str | None:
    """The stat line, or the reason this spread is illegal. Returns the error."""
    err = problem(spread)
    if err:
        st.error(err)
    elif forme_id:
        st.caption(f"{stat_line(forme_id, spread)}  ·  {spread.remaining} SP left")
    return err


def caps_caption() -> str:
    return f"{SP_MAX_PER_STAT} SP per stat, {SP_MAX_TOTAL} total."
