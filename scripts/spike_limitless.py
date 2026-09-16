"""Phase 0 step 3 probe: discover Limitless IDs and the VGC teamlist shape. Prints only, writes nothing.

Usage: uv run python scripts/spike_limitless.py
"""

import json
from datetime import datetime, timezone

import requests

from vgc.regulations import load

BASE = "https://play.limitlesstcg.com/api"
H = {"User-Agent": "vgc-teambuilding (personal, local use)"}
S = requests.Session()


def get(path, **params):
    r = S.get(f"{BASE}{path}", params=params, headers=H, timeout=30)
    r.raise_for_status()
    return r


# 1. Games and formats
r = get("/games")
print("Rate-limit headers:", {k: v for k, v in r.headers.items() if "limit" in k.lower() or "retry" in k.lower()})
for g in r.json():
    if any(s in (g["id"] + g["name"]).lower() for s in ("vgc", "champ", "pok")):
        print(f"\nGAME {g['id']!r} ({g['name']}) metagame={g.get('metagame')}")
        print("  formats:", g.get("formats"))
        print("  platforms:", g.get("platforms"))

# 2. Recent VGC tournaments inside the M-C window
start = datetime.fromisoformat(str(load()["regulations"]["M-C"]["start_utc"]).replace("Z", "+00:00"))
tours = get("/tournaments", game="VGC", limit=100).json()
print(f"\n{len(tours)} most recent VGC tournaments; formats seen:",
      sorted({t['format'] for t in tours}))
in_window = [t for t in tours
             if datetime.fromisoformat(t["date"].replace("Z", "+00:00")) >= start and t["players"] >= 16]
print(f"{len(in_window)} since {start:%Y-%m-%d} with >=16 players:")
for t in in_window[:15]:
    print(f"  {t['date'][:10]} {t['format']:<10} {t['players']:>4}p  {t['id']}  {t['name'][:50]}")

# 3. First one with public teamlists: details + standings shape
for t in in_window:
    d = get(f"/tournaments/{t['id']}/details").json()
    if not d.get("decklists"):
        continue
    print("\nDETAILS keys:", sorted(d))
    print("  platform:", d.get("platform"), "isOnline:", d.get("isOnline"),
          "phases:", d.get("phases"), "specialRules:", d.get("specialRules"))
    st = get(f"/tournaments/{t['id']}/standings").json()
    with_list = [p for p in st if p.get("decklist")]
    print(f"STANDINGS: {len(st)} players, {len(with_list)} with teamlists; row keys:", sorted(st[0]))
    if with_list:
        p = with_list[0]
        print(f"  placing={p['placing']} record={p['record']} drop={p.get('drop')} deck={p.get('deck')}")
        print("  decklist type:", type(p["decklist"]).__name__)
        print(json.dumps(p["decklist"], indent=1, ensure_ascii=False)[:2500])
        break
else:
    print("\nNo M-C tournament with teamlists in the last 100 VGC events.")
