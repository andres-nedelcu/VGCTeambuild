"""Load dim_ability_type_modifier from config/ability_type_modifiers.yaml (full replace).

Fails loudly on unknown types, multipliers outside {0, 0.5}, or abilities
not found on any Champions-legal species or Mega.
"""

from __future__ import annotations

import sys

import yaml

from vgc import REPO_ROOT
from vgc.db import connect
from vgc.ids import to_id
from vgc.typechart import normalize_type

SEED = REPO_ROOT / "config" / "ability_type_modifiers.yaml"
ALLOWED = {0.0, 0.5}

LEGAL_ABILITIES_SQL = """
    with legal as (
        select * from dim_pokemon
        where is_nonstandard is null
           or (is_mega and base_species_id in
               (select pokemon_id from dim_pokemon where is_nonstandard is null))
    )
    select distinct unnest(abilities) from legal
"""


def read_seed() -> list[tuple[str, str, float]]:
    data = yaml.safe_load(SEED.read_text())
    rows = []
    for ability, mods in data.items():
        for atk, mult in mods.items():
            m = float(mult)
            if m not in ALLOWED:
                raise ValueError(f"{ability}/{atk}: multiplier {m} not in {sorted(ALLOWED)}")
            rows.append((to_id(ability), normalize_type(atk), m))
    return rows


def main() -> int:
    rows = read_seed()
    con = connect(read_only=False)
    try:
        legal = {to_id(r[0]) for r in con.execute(LEGAL_ABILITIES_SQL).fetchall()}
        missing = sorted({a for a, _, _ in rows} - legal)
        if missing:
            print(f"ERROR: not on any legal species/Mega: {missing}")
            return 1

        con.execute("begin")
        con.execute("delete from dim_ability_type_modifier")
        con.executemany(
            "insert into dim_ability_type_modifier (ability_id, atk_type, multiplier) values (?, ?, ?)",
            rows,
        )
        con.execute("commit")
        n = con.execute("select count(*) from dim_ability_type_modifier").fetchone()[0]
        print(f"dim_ability_type_modifier: {n} rows from {SEED.relative_to(REPO_ROOT)}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
