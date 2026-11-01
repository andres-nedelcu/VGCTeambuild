"""One-time: copy my_team out of the warehouse into data/teams/*.json.

Usage: uv run python scripts/migrate_teams.py [--force]

Reads only. The warehouse table is left exactly as it is, so this can be run,
checked, and run again before anything is dropped. Existing team files are skipped
unless --force, which makes a rerun safe after an interrupted one.

Verifies by reading every written file back and comparing team and member counts
against the table it came from.
"""

import argparse
import json
import sys

from vgc.db import connect
from vgc.team import Member, Team, list_teams, save, slugify, validate


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite existing team files")
    args = ap.parse_args()

    con = connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "my_team" not in tables:
            print("No my_team table — nothing to migrate.")
            return
        rows = con.execute("""
            select paste_id, team_name, slot, pokemon_id, nickname, item_id,
                   ability_id, nature, investment, moves, loaded_at
            from my_team order by paste_id, slot
        """).fetchall()
    finally:
        con.close()

    if not rows:
        print("my_team is empty — nothing to migrate.")
        return

    by_paste: dict[str, list] = {}
    for r in rows:
        by_paste.setdefault(r[0], []).append(r)

    taken = {t.id for t in list_teams()}
    written, skipped = [], []
    for paste_id, group in by_paste.items():
        name = group[0][1] or paste_id
        team_id = slugify(name)
        if team_id in taken and not args.force:
            print(f"  skip  {name!r} -> {team_id}.json (already exists)")
            skipped.append(team_id)
            continue
        suffix = 2
        while team_id in taken and not args.force:
            team_id, suffix = f"{slugify(name)}-{suffix}", suffix + 1

        members = [Member(
            slot=g[2], pokemon_id=g[3], item_id=g[5], ability_id=g[6],
            nickname=g[4], nature=g[7],
            investment=json.loads(g[8]) if isinstance(g[8], str) else g[8],
            moves=list(g[9] or []),
        ) for g in group]

        problems, warnings = validate(members)
        for w in warnings:
            print(f"     warning: {w}")
        if problems:
            print(f"  FAIL  {name!r}: not written")
            for p in problems:
                print(f"     - {p}")
            continue

        created = min(g[10] for g in group).isoformat(timespec="seconds")
        # touch=False: this copies teams, it does not modify them. Stamping all eight
        # with one import time would flatten the order the picker reads.
        team = save(Team(
            id=team_id, name=name, members=members,
            source={"kind": "pokepaste", "paste_id": paste_id,
                    "url": f"https://pokepast.es/{paste_id}"},
            created_at=created, modified_at=created,
        ), touch=False)
        taken.add(team_id)
        written.append(team)
        print(f"  write {name!r} -> {team.id}.json ({len(members)} members)")

    print("\n--- verify ---")
    on_disk = {t.id: t for t in list_teams()}
    expected_members = sum(len(g) for g in by_paste.values())
    found_members = sum(len(on_disk[t.id].members) for t in written if t.id in on_disk)
    print(f"  pastes in my_team : {len(by_paste)}")
    print(f"  teams written     : {len(written)} (skipped {len(skipped)})")
    print(f"  teams on disk     : {len(on_disk)}")
    missing = [t.id for t in written if t.id not in on_disk]
    if missing:
        print(f"\nEXIT CHECK: FAIL — written but not readable back: {missing}")
        sys.exit(1)
    if skipped:
        print(f"  members expected  : {expected_members} across all pastes "
              f"(not compared — some teams were skipped)")
    elif found_members != expected_members:
        print(f"\nEXIT CHECK: FAIL — {found_members} members on disk, "
              f"{expected_members} in my_team")
        sys.exit(1)
    else:
        print(f"  members           : {found_members} on disk == {expected_members} in my_team")
    print("\nEXIT CHECK: PASS — my_team is untouched and can be dropped separately.")


if __name__ == "__main__":
    main()
