"""Regulation calendar lookups (config/regulations.yaml)."""

from __future__ import annotations

from functools import lru_cache

import yaml

from vgc import REPO_ROOT


@lru_cache(maxsize=1)
def load() -> dict:
    with open(REPO_ROOT / "config" / "regulations.yaml") as f:
        return yaml.safe_load(f)


def current() -> str:
    return load()["current"]


def format_id(regulation: str, source: str) -> str:
    fid = load()["regulations"][regulation]["format_ids"].get(source)
    if not fid:
        raise ValueError(f"No {source} format id configured for {regulation}")
    return fid


def regulation_for_cbd_season(season: str) -> str:
    matches = [reg for reg, cfg in load()["regulations"].items() if season in (cfg.get("cbd_seasons") or [])]
    if len(matches) != 1:
        raise ValueError(f"CBD season {season!r} maps to {matches or 'no'} regulation(s); fix regulations.yaml")
    return matches[0]
