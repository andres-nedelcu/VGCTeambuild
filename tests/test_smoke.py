"""Smoke tests: the schema builds and the package imports."""

import duckdb

from vgc import REPO_ROOT


def test_schema_builds_in_memory():
    con = duckdb.connect(":memory:")
    sql = (REPO_ROOT / "sql" / "00_schema.sql").read_text()
    con.execute(sql)
    con.execute(sql)  # idempotent
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    assert {"dim_pokemon", "fact_usage", "my_team"} <= tables


def test_settings_load():
    from vgc.db import load_settings

    assert load_settings()["defaults"]["top_n"] == 20
