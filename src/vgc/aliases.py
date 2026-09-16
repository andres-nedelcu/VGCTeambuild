"""Source-specific ID fixes on top of vgc.ids.to_id (config/id_aliases.yaml)."""

from __future__ import annotations

from functools import lru_cache

import yaml

from vgc import REPO_ROOT
from vgc.ids import to_id


@lru_cache(maxsize=1)
def _aliases() -> dict:
    with open(REPO_ROOT / "config" / "id_aliases.yaml") as f:
        return yaml.safe_load(f) or {}


def resolve(source: str, raw: str | None) -> str | None:
    """to_id(raw), then apply the source's alias map."""
    if raw is None:
        return None
    key = to_id(raw)
    return (_aliases().get(source) or {}).get(key, key)
