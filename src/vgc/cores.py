"""Teammate cores: which species actually appear on a team together.

Reads mart_meta_cores, which is a self-join over 1,553 tournament teams. The outline
deferred this on the grounds that CBD's teammate rows carry no percentage; they are
not needed, because the teamlists give true co-occurrence directly.

**Read lift, not share.** Rillaboom is on over half of all teams, so nearly every
popular species "pairs" with it at a high share — Rillaboom and Sneasler appear
together 431 times at a lift of 1.03, which is exactly what chance predicts. Lift
divides that out: well above 1 means the two are being chosen *for each other*
(Excadrill and Tyranitar sit at 13.0, because that pair is sand).

Grain is species, not forme: you pick a species, and the stone is a later build
choice. Cores respect the meta filter, so "what did top-cut teams pair this with" is
the same question asked of a smaller, better population.
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from vgc.db import session
from vgc.metafilter import MetaFilter, sample_size

BUILD_CMD = "uv run python scripts/build_marts.py"

# A pair needs enough teams behind it to mean anything, and a cut view has far fewer
# teams to draw on, so the floor scales with the sample rather than being a constant
# that is lax at 1,553 teams and impossible at 152.
MIN_SUPPORT_FRACTION = 0.02
MIN_SUPPORT_FLOOR = 5

# Lift at or below this is two popular Pokemon meeting by chance, not a core.
CHANCE = 1.0


def min_support(regulation: str, filt: MetaFilter | None = None) -> int:
    n = sample_size(regulation, filt)
    return max(MIN_SUPPORT_FLOOR, round(MIN_SUPPORT_FRACTION * n))


def _read(regulation: str, filt: MetaFilter) -> pd.DataFrame:
    with session() as con:
        try:
            return con.execute(f"""
                select a_id, b_id, a_name, b_name, together,
                       share_of_a, share_of_b, lift
                from {filt.call('meta_cores')}
            """, filt.params(regulation)).df()
        except Exception as e:  # noqa: BLE001 - surfaced to the user as a build hint
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e


def cores(regulation: str, filt: MetaFilter | None = None,
          min_together: int | None = None) -> pd.DataFrame:
    """The meta's genuine cores, strongest association first."""
    filt = filt or MetaFilter()
    floor = min_support(regulation, filt) if min_together is None else min_together
    df = _read(regulation, filt)
    df = df[(df["together"] >= floor) & (df["lift"] > CHANCE)]
    return df.sort_values("lift", ascending=False).reset_index(drop=True)


def partners(regulation: str, species_ids: Sequence[str], filt: MetaFilter | None = None,
             min_together: int | None = None, exclude_own: bool = True) -> pd.DataFrame:
    """Species the meta pairs with the ones you already have.

    One row per (your species, candidate partner). Candidates already on the team are
    dropped by default — the question is what to add, not what you have.
    """
    filt = filt or MetaFilter()
    floor = min_support(regulation, filt) if min_together is None else min_together
    mine = set(species_ids)
    if not mine:
        return pd.DataFrame(columns=["yours", "partner", "partner_id", "together",
                                     "share", "lift"])
    df = _read(regulation, filt)

    # The mart stores each pair once with a_id < b_id, so both orientations have to be
    # considered and the "share" always read from your side of the pair.
    left = df[df["a_id"].isin(mine)].rename(columns={
        "a_name": "yours", "b_name": "partner", "b_id": "partner_id",
        "share_of_a": "share"})[["yours", "partner", "partner_id", "together", "share", "lift"]]
    right = df[df["b_id"].isin(mine)].rename(columns={
        "b_name": "yours", "a_name": "partner", "a_id": "partner_id",
        "share_of_b": "share"})[["yours", "partner", "partner_id", "together", "share", "lift"]]

    out = pd.concat([left, right], ignore_index=True)
    out = out[(out["together"] >= floor) & (out["lift"] > CHANCE)]
    if exclude_own:
        out = out[~out["partner_id"].isin(mine)]
    return out.sort_values("lift", ascending=False).reset_index(drop=True)


# An item has to move a partner's share by at least this much to be worth showing.
MIN_DELTA = 0.15


def _read_item_cores(regulation: str, filt: MetaFilter) -> pd.DataFrame:
    with session() as con:
        try:
            return con.execute(f"""
                select holder_id, holder_name, item_id, item_name,
                       partner_id, partner_name, together, holder_teams_with_item,
                       share, base_share, delta, lift
                from {filt.call('meta_item_cores')}
            """, filt.params(regulation)).df()
        except Exception as e:  # noqa: BLE001
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e


def item_cores(regulation: str, filt: MetaFilter | None = None,
               min_teams: int | None = None, min_delta: float = MIN_DELTA,
               holders: Sequence[str] | None = None,
               items: Sequence[tuple[str, str]] | None = None) -> pd.DataFrame:
    """Partnerships that only appear once you condition on the holder's item.

    Species-level co-occurrence averages a species' builds together, which erases a
    partnership when two builds want opposite partners. Sneasler is the worked
    example: Grassy Seed wants Rillaboom, Psychic Seed wants Indeedee, and averaged
    over items the two cancel to a lift of 1.03. Pass `holders` to limit this to the
    species on a team.
    """
    filt = filt or MetaFilter()
    floor = min_support(regulation, filt) if min_teams is None else min_teams
    df = _read_item_cores(regulation, filt)
    # Both floors matter. Without one on the pair itself, lift is dominated by
    # single-team accidents: one Focus Sash Sneasler beside a Scolipede reads as a
    # lift of 18 purely because Scolipede is rare.
    df = df[(df["holder_teams_with_item"] >= floor)
            & (df["together"] >= floor)
            & (df["delta"] >= min_delta)]
    if holders is not None:
        df = df[df["holder_id"].isin(set(holders))]
    if items is not None:
        want = set(items)
        df = df[[(h, i) in want for h, i in zip(df["holder_id"], df["item_id"])]]
    return df.sort_values("delta", ascending=False).reset_index(drop=True)
