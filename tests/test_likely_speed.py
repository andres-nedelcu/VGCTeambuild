"""The "likely" Speed annotation: what a threat is actually built as.

Two things are under test. First, the nature -> Speed-direction mapping exists in
both SQL and Python, so it is pinned here exactly as champ_stat is pinned by
test_speed_tiers.py. Second, the annotation must stay inside the exact benchmark
band beside it -- it is an observation placed within provable bounds, never a
number that can contradict them.
"""

import re

import duckdb
import pytest

from vgc import REPO_ROOT
from vgc.db import session
from vgc.speed import LOW_CONFIDENCE, meta_speed
from vgc.stats import NATURES, NEUTRAL, nature_mod

REG = "M-C"
DIR_TO_MOD = {"plus": 1.1, "neutral": 1.0, "minus": 0.9}


@pytest.fixture(scope="module")
def macros() -> duckdb.DuckDBPyConnection:
    """In-memory DB with the Speed mart's scalar macros, warehouse not required."""
    sql = (REPO_ROOT / "sql" / "marts" / "03_meta_speed.sql").read_text()
    found = [m for m in re.findall(r"CREATE OR REPLACE MACRO[^;]+;", sql)
             if "AS TABLE" not in m]
    names = {m.split("MACRO", 1)[1].split("(", 1)[0].strip() for m in found}
    assert {"spe_nature_dir", "spe_nature_pct"} <= names, f"missing macros, found {names}"
    con = duckdb.connect()
    for macro in found:
        con.execute(macro)
    return con


@pytest.fixture(scope="module")
def meta():
    try:
        df = meta_speed(REG)
    except LookupError:
        pytest.skip("marts not built")
    if df.empty:
        pytest.skip("no meta rows")
    return df


def test_every_nature_maps_the_same_way_in_sql_and_python(macros):
    """All 25 natures, not a sample: a single disagreement is a wrong Speed."""
    all_natures = sorted(set(NATURES) | NEUTRAL)
    assert len(all_natures) == 25
    for nature in all_natures:
        direction = macros.execute("SELECT spe_nature_dir(?)", [nature]).fetchone()[0]
        assert DIR_TO_MOD[direction] == nature_mod(nature, "spe"), nature


def test_nature_pct_matches_the_modifier(macros):
    for direction, mod in DIR_TO_MOD.items():
        pct = macros.execute("SELECT spe_nature_pct(?)", [direction]).fetchone()[0]
        assert pct == round(mod * 100)


def test_a_plus_speed_nature_is_not_silently_neutral(macros):
    """Guards the mapping test: a macro returning 'neutral' for everything would
    still pass it for the 5 genuinely neutral natures."""
    assert macros.execute("SELECT spe_nature_dir('jolly')").fetchone()[0] == "plus"
    assert macros.execute("SELECT spe_nature_dir('brave')").fetchone()[0] == "minus"
    assert macros.execute("SELECT spe_nature_dir('hardy')").fetchone()[0] == "neutral"


def test_likely_speed_sits_inside_the_exact_band(meta):
    """The annotation can never contradict the benchmarks it is shown beside."""
    known = meta.dropna(subset=["likely_spe"])
    assert not known.empty
    assert (known["likely_spe"] >= known["spe_uninvested_neg"]).all()
    assert (known["likely_spe"] <= known["spe_max_plus"]).all()


def test_investment_and_shares_are_in_range(meta):
    known = meta.dropna(subset=["likely_spe"])
    assert known["likely_spe_sp"].between(0, 32).all()
    for col in ("likely_spe_sp_share", "likely_nature_share", "likely_confidence"):
        assert known[col].between(0, 1).all()


def test_confidence_is_the_weaker_of_the_two_shares(meta):
    """Deliberately not a product: the two distributions are never paired at source."""
    known = meta.dropna(subset=["likely_spe"])
    expected = known[["likely_spe_sp_share", "likely_nature_share"]].min(axis=1)
    assert (known["likely_confidence"] - expected).abs().max() < 1e-12


def test_most_of_the_meta_has_a_likely_speed(meta):
    """If coverage collapses, the column is decoration. It was 226/230 when built."""
    assert meta["likely_spe"].notna().mean() > 0.9


def test_the_low_confidence_case_actually_occurs(meta):
    """Guards the greying: a threshold nothing crosses is untested styling."""
    known = meta.dropna(subset=["likely_spe"])
    assert (known["likely_confidence"] < LOW_CONFIDENCE).any(), \
        "no split builds in the meta — is likely_confidence being computed?"


def test_the_marts_agree_with_the_python_stat_formula(meta):
    """SQL computes likely_spe; vgc.stats must reach the same number."""
    from vgc.stats import calc_stat
    with session() as con:
        rows = con.execute("""
            select t.spe, s.likely_spe_sp, s.likely_nature_dir, s.likely_spe
            from mart_meta_speed s join dim_pokemon t on t.pokemon_id = s.forme_id
            where s.likely_spe is not null limit 100
        """).fetchall()
    assert rows
    for base, sp, direction, likely in rows:
        assert likely == calc_stat(base, int(sp), DIR_TO_MOD[direction])
