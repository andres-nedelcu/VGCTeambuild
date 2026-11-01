"""One-time: drop my_team from an existing warehouse, after the file store has it.

Usage: uv run python scripts/drop_my_team.py [--force]

The schema no longer creates my_team, but `CREATE TABLE IF NOT EXISTS` never drops
anything — so a warehouse built before 2026-11-01 still carries the table. This
removes it.

Refuses unless every paste in my_team is accounted for in data/teams/, because this
is the step that makes the migration irreversible. --force skips that check and
should only be used when you know why the counts differ.
"""

import argparse
import sys

from vgc.db import connect
from vgc.team import list_teams


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="drop even if the file store looks incomplete")
    args = ap.parse_args()

    con = connect(read_only=True)
    try:
        if "my_team" not in {r[0] for r in con.execute("SHOW TABLES").fetchall()}:
            print("No my_team table — nothing to drop.")
            return
        rows = con.execute(
            "select paste_id, count(*) from my_team group by paste_id").fetchall()
    finally:
        con.close()

    in_table = {pid: n for pid, n in rows}
    saved = list_teams()
    by_paste = {t.source.get("paste_id"): t for t in saved if t.source.get("paste_id")}

    print(f"my_team      : {len(in_table)} pastes, {sum(in_table.values())} rows")
    print(f"data/teams/  : {len(saved)} teams, "
          f"{sum(len(t.members) for t in saved)} members")

    missing = [pid for pid in in_table if pid not in by_paste]
    short = [(pid, in_table[pid], len(by_paste[pid].members))
             for pid in in_table
             if pid in by_paste and len(by_paste[pid].members) != in_table[pid]]

    if missing:
        print("\n  pastes with no team file:")
        for pid in missing:
            print(f"    - {pid}")
    for pid, had, now in short:
        print(f"    - {pid}: {had} rows in my_team, {now} members on disk "
              f"({by_paste[pid].id}.json)")

    if (missing or short) and not args.force:
        print("\nEXIT CHECK: FAIL — nothing dropped.")
        print("Run scripts/migrate_teams.py first, or pass --force if the "
              "difference is expected (a team edited since migrating, say).")
        sys.exit(1)

    con = connect(read_only=False)
    try:
        con.execute("DROP TABLE IF EXISTS my_team")
        gone = "my_team" not in {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()

    if not gone:
        print("\nEXIT CHECK: FAIL — my_team is still there.")
        sys.exit(1)
    print("\nEXIT CHECK: PASS — my_team dropped. Teams live in data/teams/ only now, "
          "which is gitignored, so back it up yourself.")


if __name__ == "__main__":
    main()
