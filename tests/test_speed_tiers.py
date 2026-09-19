"""Pin the Champions Speed math to a reference speed-tier table.

Columns: max investment +Spe nature, max investment neutral, uninvested neutral,
uninvested -Spe nature, then Choice Scarf applied to the first two.
Both implementations (vgc.stats.calc_stat and the SQL macros the marts use) are
checked against the same table so they cannot drift apart.
"""
import re

import duckdb
import pytest

from vgc import REPO_ROOT
from vgc.stats import calc_stat, scarf

# base Speed -> (max+, max neutral, uninvested, uninvested -Spe, max+ scarf, neutral scarf)
REFERENCE = {
    151: (223, 203, 171, 153, 334, 304), 150: (222, 202, 170, 153, 333, 303),
    145: (216, 197, 165, 148, 324, 295), 142: (213, 194, 162, 145, 319, 291),
    135: (205, 187, 155, 139, 307, 280), 134: (204, 186, 154, 138, 306, 279),
    130: (200, 182, 150, 135, 300, 273), 126: (195, 178, 146, 131, 292, 267),
    125: (194, 177, 145, 130, 291, 265), 124: (193, 176, 144, 129, 289, 264),
    123: (192, 175, 143, 128, 288, 262), 122: (191, 174, 142, 127, 286, 261),
    121: (190, 173, 141, 126, 285, 259), 120: (189, 172, 140, 126, 283, 258),
    119: (188, 171, 139, 125, 282, 256), 118: (187, 170, 138, 124, 280, 255),
    117: (185, 169, 137, 123, 277, 253), 116: (184, 168, 136, 122, 276, 252),
    115: (183, 167, 135, 121, 274, 250), 113: (181, 165, 133, 119, 271, 247),
    112: (180, 164, 132, 118, 270, 246), 111: (179, 163, 131, 117, 268, 244),
    110: (178, 162, 130, 117, 267, 243), 109: (177, 161, 129, 116, 265, 241),
    108: (176, 160, 128, 115, 264, 240), 106: (173, 158, 126, 113, 259, 237),
    105: (172, 157, 125, 112, 258, 235), 104: (171, 156, 124, 111, 256, 234),
    103: (170, 155, 123, 110, 255, 232), 102: (169, 154, 122, 109, 253, 231),
    101: (168, 153, 121, 108, 252, 229),
}

@pytest.mark.parametrize("base,expected", sorted(REFERENCE.items()))
def test_calc_stat_matches_reference_table(base, expected):
    max_plus, max_neutral, uninvested, negative = expected[:4]
    assert calc_stat(base, 32, 1.1) == max_plus
    assert calc_stat(base, 32, 1.0) == max_neutral
    assert calc_stat(base, 0, 1.0) == uninvested
    assert calc_stat(base, 0, 0.9) == negative


@pytest.mark.parametrize("base,expected", sorted(REFERENCE.items()))
def test_choice_scarf_matches_reference_table(base, expected):
    assert scarf(calc_stat(base, 32, 1.1)) == expected[4]
    assert scarf(calc_stat(base, 32, 1.0)) == expected[5]


def _macro_connection() -> duckdb.DuckDBPyConnection:
    """In-memory DB carrying the scalar stat macros defined by the Speed mart.

    Table macros in the same file are skipped on purpose: they read warehouse tables
    and carry {{...}} placeholders that build_marts substitutes, so neither belongs
    in a bare in-memory connection. Only the stat arithmetic is under test here.
    """
    sql = (REPO_ROOT / "sql" / "marts" / "03_meta_speed.sql").read_text()
    macros = [m for m in re.findall(r"CREATE OR REPLACE MACRO[^;]+;", sql)
              if "AS TABLE" not in m]
    names = {m.split("MACRO", 1)[1].split("(", 1)[0].strip() for m in macros}
    assert {"champ_stat", "champ_scarf"} <= names, f"stat macros missing, found {names}"
    con = duckdb.connect()
    for macro in macros:
        con.execute(macro)
    return con


def test_sql_macros_match_python():
    """The marts compute Speed in SQL; it must agree with vgc.stats everywhere."""
    con = _macro_connection()
    try:
        for base in range(1, 201):
            for sp in (0, 16, 32):
                for pct in (90, 100, 110):
                    got = con.execute("SELECT champ_stat(?, ?, ?)", [base, sp, pct]).fetchone()[0]
                    assert got == calc_stat(base, sp, pct / 100), (base, sp, pct)
            scarfed = con.execute("SELECT champ_scarf(?)", [base]).fetchone()[0]
            assert scarfed == scarf(base), base
    finally:
        con.close()
