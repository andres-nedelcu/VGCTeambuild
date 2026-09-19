"""Read-only sprite lookup for the app. Cached PNGs only — never a network call.

data/sprites/gen5/<pokemon_id>.png holds real Showdown art for most formes and
a composited fallback (see vgc.ingest.sprites) for the ones with none; the app
doesn't need to tell them apart.
"""

from __future__ import annotations

import base64
from pathlib import Path

from vgc import REPO_ROOT

SPRITE_DIR = REPO_ROOT / "data" / "sprites" / "gen5"


def sprite_path(pokemon_id: str) -> Path | None:
    path = SPRITE_DIR / f"{pokemon_id}.png"
    return path if path.exists() else None


def data_uri(pokemon_id: str) -> str | None:
    """Base64 PNG data URI, for st.column_config.ImageColumn (local paths aren't
    supported there, and this stays offline with no static file serving to set up).
    """
    path = sprite_path(pokemon_id)
    if path is None:
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()
