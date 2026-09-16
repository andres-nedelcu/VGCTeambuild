"""Land one dated championsbattledata (CBD) snapshot as raw JSON.

Layout: data/raw/cbd/{regulation}/{YYYY-MM-DD}/
    index.json            the /api index as received
    {format}/{id}.json    /api/battle/{format}/{id}?season=..&days=.. as received
    manifest.json         written LAST; its presence means the snapshot is complete

API rules (championsbattledata.com/api-rules): attribution for public use; caching OK,
but no public mirror. Keep raw files local.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from vgc import REPO_ROOT
from vgc.db import load_settings
from vgc.regulations import format_id, regulation_for_cbd_season

BASE_URL = "https://championsbattledata.com"
HEADERS = {"User-Agent": "vgc-teambuilding (personal, local use)"}
MAX_DAYS = 31  # API limit


def _get_json(session: requests.Session, url: str, params: dict | None = None, retries: int = 3) -> dict:
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries:
                raise RuntimeError(f"GET {url} {params} failed after {retries} tries: {exc}") from exc
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def ddmmyyyy_to_iso(d: str) -> str:
    return datetime.strptime(d, "%d_%m_%Y").date().isoformat()


def pick_folder(index: dict, season: str, date: str | None) -> tuple[str, int]:
    """Return (DD_MM_YYYY, days param) for the requested season/date. date=None means latest."""
    dates = [f.split("/")[1] for f in index["dailyDataFolders"] if f.split("/")[0] == season]  # newest first
    if not dates:
        raise ValueError(f"No daily folders for season {season}. Available: {index['dailyDataFolders']}")
    target = dates[0] if date is None else date
    if target not in dates:
        raise ValueError(f"{season}/{target} not in index. Available for {season}: {dates}")
    # +1 buffer in case a newer snapshot is published mid-run
    days = min(MAX_DAYS, dates.index(target) + 2)
    return target, days


def fetch_snapshot(season: str, date: str | None = None, fmt: str | None = None,
                   session: requests.Session | None = None, log=print) -> Path:
    regulation = regulation_for_cbd_season(season)
    fmt = fmt or format_id(regulation, "cbd")
    settings = load_settings()
    delay = float(settings.get("cbd", {}).get("request_delay_seconds", 1.0))
    session = session or requests.Session()

    index = _get_json(session, f"{BASE_URL}/api")
    target, days = pick_folder(index, season, date)
    out = REPO_ROOT / settings["raw_data_dir"] / "cbd" / regulation / ddmmyyyy_to_iso(target)
    if (out / "manifest.json").exists():
        raise FileExistsError(f"Snapshot already landed: {out}")

    ids = sorted(
        p["showdownId"] for p in index["pokemon"]
        if any(c.get("season") == season and c.get("date") == target and c.get("format") == fmt
               for c in p["battleDataCsvs"])
    )
    (out / fmt).mkdir(parents=True, exist_ok=True)
    if not (out / "index.json").exists():  # keep the first index if resuming
        (out / "index.json").write_text(json.dumps(index))
    log(f"{season}/{target} -> {out.relative_to(REPO_ROOT)}: {len(ids)} Pokémon, days={days}")

    fetched = skipped = 0
    for n, pid in enumerate(ids, 1):
        path = out / fmt / f"{pid}.json"
        if path.exists():  # resume an interrupted run
            skipped += 1
            continue
        data = _get_json(session, f"{BASE_URL}/api/battle/{fmt}/{pid}", {"season": season, "days": days})
        found = [d for d in data.get("daily", []) if d.get("season") == season and d.get("date") == target]
        if len(found) != 1 or not found[0].get("rows"):
            raise RuntimeError(f"{pid}: expected one non-empty {season}/{target} entry, got {len(found)}")
        path.write_text(json.dumps(data))
        fetched += 1
        if n % 25 == 0:
            log(f"  {n}/{len(ids)}")
        time.sleep(delay)

    manifest = {
        "source": "cbd", "regulation": regulation, "season": season, "cbd_date": target,
        "snapshot_date": ddmmyyyy_to_iso(target), "format": fmt, "days_param": days,
        "index_generated_at": index.get("generatedAt"), "pokemon_count": len(ids),
        "fetched": fetched, "skipped_existing": skipped,
        "landed_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    log(f"Done: fetched {fetched}, resumed/skipped {skipped}")
    return out
