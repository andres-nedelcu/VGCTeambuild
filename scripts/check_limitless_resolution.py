"""Phase 0 exit check for Limitless: does every landed teamlist resolve against the dim tables?

Usage: uv run python scripts/check_limitless_resolution.py [--regulation M-C]
Read-only: never writes to the warehouse.
"""

import argparse
import json
from collections import Counter

from vgc import REPO_ROOT
from vgc.aliases import resolve
from vgc.db import connect, load_settings
from vgc.ids import to_id
from vgc.regulations import current


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regulation", default=current())
    args = ap.parse_args()
    root = REPO_ROOT / load_settings()["raw_data_dir"] / "limitless" / args.regulation
    folders = sorted(p.parent for p in root.glob("*/*/manifest.json"))
    if not folders:
        raise SystemExit(f"No landed tournaments under {root}")

    con = connect(read_only=True)
    try:
        pokemon = {r[0]: r[1] for r in con.execute("SELECT pokemon_id, base_species_id FROM dim_pokemon").fetchall()}
        moves = {r[0] for r in con.execute("SELECT move_id FROM dim_move").fetchall()}
        items = {r[0]: (r[1], r[2]) for r in con.execute(
            "SELECT item_id, is_mega_stone, mega_forme_id FROM dim_item").fetchall()}
        abilities = {to_id(r[0]) for r in con.execute("SELECT DISTINCT unnest(abilities) FROM dim_pokemon").fetchall()}
    finally:
        con.close()

    teams = 0
    species_teams = Counter()
    keys = Counter()
    miss = {"species": Counter(), "item": Counter(), "ability": Counter(), "move": Counter()}
    stone_mismatch = Counter()
    non_null_tera = team_sizes = 0
    sizes = Counter()
    for folder in folders:
        m = json.loads((folder / "manifest.json").read_text())
        standings = json.loads((folder / "standings.json").read_text())
        print(f"{m['event_date']}  {m['tournament_id']}  {m['with_teamlists']}/{m['players']} lists  "
              f"{m['platform']}  {m['name']}")
        for p in standings:
            team = p.get("decklist") or []
            if not team:
                continue
            teams += 1
            sizes[len(team)] += 1
            seen = set()
            for mon in team:
                keys.update(mon.keys())
                non_null_tera += mon.get("tera") is not None
                sid = resolve("limitless", mon.get("id"))
                if sid not in pokemon:
                    miss["species"][f"{mon.get('id')} ({mon.get('name')})"] += 1
                else:
                    seen.add(sid)
                item = mon.get("item")
                if item:
                    iid = resolve("limitless", item)
                    if iid not in items:
                        miss["item"][item] += 1
                    elif items[iid][0] and items[iid][1] and sid in pokemon \
                            and pokemon.get(items[iid][1]) != pokemon[sid]:
                        stone_mismatch[f"{mon.get('id')} holding {item}"] += 1
                if mon.get("ability") and resolve("limitless", mon["ability"]) not in abilities:
                    miss["ability"][mon["ability"]] += 1
                for mv in mon.get("attacks") or []:
                    if resolve("limitless", mv) not in moves:
                        miss["move"][mv] += 1
            species_teams.update(seen)

    print(f"\nTEAMLIST FORMAT: {teams} teams, sizes {dict(sizes)}; entry keys {dict(keys)}; "
          f"non-null tera: {non_null_tera}")
    total_miss = sum(sum(c.values()) for c in miss.values())
    print(f"EXIT CHECK: {'PASS' if total_miss == 0 else 'FAIL'} ({total_miss} unresolved references)")
    for kind, c in miss.items():
        print(f"  {kind} unresolved: {dict(c.most_common()) or 'none'}")
    print(f"  mega stone held by the wrong species: {dict(stone_mismatch) or 'none'}")
    print("\nTop 10 by team share:", ", ".join(
        f"{sid} {100 * n / teams:.0f}%" for sid, n in species_teams.most_common(10)))


if __name__ == "__main__":
    main()
