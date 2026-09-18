"""Load landed Limitless tournaments into fact_tournament + fact_tournament_set,
then roll all landed tournaments for the regulation up into fact_usage and
fact_usage_detail (source='limitless').

Usage: uv run python scripts/load_limitless.py [--regulation M-C]
Per-tournament rows are replaced by tournament_id (safe to rerun after
fetch_limitless.py lands more events). The usage rollup is recomputed in full
from every landed tournament each run, so it reflects the whole regulation to
date rather than any single event.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

from vgc import REPO_ROOT
from vgc.aliases import resolve
from vgc.db import connect, load_settings
from vgc.ids import to_id
from vgc.regulations import current


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regulation", default=current())
    args = ap.parse_args()
    reg = args.regulation

    root = REPO_ROOT / load_settings()["raw_data_dir"] / "limitless" / reg
    folders = sorted(p.parent for p in root.glob("*/*/manifest.json"))
    if not folders:
        raise SystemExit(f"No landed tournaments under {root}")

    con = connect(read_only=False)
    try:
        pokemon = {r[0] for r in con.execute("SELECT pokemon_id FROM dim_pokemon").fetchall()}
        moves = {r[0] for r in con.execute("SELECT move_id FROM dim_move").fetchall()}
        items = {r[0] for r in con.execute("SELECT item_id FROM dim_item").fetchall()}
        abilities = {to_id(r[0]) for r in con.execute(
            "SELECT DISTINCT unnest(abilities) FROM dim_pokemon").fetchall()}

        now = datetime.now()
        dropped = Counter()

        def keep(raw, valid, kind):
            """Resolve a descriptive field, dropping values the dims don't know.

            Teamlists are third-party data and occasionally carry junk (a Mega stone
            typed into the ability box, 'No Item'). Species is the join key and still
            fails the load; these fields are descriptive, so one typo in 6000 entries
            should not block the other 5999. Everything dropped is reported.
            """
            if not raw:
                return None
            value = resolve("limitless", raw)
            if value in valid:
                return value
            dropped[f"{kind} {raw!r}"] += 1
            return None

        tournaments, sets = [], []
        species_teams = Counter()
        detail_teams = defaultdict(Counter)  # (pokemon_id, detail_type) -> Counter(value)
        total_teams = 0

        for folder in folders:
            manifest = json.loads((folder / "manifest.json").read_text())
            standings = json.loads((folder / "standings.json").read_text())
            tid = manifest["tournament_id"]
            tournaments.append((tid, manifest["name"], reg, manifest["event_date"],
                                 manifest["players"], manifest["with_teamlists"] > 0,
                                 manifest["is_online"], now))
            for p in standings:
                team = p.get("decklist") or []
                if not team:
                    continue
                total_teams += 1
                pid, record = p["player"], p.get("record") or {}
                seen = set()
                for slot, mon in enumerate(team, 1):
                    sid = resolve("limitless", mon.get("id"))
                    if sid not in pokemon:
                        sys.exit(f"{tid} {pid} slot {slot}: unresolved species {mon.get('id')!r}")
                    iid = keep(mon.get("item"), items, "item")
                    aid = keep(mon.get("ability"), abilities, "ability")
                    mids = [m for m in (keep(mv, moves, "move")
                                        for mv in mon.get("attacks") or []) if m]
                    sets.append((tid, pid, p.get("placing"), record.get("wins"), record.get("losses"),
                                 record.get("ties"), slot, sid, iid, aid, mids))
                    if sid not in seen:
                        seen.add(sid)
                        if iid:
                            detail_teams[(sid, "item")][iid] += 1
                        if aid:
                            detail_teams[(sid, "ability")][aid] += 1
                        for mid in set(mids):
                            detail_teams[(sid, "move")][mid] += 1
                species_teams.update(seen)

        today = date.today()
        ranked = sorted(species_teams.items(), key=lambda kv: kv[1], reverse=True)
        usage_rows = [("limitless", reg, today, sid, n / total_teams, rank, total_teams, now)
                      for rank, (sid, n) in enumerate(ranked, 1)]
        detail_rows = [("limitless", reg, today, sid, dtype, value, cnt / species_teams[sid], now)
                        for (sid, dtype), counter in detail_teams.items()
                        for value, cnt in counter.items()]

        con.begin()
        for tid, *_ in tournaments:
            con.execute("DELETE FROM fact_tournament WHERE tournament_id = ?", [tid])
            con.execute("DELETE FROM fact_tournament_set WHERE tournament_id = ?", [tid])
        con.executemany("INSERT INTO fact_tournament VALUES (?,?,?,?,?,?,?,?)", tournaments)
        con.executemany("INSERT INTO fact_tournament_set VALUES (?,?,?,?,?,?,?,?,?,?,?)", sets)
        con.execute("DELETE FROM fact_usage WHERE source = 'limitless' AND regulation = ?", [reg])
        con.execute("DELETE FROM fact_usage_detail WHERE source = 'limitless' AND regulation = ?", [reg])
        con.executemany("INSERT INTO fact_usage VALUES (?,?,?,?,?,?,?,?)", usage_rows)
        con.executemany("INSERT INTO fact_usage_detail VALUES (?,?,?,?,?,?,?,?)", detail_rows)
        con.commit()

        n_t = con.execute("SELECT count(*) FROM fact_tournament WHERE regulation = ?", [reg]).fetchone()[0]
        n_u = con.execute("SELECT count(*) FROM fact_usage WHERE source='limitless' AND regulation=?",
                           [reg]).fetchone()[0]
        print(f"regulation={reg} tournaments={n_t} teams={total_teams} species={n_u} "
              f"detail_rows={len(detail_rows)}")
        print(f"dropped {sum(dropped.values())} unknown values: {dict(dropped) or 'none'}")
        print("Top 10:", ", ".join(f"{sid} {100*n/total_teams:.0f}%" for sid, n in ranked[:10]))
    finally:
        con.close()


if __name__ == "__main__":
    main()
