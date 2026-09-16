"""Create (or update) the warehouse schema. Safe to rerun."""

from vgc import REPO_ROOT
from vgc.db import connect, warehouse_path


def main() -> None:
    con = connect(read_only=False)
    try:
        con.execute((REPO_ROOT / "sql" / "00_schema.sql").read_text())
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    finally:
        con.close()
    print(f"Warehouse ready at {warehouse_path()}")
    print(f"{len(tables)} tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
