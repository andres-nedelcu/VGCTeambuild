"""How old is each source's data? Shared by scripts/refresh.py and the app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from vgc.db import session


@dataclass(frozen=True)
class Source:
    name: str
    as_of: date | None       # the data's own date, not when we fetched it
    loaded_at: datetime | None
    detail: str

    def age_days(self, today: date | None = None) -> int | None:
        if self.as_of is None:
            return None
        return ((today or date.today()) - self.as_of).days

    def age_label(self, today: date | None = None) -> str:
        """Human-readable age. CBD's newest day can sit a day ahead of local time,
        which would otherwise render as a nonsensical '-1d old'."""
        age = self.age_days(today)
        if age is None:
            return "static"
        return "today" if age <= 0 else f"{age}d old"


def sources(regulation: str) -> list[Source]:
    with session() as con:
        tourneys = con.execute("""
            select count(*), max(event_date), max(loaded_at)
            from fact_tournament where regulation = ?
        """, [regulation]).fetchone()
        teams = con.execute("""
            select max(sample_size) from fact_usage
            where source = 'limitless' and regulation = ?
        """, [regulation]).fetchone()[0]
        cbd = con.execute("""
            select max(snapshot_date), max(loaded_at), count(distinct pokemon_id)
            from fact_usage_detail where source = 'cbd' and regulation = ?
        """, [regulation]).fetchone()
        static = con.execute(
            "select max(loaded_at), any_value(data_source) from dim_pokemon").fetchone()

    count, latest_event, tourney_loaded = tourneys
    cbd_date, cbd_loaded, cbd_species = cbd
    static_loaded, static_source = static
    return [
        Source("Limitless tournaments", latest_event, tourney_loaded,
               f"{count or 0} events, {teams or 0} teams" if count else "nothing landed"),
        Source("Champions Battle Data", cbd_date, cbd_loaded,
               f"{cbd_species} species" if cbd_species else "nothing landed"),
        Source("Showdown static data", None, static_loaded, static_source or "not loaded"),
    ]
