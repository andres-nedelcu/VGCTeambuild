"""Load the pinned Showdown `champions` export (data/raw/showdown/...) into dim_* tables.

The raw folder is produced by scripts/export_showdown.js. This module never
downloads anything; it only reads immutable raw files.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from vgc import REPO_ROOT
from vgc.db import load_settings
from vgc.ids import to_id

DATA_SOURCE = "showdown_champions_mod"
SPREAD_TARGETS = {"allAdjacent", "allAdjacentFoes"}
EXCLUDED_TYPES = {"Stellar"}  # no Terastallization in Champions
# Showdown damageTaken codes -> multiplier
DAMAGE_CODE = {0: 1.0, 1: 2.0, 2: 0.5, 3: 0.0}


def raw_dir() -> Path:
    cfg = load_settings()["showdown"]
    folder = REPO_ROOT / cfg["raw_dir"]
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest["commit"] != cfg["commit"]:
        raise ValueError(
            f"Raw folder commit {manifest['commit']} != settings commit {cfg['commit']}"
        )
    if manifest["mod"] != cfg["mod"]:
        raise ValueError(f"Raw folder mod {manifest['mod']} != settings mod {cfg['mod']}")
    return folder


def _read(folder: Path, name: str) -> list[dict]:
    return json.loads((folder / f"{name}.json").read_text())


def build_pokemon(folder: Path, now: datetime) -> pd.DataFrame:
    rows = []
    for s in _read(folder, "species"):
        types = s["types"]
        bs = s["baseStats"]
        rows.append({
            "pokemon_id": to_id(s["name"]),
            "display_name": s["name"],
            "base_species_id": to_id(s["baseSpecies"]),
            "is_mega": bool(s["isMega"]),
            "type1": types[0],
            "type2": types[1] if len(types) > 1 else None,
            "hp": bs["hp"], "atk": bs["atk"], "def": bs["def"],
            "spa": bs["spa"], "spd": bs["spd"], "spe": bs["spe"],
            "abilities": s["abilities"],
            "data_source": DATA_SOURCE,
            "loaded_at": now,
            "is_nonstandard": s["isNonstandard"],
        })
    return pd.DataFrame(rows)


def build_moves(folder: Path) -> pd.DataFrame:
    rows = []
    for m in _read(folder, "moves"):
        acc = m["accuracy"]
        rows.append({
            "move_id": to_id(m["name"]),  # Hidden Power variants share Showdown id; names don't
            "display_name": m["name"],
            "type": m["type"],
            "category": m["category"],
            "base_power": m["basePower"],
            "accuracy": None if acc is True else acc,  # NULL = never misses
            "priority": m["priority"],
            "target": m["target"],
            "is_spread": m["target"] in SPREAD_TARGETS,
        })
    return pd.DataFrame(rows)


def build_items(folder: Path) -> tuple[pd.DataFrame, list[str]]:
    rows, ambiguous = [], []
    for i in _read(folder, "items"):
        stone = i["megaStone"] or {}
        formes = list(stone.values())
        if len(formes) > 1:
            ambiguous.append(f"{i['name']} -> {', '.join(formes)}")
        rows.append({
            "item_id": to_id(i["name"]),
            "display_name": i["name"],
            "is_mega_stone": bool(stone),
            # NULL when one stone serves several formes; resolve from the holder's forme instead
            "mega_forme_id": to_id(formes[0]) if len(formes) == 1 else None,
        })
    return pd.DataFrame(rows), ambiguous


def build_type_chart(folder: Path) -> pd.DataFrame:
    types = [t for t in _read(folder, "typechart") if t["name"] not in EXCLUDED_TYPES]
    names = {t["name"] for t in types}
    rows = []
    for t in types:
        for atk, code in t["damageTaken"].items():
            if atk in names:  # skip non-type keys like brn, sandstorm, prankster
                rows.append({"atk_type": atk, "def_type": t["name"], "multiplier": DAMAGE_CODE[code]})
    df = pd.DataFrame(rows)
    expected = len(names) ** 2
    if len(df) != expected:
        raise ValueError(f"Type chart has {len(df)} rows, expected {expected}")
    return df


def load(con: duckdb.DuckDBPyConnection) -> dict:
    """Replace all Showdown-sourced dim tables in one transaction. Returns load stats."""
    folder = raw_dir()
    now = datetime.now()
    pokemon = build_pokemon(folder, now)
    moves = build_moves(folder)
    items, ambiguous = build_items(folder)
    chart = build_type_chart(folder)

    frames = {"dim_pokemon": pokemon, "dim_move": moves, "dim_item": items, "dim_type_chart": chart}
    con.begin()
    try:
        con.execute("DELETE FROM dim_pokemon WHERE data_source = ?", [DATA_SOURCE])  # keep 'manual' rows
        for table in ("dim_move", "dim_item", "dim_type_chart"):
            con.execute(f"DELETE FROM {table}")
        for table, df in frames.items():
            con.register("_df", df)
            con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
            con.unregister("_df")
        con.commit()
    except Exception:
        con.rollback()
        raise
    return {"folder": folder, "counts": {t: len(df) for t, df in frames.items()}, "ambiguous_stones": ambiguous}
