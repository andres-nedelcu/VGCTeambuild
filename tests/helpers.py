"""Shared test helpers.

Teams used to be warehouse rows and six test files hardcoded the same paste id
(`b58a4fb249fb3cbf`), which tied the suite to one person's loaded data: on any other
checkout those tests skipped, and a skipped test is green. Teams are files now, so a
test can ask for one *by shape* instead — any saved team with a full six — and the
suite stops depending on which pastes happen to be sitting in the store.
"""

from __future__ import annotations

from vgc.team import list_teams

FULL_TEAM = 6


def full_team_id() -> str | None:
    """A saved team with six members, or None. Oldest first, so the id a test picks
    does not change every time a team is saved."""
    teams = [t for t in list_teams() if len(t.members) >= FULL_TEAM]
    if not teams:
        return None
    return sorted(teams, key=lambda t: (t.created_at or "", t.id))[0].id
