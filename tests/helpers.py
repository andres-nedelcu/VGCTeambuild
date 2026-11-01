"""Shared test helpers.

Teams used to be warehouse rows and six test files hardcoded the same paste id
(`b58a4fb249fb3cbf`), which tied the suite to one person's loaded data: on any other
checkout those tests skipped, and a skipped test is green. Teams are files now, so a
test can ask for one *by shape* instead — any saved team with a full six — and the
suite stops depending on which pastes happen to be sitting in the store.
"""

from __future__ import annotations

from vgc.team import Member, list_teams

FULL_TEAM = 6


def full_team_id() -> str | None:
    """A saved team with six members, or None. Oldest first, so the id a test picks
    does not change every time a team is saved.

    Only for tests asserting things true of *any* team. A test that asserts facts
    about a particular one wants `reference_team()` instead — see below.
    """
    teams = [t for t in list_teams() if len(t.members) >= FULL_TEAM]
    if not teams:
        return None
    return sorted(teams, key=lambda t: (t.created_at or "", t.id))[0].id


def reference_team() -> list[Member]:
    """A fixed six, owned by the suite rather than read from the store.

    This is the paste the mega and defensive-grid tests were written against, and
    they assert specific things about it: Golisopod and Gardevoir as the two Mega
    options, Pelipper 4x weak to Electric, three Electric weaknesses with nothing
    resisting. Reading it from the store made those assertions hostage to whichever
    teams happened to be saved — when it was deleted from the store on 2026-11-01
    they started failing against a different team, which is the bug this fixes.

    Nothing here needs the warehouse, so these tests now run on a bare checkout.
    """
    return [
        Member(slot=1, pokemon_id="golisopod", item_id="golisopite",
               ability_id="emergencyexit", nature="Adamant",
               investment={"unit": "sp", "values": {"hp": 32, "atk": 32, "spd": 2}},
               moves=["protect", "swordsdance", "ironhead", "leechlife"]),
        Member(slot=2, pokemon_id="indeedeef", item_id="colburberry",
               ability_id="psychicsurge", nature="Calm",
               investment={"unit": "sp", "values": {"hp": 32, "def": 25, "spd": 9}},
               moves=["followme", "helpinghand", "trickroom", "psychic"]),
        Member(slot=3, pokemon_id="sneasler", item_id="psychicseed",
               ability_id="unburden", nature="Adamant",
               investment={"unit": "sp", "values": {"hp": 2, "atk": 32, "spe": 32}},
               moves=["protect", "closecombat", "direclaw", "rockslide"]),
        Member(slot=4, pokemon_id="pelipper", item_id="focussash",
               ability_id="drizzle", nature="Modest",
               investment={"unit": "sp", "values": {"hp": 2, "spa": 32, "spe": 32}},
               moves=["protect", "tailwind", "weatherball", "hurricane"]),
        Member(slot=5, pokemon_id="gardevoir", item_id="gardevoirite",
               ability_id="trace", nature="Modest",
               investment={"unit": "sp", "values": {"hp": 29, "spa": 32, "spe": 5}},
               moves=["protect", "expandingforce", "hypervoice", "trickroom"]),
        Member(slot=6, pokemon_id="basculegion", item_id="choicescarf",
               ability_id="adaptability", nature="Jolly",
               investment={"unit": "sp", "values": {"hp": 2, "atk": 32, "spe": 32}},
               moves=["flipturn", "wavecrash", "lastrespects", "aquajet"]),
    ]
