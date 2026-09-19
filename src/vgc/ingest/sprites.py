"""Fetch and cache gen5 sprites for brief 6.2, with a fallback for the 10 formes
that have none (see docs/briefs/6.2-sprites.md Phase A).

Everything the app draws ends up as one PNG per pokemon_id under
data/sprites/gen5/ — real Showdown art for the 221 that have it, and a
composited fallback for the 10 that don't. The app never has to know which is
which at render time.

Fallback rule: base species sprite plus a small gold "M" badge (every miss in
Phase A's report is a Mega). If the Mega's typing differs from the base
species it's borrowing art from, an orange ring is added as a second signal —
the badge alone doesn't say "and the types are different too". Checked against
dim_pokemon, not hardcoded to the two species HANDOFF.md §6.2 named: that
Barbaracle-Mega (Rock/Fighting vs base Rock/Water) also differs was found this
way, not called out in the brief.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from vgc import REPO_ROOT
from vgc.db import session

SPRITE_URL = "https://play.pokemonshowdown.com/sprites/gen5/{name}.png"
SPRITE_DIR = REPO_ROOT / "data" / "sprites" / "gen5"
COVERAGE_PATH = REPO_ROOT / "data" / "sprites" / "coverage.json"

BADGE_COLOR = (234, 179, 8, 255)     # gold — "this art is a stand-in"
BADGE_TEXT = (66, 45, 0, 255)
MISMATCH_RING = (234, 88, 12, 255)   # orange — "and the types differ too"


def _get(session_: requests.Session, name: str) -> bytes | None:
    resp = session_.get(SPRITE_URL.format(name=name), timeout=10)
    return resp.content if resp.status_code == 200 else None


def _base_species(con, pokemon_id: str) -> tuple[str, tuple[str | None, str | None]]:
    row = con.execute(
        "select base_species_id, type1, type2 from dim_pokemon where pokemon_id = ?",
        [pokemon_id],
    ).fetchone()
    if row is None:
        raise LookupError(f"{pokemon_id} not in dim_pokemon")
    base_id, t1, t2 = row
    base_row = con.execute(
        "select type1, type2 from dim_pokemon where pokemon_id = ?", [base_id]
    ).fetchone()
    if base_row is None:
        raise LookupError(f"base species {base_id!r} of {pokemon_id} not in dim_pokemon")
    return base_id, base_row


def build_fallback(base_path: Path, dest: Path, *, mismatched: bool) -> None:
    """Base sprite + Mega badge, with an orange ring if typing differs from base."""
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(img, (0, 0), img)
    draw = ImageDraw.Draw(canvas)

    if mismatched:
        ring = max(2, w // 24)
        draw.rectangle([ring // 2, ring // 2, w - ring // 2 - 1, h - ring // 2 - 1],
                       outline=MISMATCH_RING, width=ring)

    badge = max(w, h) // 3
    cx, cy = w - badge // 2 - 1, badge // 2 + 1
    draw.ellipse([cx - badge // 2, cy - badge // 2, cx + badge // 2, cy + badge // 2],
                 fill=BADGE_COLOR, outline=(255, 255, 255, 255), width=max(1, badge // 12))
    draw.text((cx, cy), "M", fill=BADGE_TEXT, anchor="mm")

    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest)


def fetch_all(delay: float = 0.15, session_: requests.Session | None = None,
             log=print) -> dict[str, int]:
    """Download every real sprite in coverage.json, then build fallbacks for the
    misses. Idempotent: anything already on disk — real or fallback — is skipped.
    """
    coverage = json.loads(COVERAGE_PATH.read_text())
    session_ = session_ or requests.Session()

    downloaded = skipped = built = 0

    for pokemon_id, name in coverage["sprites"].items():
        dest = SPRITE_DIR / f"{pokemon_id}.png"
        if dest.exists():
            skipped += 1
            continue
        content = _get(session_, name)
        if content is None:
            log(f"  warning: {pokemon_id} ({name}) reported a sprite but the download failed")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        downloaded += 1
        time.sleep(delay)

    with session() as con:
        for pokemon_id in coverage["missing"]:
            dest = SPRITE_DIR / f"{pokemon_id}.png"
            if dest.exists():
                skipped += 1
                continue

            base_id, (base_t1, base_t2) = _base_species(con, pokemon_id)
            forme_types = con.execute(
                "select type1, type2 from dim_pokemon where pokemon_id = ?", [pokemon_id]
            ).fetchone()

            base_path = SPRITE_DIR / f"{base_id}.png"
            if not base_path.exists():
                content = _get(session_, base_id)
                if content is None:
                    log(f"  warning: no base sprite for {pokemon_id} (base {base_id}); skipped")
                    continue
                base_path.parent.mkdir(parents=True, exist_ok=True)
                base_path.write_bytes(content)
                downloaded += 1
                time.sleep(delay)

            mismatched = set(forme_types) != {base_t1, base_t2}
            build_fallback(base_path, dest, mismatched=mismatched)
            built += 1

    return {"downloaded": downloaded, "skipped": skipped, "built": built}
