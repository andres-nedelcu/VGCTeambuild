"""Build the meta marts (sql/marts/*.sql) against the warehouse.

Usage: uv run python scripts/build_marts.py
Views only, so rerunning replaces every mart in place and nothing goes stale.
Numeric thresholds are substituted from defaults in config/settings.yaml, which
keeps them in one place instead of hard-coded in SQL.
"""
import re

from vgc import REPO_ROOT
from vgc.db import connect, load_settings

PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def render(sql: str, defaults: dict, name: str) -> str:
    for key in set(PLACEHOLDER.findall(sql)):
        if key not in defaults:
            raise SystemExit(f"{name}: no defaults.{key} in config/settings.yaml")
        sql = sql.replace("{{" + key + "}}", repr(float(defaults[key])))
    return sql


def main() -> None:
    defaults = load_settings()["defaults"]
    files = sorted((REPO_ROOT / "sql" / "marts").glob("*.sql"))
    if not files:
        raise SystemExit("No mart SQL files found in sql/marts/")

    con = connect(read_only=False)
    try:
        for path in files:
            con.execute(render(path.read_text(), defaults, path.name))
            print(f"  built {path.name}")
        marts = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'mart_%' ORDER BY 1").fetchall()]
        for mart in marts:
            n = con.execute(f'SELECT count(*) FROM "{mart}"').fetchone()[0]
            print(f"{mart}: {n} rows")
    finally:
        con.close()


if __name__ == "__main__":
    main()
