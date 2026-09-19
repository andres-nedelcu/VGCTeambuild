"""Phase A exit check for brief 6.2: which pokemon_ids have a gen5 sprite on Showdown?

Usage: uv run python scripts/check_sprite_coverage.py [--delay 0.15]
Read-only on the warehouse, and downloads nothing: HEAD requests only.

Naming matters more than it looks. Showdown's sprite files are NOT named by
pokemon_id. They hyphenate the base species from its forme, and concatenate
everything after that first separator:

    salamencemega     -> salamence-mega
    charizardmegay    -> charizard-megay      (not charizard-mega-y)
    taurospaldeaaqua  -> tauros-paldeaaqua
    rotomheat         -> rotom-heat

dim_pokemon.base_species_id gives this directly, with no string munging of
display names. Using pokemon_id as the filename reports ~86 false misses --
every Mega and every post-gen5 regional forme -- which is not a coverage
problem, just a wrong URL.
"""

import argparse
import json
import time

import requests

from vgc import REPO_ROOT
from vgc.db import connect

SPRITE_URL = "https://play.pokemonshowdown.com/sprites/gen5/{name}.png"
REPORT_PATH = REPO_ROOT / "data" / "sprites" / "coverage.json"


def sprite_name(pokemon_id: str, base_species_id: str | None) -> str:
    """Showdown's sprite filename: base species, one hyphen, forme suffix."""
    base = base_species_id or pokemon_id
    if pokemon_id == base or not pokemon_id.startswith(base):
        return pokemon_id
    return f"{base}-{pokemon_id[len(base):]}"


def collect(con) -> dict[str, str]:
    """pokemon_id -> sprite name, for every Pokemon the app can draw.

    Formes alone are not enough. The Cores tab works at species grain -- you pick a
    species and the stone is a later build choice -- so a meta row for
    Charizard-Mega-Y still needs a plain Charizard sprite beside its core. Base
    species are therefore pulled in alongside the formes.
    """
    rows = con.execute("""
        SELECT DISTINCT p.pokemon_id, p.base_species_id
        FROM dim_pokemon p
        WHERE p.pokemon_id IN (SELECT forme_id FROM mart_meta_top)
           OR p.pokemon_id IN (SELECT species_id FROM mart_meta_top)
           OR p.pokemon_id IN (SELECT base_species_id FROM dim_pokemon
                               WHERE pokemon_id IN (SELECT forme_id FROM mart_meta_top))
           OR p.pokemon_id IN (SELECT pokemon_id FROM my_team)
        ORDER BY 1
    """).fetchall()
    return {pid: sprite_name(pid, base) for pid, base in rows}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.15, help="seconds between requests")
    args = ap.parse_args()

    con = connect(read_only=True)
    try:
        wanted = collect(con)
    finally:
        con.close()

    session = requests.Session()
    hits, misses = {}, {}
    for i, (pokemon_id, name) in enumerate(wanted.items()):
        code = session.head(SPRITE_URL.format(name=name), timeout=10).status_code
        (hits if code == 200 else misses)[pokemon_id] = name
        if i < len(wanted) - 1:
            time.sleep(args.delay)

    print(f"{len(hits)}/{len(wanted)} formes have a gen5 sprite.")
    if misses:
        print(f"\n{len(misses)} need a fallback:")
        for pokemon_id, name in sorted(misses.items()):
            print(f"  {pokemon_id:20s} ({name})")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(
        {"checked": len(wanted), "sprites": hits, "missing": misses}, indent=2) + "\n")
    print(f"\nReport written to {REPORT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
