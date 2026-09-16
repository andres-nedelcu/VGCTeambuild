"""Warehouse access. The only module that knows where the DuckDB file lives."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb
import yaml

from vgc import REPO_ROOT


def load_settings() -> dict:
    with open(REPO_ROOT / "config" / "settings.yaml") as f:
        return yaml.safe_load(f)


def warehouse_path() -> Path:
    return REPO_ROOT / load_settings()["warehouse_path"]


def connect(read_only: bool = True, path: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open the warehouse. Read-only by default; only refresh/init scripts should pass False."""
    db_path = Path(path) if path else warehouse_path()
    if read_only and not db_path.exists():
        raise FileNotFoundError(
            f"No warehouse at {db_path}. Run: uv run python scripts/init_warehouse.py"
        )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


@contextmanager
def session(read_only: bool = True) -> Iterator[duckdb.DuckDBPyConnection]:
    """Short-lived connection that always closes.

    Use this in the app instead of a long-lived cached connection: an open
    read-only connection in another process blocks refresh.py from writing.
    """
    con = connect(read_only=read_only)
    try:
        yield con
    finally:
        con.close()


def run_sql_file(con: duckdb.DuckDBPyConnection, file: Path) -> None:
    con.execute(file.read_text())


def run_sql_dir(con: duckdb.DuckDBPyConnection, directory: Path) -> list[Path]:
    """Run every .sql file in a directory in filename order. Returns the files run."""
    files = sorted(directory.glob("*.sql"))
    for f in files:
        run_sql_file(con, f)
    return files
