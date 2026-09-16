"""Land Limitless VGC tournaments (details + standings) as raw JSON.

Layout: data/raw/limitless/{regulation}/{event_date}/{tournament_id}/
    details.json, standings.json, manifest.json (written LAST = complete)
Tournament list responses are kept in data/raw/limitless/_lists/ for audit.

Findings (Phase 0, 2026-09-16):
- No API key needed; limit is "50-in-5min", reported in the RateLimit header.
- Limitless has no M-C format yet; M-C events use format CUSTOM with the regulation
  in the name. Classification rules live in config/regulations.yaml (limitless:).
- Teamlist = list of {id, name, item, ability, attacks[], nature, tera}. Species key is
  `id` (slug, e.g. "indeedee-f"); `name` is a display name ("Indeedee ♀") and must not
  be used as a key. No stat points. Megas = base species + stone.
- placing is null for dropped players.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from vgc import REPO_ROOT
from vgc.db import load_settings
from vgc.regulations import load as load_regulations

BASE_URL = "https://play.limitlesstcg.com/api"
HEADERS = {"User-Agent": "vgc-teambuilding (personal, local use)"}
GAME = "VGC"


class Client:
    """Polite GET client that honours the IETF RateLimit header ('...; r=remaining; t=reset')."""

    def __init__(self, session: requests.Session | None = None, delay: float = 1.0, reserve: int = 2,
                 sleep=time.sleep, log=print):
        self.s = session or requests.Session()
        self.delay, self.reserve, self.sleep, self.log = delay, reserve, sleep, log
        self.requests = 0

    def get(self, path: str, **params):
        for attempt in range(1, 4):
            resp = self.s.get(f"{BASE_URL}{path}", params=params or None, headers=HEADERS, timeout=30)
            self.requests += 1
            remaining, reset = self._rate(resp.headers)
            if resp.status_code == 429:
                wait = reset or int(resp.headers.get("Retry-After", 60))
                self.log(f"  429 rate limited; sleeping {wait + 1}s")
                self.sleep(wait + 1)
                continue
            resp.raise_for_status()
            if remaining is not None and remaining <= self.reserve:
                self.log(f"  rate budget low (r={remaining}); sleeping {reset + 1}s")
                self.sleep((reset or 60) + 1)
            else:
                self.sleep(self.delay)
            return resp.json()
        raise RuntimeError(f"GET {path} still rate limited after 3 tries")

    @staticmethod
    def _rate(headers) -> tuple[int | None, int | None]:
        m = re.search(r"r=(\d+).*?t=(\d+)", headers.get("RateLimit", ""))
        return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _parse_dt(value) -> datetime | None:
    if value in (None, ""):
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def classify(tournament: dict) -> str | None:
    """Return the regulation a Limitless tournament belongs to, or None if unclear."""
    when = _parse_dt(tournament["date"])
    matches = []
    for reg, cfg in load_regulations()["regulations"].items():
        rule = cfg.get("limitless") or {}
        start, end = _parse_dt(cfg.get("start_utc")), _parse_dt(cfg.get("end_utc"))
        if (start and when < start) or (end and when > end):
            continue
        fmt = tournament.get("format")
        if fmt in (rule.get("formats") or []):
            matches.append(reg)
        elif fmt == "CUSTOM" and any(re.search(p, tournament.get("name", ""), re.I)
                                     for p in rule.get("custom_name_patterns") or []):
            matches.append(reg)
    return matches[0] if len(matches) == 1 else None


def tournament_dir(regulation: str, tournament: dict) -> Path:
    raw = REPO_ROOT / load_settings()["raw_data_dir"] / "limitless"
    return raw / regulation / tournament["date"][:10] / tournament["id"]


def discover(client: Client, pages: int = 1, limit: int = 100) -> list[dict]:
    listing = []
    for page in range(1, pages + 1):
        batch = client.get("/tournaments", game=GAME, limit=limit, page=page)
        listing.extend(batch)
        if len(batch) < limit:
            break
    audit = REPO_ROOT / load_settings()["raw_data_dir"] / "limitless" / "_lists"
    audit.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (audit / f"tournaments_{stamp}.json").write_text(json.dumps(listing))
    return listing


def land(client: Client, tournament: dict, regulation: str, log=print) -> str:
    """Land one tournament. Returns 'landed' or a skip reason."""
    out = tournament_dir(regulation, tournament)
    if (out / "manifest.json").exists():
        return "already landed"
    details = client.get(f"/tournaments/{tournament['id']}/details")
    if details.get("game") != GAME:
        return f"not {GAME}"
    if not details.get("decklists"):
        return "no teamlists"
    standings = client.get(f"/tournaments/{tournament['id']}/standings")
    with_lists = sum(1 for p in standings if p.get("decklist"))
    placed = sum(1 for p in standings if p.get("placing") is not None)
    if with_lists == 0:
        return "teamlists not published"
    if placed == 0:
        return "no placings yet (in progress?)"
    out.mkdir(parents=True, exist_ok=True)
    (out / "details.json").write_text(json.dumps(details, ensure_ascii=False))
    (out / "standings.json").write_text(json.dumps(standings, ensure_ascii=False))
    manifest = {
        "source": "limitless", "regulation": regulation, "tournament_id": tournament["id"],
        "name": details.get("name"), "event_date": tournament["date"][:10], "format": details.get("format"),
        "platform": details.get("platform"), "is_online": details.get("isOnline"),
        "players": len(standings), "with_teamlists": with_lists, "placed": placed,
        "landed_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    log(f"  landed {tournament['id']}  {with_lists}/{len(standings)} teamlists  {details.get('name')}")
    return "landed"


def fetch(regulation: str, max_new: int = 1, min_players: int = 16, pages: int = 1,
          tournament_id: str | None = None, client: Client | None = None, log=print) -> dict:
    settings = load_settings().get("limitless", {})
    client = client or Client(delay=float(settings.get("request_delay_seconds", 1.0)), log=log)
    if tournament_id:
        details = client.get(f"/tournaments/{tournament_id}/details")
        reg = classify(details)
        if reg != regulation:
            raise ValueError(f"{tournament_id} classifies as {reg!r}, not {regulation!r}: {details.get('name')}")
        candidates = [details]
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)  # skip events that may still be running
        listing = discover(client, pages=pages)
        candidates = [t for t in listing
                      if classify(t) == regulation and t["players"] >= min_players
                      and _parse_dt(t["date"]) < cutoff]
        candidates.sort(key=lambda t: t["players"], reverse=True)
        log(f"{len(listing)} listed, {len(candidates)} {regulation} candidates (>= {min_players}p, finished)")

    results: dict[str, list[str]] = {}
    landed = 0
    for t in candidates:
        if landed >= max_new:
            break
        reason = land(client, t, regulation, log=log)
        results.setdefault(reason, []).append(t["id"])
        landed += reason == "landed"
    log(f"Done: {landed} landed, {client.requests} requests; " +
        ", ".join(f"{k}: {len(v)}" for k, v in results.items() if k != "landed"))
    return results
