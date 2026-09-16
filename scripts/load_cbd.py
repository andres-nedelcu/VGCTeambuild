"""Load the newest CBD landing into fact_usage_detail (source='cbd').
Keeps only the latest date per regulation; rerunning replaces, never duplicates.
Usage: uv run python scripts/load_cbd.py [M-C]"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from vgc.db import connect
from vgc.ids import to_id

REG = sys.argv[1] if len(sys.argv) > 1 else "M-C"
PTS = ("hp_points", "attack_points", "defense_points",
       "sp_atk_points", "sp_def_points", "speed_points")
TYPES = {"move": "move", "held_item": "item", "ability": "ability",
         "stat_alignment": "nature", "stat_points": "spread"}  # teammate skipped


def parse_date(s):
    return datetime.strptime(s, "%d_%m_%Y").date()


root = Path("data/raw/cbd") / REG
landing = max((p for p in root.iterdir() if (p / "manifest.json").exists()),
              key=lambda p: json.loads((p / "manifest.json").read_text())["landed_at"])
docs = [json.loads(f.read_text()) for f in sorted((landing / "Doubles").glob("*.json"))]
latest = max(parse_date(e["date"]) for d in docs for e in d["daily"])

now = datetime.now(timezone.utc).replace(tzinfo=None)
rows, missing = [], []
for d in docs:
    entry = next((e for e in d["daily"] if parse_date(e["date"]) == latest), None)
    if entry is None:
        missing.append(d["showdownId"])
        continue
    pid = to_id(d["showdownId"])
    for r in entry["rows"]:
        dtype = TYPES.get(r["category"])
        if dtype is None:
            continue
        if dtype == "spread":
            value = "/".join(str(r[k]) for k in PTS)
        elif dtype == "nature":
            value = r["name"].strip().lower()
        else:
            value = to_id(r["name"])
        pct = float(r["percentage"].rstrip("%")) / 100
        rows.append(("cbd", REG, latest, pid, dtype, value, pct, now))

con = connect(read_only=False)
con.begin()
con.execute("DELETE FROM fact_usage_detail WHERE source = 'cbd' AND regulation = ?", [REG])
con.executemany("""INSERT INTO fact_usage_detail
    (source, regulation, snapshot_date, pokemon_id, detail_type, detail_value, pct, loaded_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", rows)
con.commit()

total = con.execute("SELECT count(*) FROM fact_usage_detail WHERE source='cbd' AND regulation=?",
                    [REG]).fetchone()[0]
print(f"landing={landing.name} date={latest} species={len(docs) - len(missing)} "
      f"rows={total} missing_date={missing[:5]}")
