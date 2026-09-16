"""Fetch and parse PokePaste (pokepast.es) teams.

Endpoints (checked in the pokepaste source, server.go):
  /{id}/raw   -> paste text only
  /{id}/json  -> {"paste", "title", "author", "notes"}  <- used; title becomes team_name
Paste IDs are 16 hex chars. Paste text uses CRLF line endings.

Champions exports reuse the "EVs:" line, but the values are Stat Points
(max 32 per stat, 66 total; Showdown sim/team-validator.ts and the M-C rule table).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from vgc import REPO_ROOT
from vgc.db import load_settings

BASE_URL = "https://pokepast.es"
HEADERS = {"User-Agent": "vgc-teambuilding (personal, local use)"}
PASTE_ID = re.compile(r"(?:pokepast\.es/)?([0-9a-f]{16})(?:[/?#].*)?$", re.I)
STAT_KEYS = {"hp": "hp", "atk": "atk", "def": "def", "spa": "spa", "spd": "spd", "spe": "spe"}
SP_MAX_PER_STAT, SP_MAX_TOTAL = 32, 66


def paste_id(url_or_id: str) -> str:
    m = PASTE_ID.search(url_or_id.strip())
    if not m:
        raise ValueError(f"Not a pokepast.es URL or 16-hex paste id: {url_or_id!r}")
    return m.group(1).lower()


def fetch(url_or_id: str, session: requests.Session | None = None) -> tuple[str, dict]:
    """Land /json once (pastes can't be edited), return (paste_id, payload)."""
    pid = paste_id(url_or_id)
    out = REPO_ROOT / load_settings()["raw_data_dir"] / "pokepaste" / pid
    if (out / "paste.json").exists():
        return pid, json.loads((out / "paste.json").read_text())
    resp = (session or requests).get(f"{BASE_URL}/{pid}/json", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("paste", "").strip():
        raise ValueError(f"Paste {pid} is empty")
    out.mkdir(parents=True, exist_ok=True)
    (out / "paste.json").write_text(json.dumps(payload, ensure_ascii=False))
    (out / "manifest.json").write_text(json.dumps(
        {"source": "pokepaste", "paste_id": pid, "fetched_at": datetime.now(timezone.utc).isoformat()}, indent=1))
    return pid, payload


def _parse_stats(text: str) -> dict[str, int]:
    stats = {}
    for part in text.split("/"):
        bits = part.strip().split()
        if len(bits) >= 2 and bits[1].lower() in STAT_KEYS:
            stats[STAT_KEYS[bits[1].lower()]] = int(bits[0])
    return stats


def _investment(values: dict[str, int]) -> dict:
    """Classify the EVs line: Champions stat points, or mainline EVs that can't be used as-is."""
    total = sum(values.values())
    is_sp = all(v <= SP_MAX_PER_STAT for v in values.values()) and total <= SP_MAX_TOTAL
    return {"unit": "sp" if is_sp else "ev", "values": values, "total": total}


def _parse_header(line: str) -> dict:
    """'Nickname (Species) (F) @ Item' -> species, nickname, gender, item (Showdown import rules)."""
    item = None
    if " @ " in line:
        line, item = line.rsplit(" @ ", 1)
        item = item.strip() or None
    line = line.strip()
    gender = None
    if line.endswith(" (M)") or line.endswith(" (F)"):
        gender, line = line[-2], line[:-4].strip()
    nickname = None
    if line.endswith(")") and "(" in line:
        start = line.rindex("(")
        nickname, species = line[:start].strip() or None, line[start + 1:-1].strip()
    else:
        species = line
    return {"species": species, "nickname": nickname, "gender": gender, "item": item}


def parse(text: str) -> list[dict]:
    """Parse a Showdown export into a list of sets (paste order)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sets = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines or lines[0].startswith("==="):  # skip teambuilder folder headers
            continue
        s = _parse_header(lines[0])
        s.update({"ability": None, "nature": None, "level": 50, "investment": None, "ivs": None, "moves": []})
        for line in lines[1:]:
            if line.startswith("Ability:"):
                s["ability"] = line.split(":", 1)[1].strip()
            elif line.startswith("Level:"):
                s["level"] = int(line.split(":", 1)[1])
            elif line.startswith(("EVs:", "SPs:")):
                s["investment"] = _investment(_parse_stats(line.split(":", 1)[1]))
            elif line.startswith("IVs:"):
                s["ivs"] = _parse_stats(line.split(":", 1)[1])
            elif line.endswith(" Nature"):
                s["nature"] = line[: -len(" Nature")].strip()
            elif line.startswith(("-", "~")):
                move = line[1:].strip()
                move = re.sub(r"^Hidden Power \[(\w+)\]$", r"Hidden Power \1", move)
                s["moves"].append(move.split(" / ")[0].strip())  # "A / B" slash options: keep the first
        if s["investment"] is None:
            s["investment"] = _investment({})
        sets.append(s)
    return sets
