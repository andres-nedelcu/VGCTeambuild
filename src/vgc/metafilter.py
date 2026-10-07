"""Meta-side filters: which tournament results count as "the meta".

Every meta number in the app used to come from fact_usage, a precomputed rollup with
one row per species and no placement, date or event-size dimension -- so there was
nothing to filter by. The marts now aggregate fact_tournament_set through the
meta_usage macro instead, and this module is how Python asks for a slice of it.

A default MetaFilter() is the whole regulation, every event, every finisher, which
reproduces fact_usage exactly (tests/test_meta_filter.py pins this). So passing no
filter anywhere behaves exactly as before.

What each field is good for, against the 159 events landed on 2026-10-07, spanning
2026-09-09 to 2026-10-06 at 16-388 players each:

- cut          the sharp one. "What did teams that actually finished well bring."
               Costs sample: top 16 is 2,431 teams against 8,959, so small rank moves
               inside a cut view are still noise, not signal.
- weight       the gentle one. Keeps all 8,959 teams and weights each by its wins,
               so it is far more stable than a cut while still rewarding results.
               Agreeing moves between cut and weight are the ones worth trusting.
- since        no longer decorative -- this is now the filter that matters most. The
               window spans 27 days and the meta turned over inside it: Salamence ran
               41.3% -> 12.8% across the four weeks, Garchomp 11.7% -> 30.9%, Raichu
               6.4% -> 32.5%. An unfiltered view is an average over metas that are no
               longer the same one, so it understates both the risers and the fallers.
- min_players  bites more than it did (16-388, against 42-148 before), but the largest
               events here are still community events, not majors, so it separates by
               event size rather than by field strength.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from vgc.db import session

TEAMS, WINS = "teams", "wins"
WEIGHTS = (TEAMS, WINS)

# Below this many teams, treat rank order as indicative rather than meaningful.
# The meta stability work put ~3,000 teams as the bar for settling a top 15. The
# unfiltered view now clears that at 8,959; a cut view is still a fraction of it.
THIN_SAMPLE = 400


@dataclass(frozen=True)
class MetaFilter:
    """Which tournament entries count. Every field None/default means "no filter"."""

    cut: int | None = None
    since: date | None = None
    min_players: int | None = None
    weight: str = TEAMS

    def __post_init__(self) -> None:
        if self.weight not in WEIGHTS:
            raise ValueError(f"weight must be one of {WEIGHTS}, got {self.weight!r}")
        if self.cut is not None and self.cut < 1:
            raise ValueError(f"cut must be a placement of 1 or more, got {self.cut}")

    @property
    def is_default(self) -> bool:
        return self == MetaFilter()

    def call(self, macro: str) -> str:
        """SQL calling `macro` with placeholders. Casts are explicit because DuckDB
        cannot infer a type for a NULL parameter, and every filter here may be NULL."""
        return (f"{macro}(CAST(? AS VARCHAR), CAST(? AS INTEGER), CAST(? AS DATE), "
                f"CAST(? AS INTEGER), CAST(? AS VARCHAR))")

    def params(self, regulation: str) -> list:
        """Bind values for `call`, in order."""
        return [regulation, self.cut, self.since, self.min_players, self.weight]

    def label(self) -> str:
        """One-line summary for a caption. Says what is included, not what is excluded."""
        parts = []
        parts.append(f"top {self.cut} finishers" if self.cut else "all finishers")
        if self.weight == WINS:
            parts.append("weighted by wins")
        if self.since:
            parts.append(f"events from {self.since}")
        if self.min_players:
            parts.append(f"{self.min_players}+ players")
        return ", ".join(parts)


def sample_size(regulation: str, filt: MetaFilter | None = None) -> int:
    """How many teams this filter actually selects. 0 if it selects nothing."""
    filt = filt or MetaFilter()
    with session() as con:
        row = con.execute(
            f"select max(sample_size) from {filt.call('meta_usage')}",
            filt.params(regulation)).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


@dataclass(frozen=True)
class Extent:
    """What the landed events actually span, so the filter controls can be honest
    about which of them have anything to bite on yet."""

    events: int
    first: date | None
    last: date | None
    smallest: int | None
    largest: int | None

    @property
    def days(self) -> int:
        return (self.last - self.first).days if self.first and self.last else 0


def extent(regulation: str) -> Extent:
    """Range of the landed tournaments for a regulation."""
    with session() as con:
        row = con.execute("""
            select count(*), min(event_date), max(event_date), min(players), max(players)
            from fact_tournament where regulation = ?
        """, [regulation]).fetchone()
    return Extent(*row) if row else Extent(0, None, None, None, None)
