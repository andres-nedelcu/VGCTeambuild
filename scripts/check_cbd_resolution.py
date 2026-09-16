"""Phase 0 exit check: does the CBD top-N resolve against the static dim tables?

Usage: uv run python scripts/check_cbd_resolution.py [--folder data/raw/cbd/M-C/2026-09-16] [--top 50]
Read-only: never writes to the warehouse.
"""

import argparse
import json
from pathlib import Path

from vgc import REPO_ROOT
from vgc.db import connect, load_settings
from vgc.ids import to_id
from vgc.regulations import current


def latest_folder() -> Path:
    root = REPO_ROOT / load_settings()["raw_data_dir"] / "cbd" / current()
    done = sorted(p.parent for p in root.glob("*/manifest.json"))
    if not done:
        raise SystemExit(f"No completed snapshot under {root}")
    return done[-1]


def load_snapshot(folder: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((folder / "manifest.json").read_text())
    entries = []
    for f in sorted((folder / manifest["format"]).glob("*.json")):
        data = json.loads(f.read_text())
        day = next(d for d in data["daily"]
                   if d["season"] == manifest["season"] and d["date"] == manifest["cbd_date"])
        entries.append({"pokemon_id": to_id(data["showdownId"]), "name": data["pokemon"],
                        "rank": day["rows"][0]["column_position"], "rows": day["rows"]})
    return manifest, sorted(entries, key=lambda e: e["rank"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", type=Path, default=None)
    ap.add_argument("--top", type=int, default=50)
    args = ap.parse_args()
    folder = (REPO_ROOT / args.folder) if args.folder else latest_folder()
    manifest, entries = load_snapshot(folder)
    print(f"{folder.relative_to(REPO_ROOT)}  {manifest['season']} {manifest['cbd_date']}  "
          f"{len(entries)} Pokémon (manifest says {manifest['pokemon_count']})")

    ranks = [e["rank"] for e in entries]
    if len(set(ranks)) != len(ranks):
        print("WARNING: duplicate ranks:", sorted({r for r in ranks if ranks.count(r) > 1}))

    con = connect(read_only=True)
    try:
        pokemon = dict(con.execute("SELECT pokemon_id, is_nonstandard FROM dim_pokemon").fetchall())
        moves = {r[0] for r in con.execute("SELECT move_id FROM dim_move").fetchall()}
        items = {r[0]: (r[1], r[2]) for r in con.execute(
            "SELECT item_id, is_mega_stone, mega_forme_id FROM dim_item").fetchall()}
        abilities = {to_id(r[0]) for r in con.execute(
            "SELECT DISTINCT unnest(abilities) FROM dim_pokemon").fetchall()}
    finally:
        con.close()

    top = entries[: args.top]
    print("\nTop 10:", ", ".join(f"{e['rank']}. {e['name']}" for e in top[:10]))

    missing_mon = [e["name"] for e in entries if e["pokemon_id"] not in pokemon]
    top_missing = [e["name"] for e in top if e["pokemon_id"] not in pokemon]
    flagged = [e["name"] for e in top if pokemon.get(e["pokemon_id"])]
    lookup = {"move": moves, "held_item": items, "ability": abilities, "teammate": pokemon}
    unresolved = {k: set() for k in lookup}
    for e in top:
        for row in e["rows"]:
            cat = row["category"]
            if cat in lookup and row["name"] and to_id(row["name"]) not in lookup[cat]:
                unresolved[cat].add(row["name"])

    ok = len(top) - len(top_missing)
    print(f"\nEXIT CHECK: top {len(top)} Pokémon resolved {ok}/{len(top)}", "PASS" if not top_missing else "FAIL")
    if top_missing:
        print("  unresolved:", top_missing)
    if missing_mon:
        print(f"All {len(entries)}: {len(missing_mon)} unresolved:", missing_mon)
    if flagged:
        print("  in top N but flagged nonstandard in Showdown:", flagged)
    for cat, names in unresolved.items():
        print(f"  top-{len(top)} {cat} names unresolved: {sorted(names) or 'none'}")

    print("\nMega stones held by top-N Pokémon (>= 5%):")
    for e in top:
        for row in e["rows"]:
            if row["category"] == "held_item" and (row.get("percentage_value") or 0) >= 5:
                stone = items.get(to_id(row["name"]))
                if stone and stone[0]:
                    forme = stone[1] or "AMBIGUOUS (resolve from forme)"
                    ok_forme = "" if stone[1] is None or stone[1] in pokemon else "  <- forme missing!"
                    print(f"  {e['name']:<14} {row['name']:<16} {row['percentage_value']:>5}%  -> {forme}{ok_forme}")


if __name__ == "__main__":
    main()
