"""Phase 0 / 1b: load pinned Showdown champions data into dim_* and print checks.

Usage: uv run python scripts/load_static.py
Safe to rerun: each run replaces the Showdown rows, so counts stay the same.
"""

from vgc import REPO_ROOT
from vgc.db import connect, run_sql_file
from vgc.ingest import static_showdown


def main() -> None:
    con = connect(read_only=False)
    try:
        run_sql_file(con, REPO_ROOT / "sql" / "00_schema.sql")  # idempotent; adds is_nonstandard
        stats = static_showdown.load(con)
        print(f"Loaded from {stats['folder'].relative_to(REPO_ROOT)}")

        print("\nRow counts (table: loaded / now in table)")
        for table, n in stats["counts"].items():
            total = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {n} / {total}")

        print("\nGarchomp-Mega-Z:")
        print(" ", con.execute("""
            SELECT pokemon_id, base_species_id, is_mega, type1, type2, spe, abilities, is_nonstandard
            FROM dim_pokemon WHERE pokemon_id = 'garchompmegaz'
        """).fetchone())

        print("\nType chart spot checks (expected 0.0, 0.5, 2.0, 1.0):")
        for atk, dfn in [("Ground", "Flying"), ("Fire", "Water"), ("Ice", "Dragon"), ("Fire", "Ground")]:
            m = con.execute(
                "SELECT multiplier FROM dim_type_chart WHERE atk_type = ? AND def_type = ?", [atk, dfn]
            ).fetchone()[0]
            print(f"  {atk} -> {dfn}: {m}")

        print("\nMove checks (expected Anchor Shot 90, Earthquake spread, Fake Out +3):")
        for row in con.execute("""
            SELECT move_id, base_power, is_spread, priority FROM dim_move
            WHERE move_id IN ('anchorshot', 'earthquake', 'fakeout') ORDER BY move_id
        """).fetchall():
            print(" ", row)

        print("\nMega stones:", con.execute("SELECT count(*) FROM dim_item WHERE is_mega_stone").fetchone()[0])
        print("Stones with several formes (mega_forme_id left NULL):")
        for s in stats["ambiguous_stones"]:
            print("  ", s)

        print("\nNot flagged nonstandard:", con.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_mega) FROM dim_pokemon WHERE is_nonstandard IS NULL"
        ).fetchone(), "(species, megas)")
    finally:
        con.close()


if __name__ == "__main__":
    main()
