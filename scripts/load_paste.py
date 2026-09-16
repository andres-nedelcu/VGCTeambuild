"""Fetch a PokePaste, check every reference resolves, and load it into my_team.

Usage: uv run python scripts/load_paste.py https://pokepast.es/<16-hex-id>
Writes only if everything resolves; rerunning replaces that paste's rows.
"""

import argparse
import json
import sys
from datetime import datetime

from vgc.db import connect
from vgc.ids import to_id
from vgc.ingest import pokepaste


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    args = ap.parse_args()

    pid, payload = pokepaste.fetch(args.url)
    sets = pokepaste.parse(payload["paste"])
    team_name = payload.get("title") or pid
    print(f"Paste {pid}: '{team_name}' by {payload.get('author') or '?'}; {len(sets)} Pokémon")

    con = connect(read_only=False)
    try:
        pokemon = {r[0]: r[1:] for r in con.execute(
            "SELECT pokemon_id, base_species_id, is_mega, is_nonstandard FROM dim_pokemon").fetchall()}
        moves = {r[0] for r in con.execute("SELECT move_id FROM dim_move").fetchall()}
        items = {r[0]: r[1:] for r in con.execute(
            "SELECT item_id, is_mega_stone, mega_forme_id FROM dim_item").fetchall()}
        abilities = {to_id(r[0]) for r in con.execute(
            "SELECT DISTINCT unnest(abilities) FROM dim_pokemon").fetchall()}

        problems, warnings, rows = [], [], []
        for slot, s in enumerate(sets, 1):
            pkid, iid, aid = to_id(s["species"]), to_id(s["item"]), to_id(s["ability"])
            mids = [to_id(m) for m in s["moves"]]
            label = f"slot {slot} {s['species']}"
            if pkid not in pokemon:
                problems.append(f"{label}: species not in dim_pokemon")
            elif pokemon[pkid][2]:
                warnings.append(f"{label}: flagged {pokemon[pkid][2]} in Showdown's Champions data")
            if iid and iid not in items:
                problems.append(f"{label}: item {s['item']!r} not in dim_item")
            if aid and aid not in abilities:
                problems.append(f"{label}: ability {s['ability']!r} unknown")
            if not aid:
                warnings.append(f"{label}: no ability line")
            for m, mid in zip(s["moves"], mids):
                if mid not in moves:
                    problems.append(f"{label}: move {m!r} not in dim_move")
            if len(mids) != 4:
                warnings.append(f"{label}: {len(mids)} moves")
            inv = s["investment"]
            if inv["unit"] != "sp":
                problems.append(f"{label}: EVs look like mainline EVs ({inv['values']}), not Champions stat points")
            rows.append((pid, team_name, slot, pkid, s["nickname"], iid, aid, s["nature"],
                         json.dumps(inv), mids, datetime.now()))
            sp = inv["values"]
            print(f"  {slot}. {s['species']:<18} @ {s['item'] or '-':<16} {s['ability'] or '-':<16} "
                  f"{s['nature'] or '-':<8} SP {sp} ({inv['total']}/66)  {', '.join(s['moves'])}")
            if iid in items and items[iid][0]:
                forme = items[iid][1]
                note = forme or "AMBIGUOUS stone (resolve from forme)"
                if forme and forme in pokemon and pokemon[forme][0] != (pokemon.get(pkid) or [None])[0]:
                    problems.append(f"{label}: {s['item']} does not belong to this species")
                print(f"     Mega via {s['item']} -> {note}")

        for w in warnings:
            print("  warning:", w)
        if problems:
            print("\nEXIT CHECK: FAIL — nothing written")
            for p in problems:
                print("  -", p)
            sys.exit(1)

        con.begin()
        con.execute("DELETE FROM my_team WHERE paste_id = ?", [pid])
        con.executemany("INSERT INTO my_team VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        con.commit()
        n = con.execute("SELECT count(*) FROM my_team WHERE paste_id = ?", [pid]).fetchone()[0]
        print(f"\nEXIT CHECK: PASS — {n} rows in my_team for paste {pid}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
