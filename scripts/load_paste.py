"""Fetch a PokePaste, check every reference resolves, and save it to data/teams/.

Usage: uv run python scripts/load_paste.py https://pokepast.es/<16-hex-id> [--name NAME]
Writes only if everything resolves; re-importing the same paste replaces that team.

The app can do this too now (teams are files, not warehouse rows), so this script is
the terminal route rather than the only one. Both go through vgc.team.validate, so
neither can save a team the other would refuse.
"""

import argparse
import sys

from vgc.ingest import pokepaste
from vgc.stats import STATS
from vgc.team import (Team, list_teams, members_from_sets, save, unique_id,
                      validate)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--name", help="override the team name (default: the paste title)")
    args = ap.parse_args()

    pid, payload = pokepaste.fetch(args.url)
    sets = pokepaste.parse(payload["paste"])
    team_name = args.name or payload.get("title") or pid
    print(f"Paste {pid}: '{team_name}' by {payload.get('author') or '?'}; {len(sets)} Pokémon")

    members = members_from_sets(sets)

    # Re-importing a paste replaces the team it produced before, rather than piling
    # up near-duplicates: the paste id is the identity, the slug is only the filename.
    existing = next((t for t in list_teams()
                     if t.source.get("paste_id") == pid), None)
    team_id = existing.id if existing else unique_id(team_name)

    for m in members:
        inv = m.investment or {}
        sp = inv.get("values", {}) if isinstance(inv, dict) else {}
        shown = {s: sp[s] for s in STATS if sp.get(s)}
        print(f"  {m.slot}. {m.pokemon_id:<18} @ {m.item_id or '-':<16} "
              f"{m.ability_id or '-':<16} {m.nature or '-':<8} "
              f"SP {shown} ({inv.get('total', 0)}/66)  {', '.join(m.moves or [])}")

    problems, warnings = validate(members)
    for w in warnings:
        print("  warning:", w)
    if problems:
        print("\nEXIT CHECK: FAIL — nothing written")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    team = save(Team(
        id=team_id, name=team_name, members=members,
        source={"kind": "pokepaste", "paste_id": pid,
                "url": f"https://pokepast.es/{pid}",
                "author": payload.get("author") or None},
        created_at=existing.created_at if existing else None,
    ))
    verb = "replaced" if existing else "saved"
    print(f"\nEXIT CHECK: PASS — {verb} {len(team.members)} members as {team.id}.json")


if __name__ == "__main__":
    main()
