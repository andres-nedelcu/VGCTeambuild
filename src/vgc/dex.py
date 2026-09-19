"""Any Pokémon in the dex, not just the six on your team.

Everything else in this project is anchored to a loaded paste: `incoming` asks what
the meta does to *your* team, `outgoing` what *your* team does to the meta, `suggest`
what to add to *your* team. That is the right default and it is not what you want
when an unfamiliar name appears in front of you and the question is simply "what is
that thing, and what does it do to me".

Two jobs here, and neither of them computes damage — that is `vgc.matchup`:

  WHICH POKEMON     `dex_entries` is the searchable population, and it is not all
                    1,518 rows of dim_pokemon. Most of those are `is_nonstandard`
                    ('Past', 'CAP', 'Future'), unplayable in Champions, and putting
                    them in a picker means typing past four Venusaur formes to reach
                    a legal one. The rule is standard, PLUS anything that actually
                    appears in tournament or build data, so a straggler the dex flags
                    as Past but people demonstrably run is never hidden.

  WHAT THE META RUNS  `profile` — usage, rank, and the item / ability / move / nature
                    / spread breakdowns. All of it is already computed in the marts;
                    this is a read, not a calculation.

Usage and rank move with the meta filter, because they come from the `meta_top` macro
the rest of the app uses. The build breakdowns do not: `mart_build_detail` is a
Champions ladder snapshot with no tournament dimension to filter on, which is the
same limit the Spreads and Damage tabs already carry.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from vgc.db import session
from vgc.ids import to_id
from vgc.matchup import Build
from vgc.metafilter import MetaFilter
from vgc.stats import STATS

BUILD_CMD = "uv run python scripts/build_marts.py"

# The detail_types carried by mart_build_detail, in the order a player reads them:
# what it holds, what it is, what it does, then the numbers behind that.
ITEM, ABILITY, MOVE, NATURE, SPREAD = "item", "ability", "move", "nature", "spread"
DETAIL_TYPES = (ITEM, ABILITY, MOVE, NATURE, SPREAD)


@dataclass(frozen=True)
class DexEntry:
    pokemon_id: str
    display_name: str
    types: tuple[str, ...]
    abilities: tuple[str, ...]       # ability ids, in dex order
    base: dict[str, int]             # hp / atk / def / spa / spd / spe
    is_mega: bool
    base_species_id: str

    @property
    def bst(self) -> int:
        return sum(self.base.values())


_ENTRY_COLUMNS = """
    p.pokemon_id, p.display_name, p.base_species_id, p.is_mega, p.type1, p.type2,
    p.hp, p.atk, p."def", p.spa, p.spd, p.spe, p.abilities
"""


def _to_entry(row) -> DexEntry:
    (pid, name, base_species, is_mega, t1, t2, *stats, abilities) = row
    return DexEntry(
        pokemon_id=pid,
        display_name=name,
        types=tuple(t for t in (t1, t2) if t),
        abilities=tuple(to_id(a) for a in (abilities or [])),
        base=dict(zip(STATS, (int(s) for s in stats))),
        is_mega=bool(is_mega),
        base_species_id=base_species,
    )


@lru_cache(maxsize=1)
def dex_entries() -> tuple[DexEntry, ...]:
    """Every Pokémon worth being able to pick, alphabetically.

    "Worth picking" is standard-legal OR seen in the data. The second half of that
    matters: one species in the landed tournament set is flagged `Past` and is
    genuinely being brought to events, and a picker that hides what people are
    playing is worse than one with a few extra rows.
    """
    seen_in_data = """
        or p.pokemon_id in (select forme_id from mart_meta_top)
        or p.pokemon_id in (select pokemon_id from mart_build_detail)
    """
    with session() as con:
        def fetch(extra: str) -> list:
            return con.execute(f"""
                select {_ENTRY_COLUMNS} from dim_pokemon p
                where p.is_nonstandard is null {extra}
                order by p.display_name
            """).fetchall()
        try:
            rows = fetch(seen_in_data)
        except Exception:  # noqa: BLE001 — marts not built yet; the legal dex still works
            rows = fetch("")
    return tuple(_to_entry(r) for r in rows)


@lru_cache(maxsize=1)
def ability_names() -> dict[str, str]:
    """ability id -> how it is written, e.g. grassysurge -> 'Grassy Surge'.

    Ids have no separator in them, so a display name cannot be recovered from one by
    title-casing: `grassysurge` comes back as "Grassysurge". dim_pokemon.abilities
    holds the real spelling, so the map is built from there once.
    """
    with session() as con:
        rows = con.execute(
            "select abilities from dim_pokemon where abilities is not null").fetchall()
    return {to_id(a): a for (names,) in rows for a in (names or [])}


def entry(pokemon_id: str) -> DexEntry:
    """One Pokémon by id, whether or not it is in the pickable population."""
    for e in dex_entries():
        if e.pokemon_id == pokemon_id:
            return e
    with session() as con:
        row = con.execute(
            f"select {_ENTRY_COLUMNS} from dim_pokemon p where p.pokemon_id = ?",
            [pokemon_id]).fetchone()
    if not row:
        raise LookupError(f"No Pokémon {pokemon_id!r} in dim_pokemon")
    return _to_entry(row)


def clear_cache() -> None:
    dex_entries.cache_clear()
    ability_names.cache_clear()
    _meta_species.cache_clear()
    _detail_keys.cache_clear()


def usage_map(regulation: str, filt: MetaFilter | None = None) -> dict[str, tuple[float, int]]:
    """forme_id -> (usage share, rank) under this meta filter."""
    filt = filt or MetaFilter()
    with session() as con:
        try:
            rows = con.execute(f"""
                select forme_id, forme_usage_pct, species_rank
                from {filt.call('meta_top')}
            """, filt.params(regulation)).fetchall()
        except Exception as e:  # noqa: BLE001
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e
    return {fid: (float(pct), int(rank)) for fid, pct, rank in rows}


def picker_order(regulation: str, filt: MetaFilter | None = None,
                 entries: Sequence[DexEntry] | None = None) -> list[DexEntry]:
    """The pickable dex, most-used first, then alphabetically.

    A 394-row selectbox is searchable, but it still opens on *something*, and what it
    opens on should be what you are most likely to be looking up. Ordering by usage
    puts the meta at the top and costs nothing: typing still filters the whole list.
    """
    entries = entries if entries is not None else dex_entries()
    try:
        usage = usage_map(regulation, filt)
    except LookupError:
        return list(entries)
    return sorted(entries, key=lambda e: (-usage.get(e.pokemon_id, (0.0, 0))[0],
                                          e.display_name))


@dataclass(frozen=True)
class Profile:
    """What the meta knows about one Pokémon. Presentation data, already computed."""

    entry: DexEntry
    usage_pct: float | None          # None = it does not appear in the meta at all
    rank: int | None
    sample_size: int
    details: dict[str, tuple[tuple[str, float], ...]]   # detail_type -> ((value, pct), ...)

    @property
    def in_meta(self) -> bool:
        return self.usage_pct is not None

    def top(self, detail_type: str) -> tuple[str, float] | None:
        """The single most common value of a detail, or None if there is no data."""
        rows = self.details.get(detail_type) or ()
        return rows[0] if rows else None

    def has_builds(self) -> bool:
        return any(self.details.get(d) for d in DETAIL_TYPES)


def profile(pokemon_id: str, regulation: str,
            filt: MetaFilter | None = None) -> Profile:
    """Usage, rank and build breakdowns for one Pokémon.

    Build detail is keyed by SPECIES while usage is keyed by forme, which is the same
    split `vgc.outgoing` handles: Salamence-Mega's damage uses the Mega's stats and
    types, but the item and spread people run come from the Salamence row.
    """
    e = entry(pokemon_id)
    filt = filt or MetaFilter()
    try:
        usage = usage_map(regulation, filt)
    except LookupError:
        usage = {}
    usage_pct, rank = usage.get(pokemon_id, (None, None))

    with session() as con:
        try:
            sample = con.execute(
                f"select max(sample_size) from {filt.call('meta_top')}",
                filt.params(regulation)).fetchone()
            rows = con.execute("""
                select detail_type, detail_value, pct
                from mart_build_detail
                where pokemon_id = ? and regulation = ?
                order by detail_type, pct desc, detail_value
            """, [build_key(e), regulation]).fetchall()
        except Exception:  # noqa: BLE001 — a dex entry with no meta data is normal
            sample, rows = (0,), []

    details: dict[str, list[tuple[str, float]]] = {d: [] for d in DETAIL_TYPES}
    for detail_type, value, pct in rows:
        details.setdefault(detail_type, []).append((value, float(pct)))

    return Profile(
        entry=e,
        usage_pct=usage_pct,
        rank=rank,
        sample_size=int(sample[0] or 0) if sample else 0,
        details={k: tuple(v) for k, v in details.items()},
    )


# --- from what the meta runs, to something the calculator can use ----------------

def parse_spread(text: str) -> dict[str, int]:
    """'32/32/0/0/2/0' -> SP per stat. Slot order is HP/Atk/Def/SpA/SpD/Spe."""
    parts = (text or "").split("/")
    if len(parts) != len(STATS):
        raise ValueError(f"Not a spread: {text!r}")
    return {stat: int(p) for stat, p in zip(STATS, parts)}


def format_spread(sp: dict[str, int]) -> str:
    return "/".join(str(sp.get(stat, 0)) for stat in STATS)


@lru_cache(maxsize=1)
def _meta_species() -> dict[str, str]:
    """forme_id -> the species_id the meta marts use. Empty if they are not built."""
    with session() as con:
        try:
            return dict(con.execute(
                "select forme_id, species_id from mart_meta_top").fetchall())
        except Exception:  # noqa: BLE001
            return {}


@lru_cache(maxsize=1)
def _detail_keys() -> frozenset[str]:
    with session() as con:
        try:
            return frozenset(r[0] for r in con.execute(
                "select distinct pokemon_id from mart_build_detail").fetchall())
        except Exception:  # noqa: BLE001
            return frozenset()


def build_key(e: DexEntry) -> str:
    """Which `mart_build_detail` row holds this forme's builds.

    NOT `base_species_id`, which is the trap here: dim_pokemon collapses regional
    formes onto their original (arcaninehisui -> arcanine, indeedeef -> indeedee)
    while the build marts keep them apart and hold BOTH keys. Reading Arcanine-Hisui's
    item and nature off the Kantonian row returns confident, wrong numbers — it was
    Adamant against a true Jolly, worth 10% of its Attack.

    The meta's own `species_id` is the correct grouping and the one `vgc.outgoing`
    and `vgc.incoming` already use: it folds a Mega into its base species and leaves
    regional formes alone. Outside the meta there is no such row, so a Mega falls
    back to its base species and everything else is its own key.
    """
    species = _meta_species().get(e.pokemon_id)
    if species:
        return species
    if e.is_mega:
        return e.base_species_id
    return e.pokemon_id if e.pokemon_id in _detail_keys() else e.base_species_id


def likely_ability(e: DexEntry, regulation: str) -> str | None:
    """The ability to assume for a Pokémon you did not build.

    Same rule as `vgc.offense._threat_ability`, and `tests/test_dex.py` pins that the
    two agree across the whole meta rather than trusting the resemblance: a Mega's
    ability is fixed by its forme, otherwise take the most common build's, otherwise
    fall back to the first the dex lists.
    """
    if e.is_mega and len(e.abilities) == 1:
        return e.abilities[0]
    with session() as con:
        row = con.execute("""
            select detail_value from mart_build_detail
            where pokemon_id = ? and regulation = ? and detail_type = 'ability'
            order by pct desc, detail_value limit 1
        """, [build_key(e), regulation]).fetchone()
    common = to_id(row[0]) if row and row[0] else None
    if common and common in e.abilities:
        return common
    return e.abilities[0] if e.abilities else None


def marginal_spread(pokemon_id: str, regulation: str,
                    filt: MetaFilter | None = None) -> dict[str, int]:
    """Modal investment computed one stat at a time — what the Damage tab uses.

    These are MARGINALS, not a spread. Each slot is the most common value for that
    slot alone, so the six together are frequently a combination nobody runs, and
    they can add up past the 66 SP cap: Farigiraf's marginals sum to 71. For damage
    that never mattered, because only one stat is read per hit. For a build panel it
    matters a great deal, which is why `meta_build` defaults to a real spread and
    this is opt-in.
    """
    filt = filt or MetaFilter()
    with session() as con:
        try:
            rows = con.execute(
                f"select stat, sp from {filt.call('meta_investment')} where pokemon_id = ?",
                filt.params(regulation) + [pokemon_id]).fetchall()
        except Exception as e:  # noqa: BLE001
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e
    sp = dict.fromkeys(STATS, 0)
    sp.update({stat: int(value) for stat, value in rows if stat in sp})
    return sp


def meta_build(pokemon_id: str, regulation: str, filt: MetaFilter | None = None,
               *, marginal: bool = False, n_moves: int = 4,
               prof: Profile | None = None) -> Build:
    """What this Pokémon most commonly is, as something the calculator can fire.

    The spread is the single most common FULL spread, which is a build somebody
    actually ran and is therefore legal and editable. `marginal=True` switches to the
    per-stat modes instead, which is what `vgc.incoming` and `vgc.outgoing` use —
    available so the two paths can be proved identical, not because it is a better
    default. See `marginal_spread` for why it is not.
    """
    p = prof if prof is not None else profile(pokemon_id, regulation, filt)
    e = p.entry

    if marginal:
        sp = marginal_spread(build_key(e), regulation, filt)
    else:
        top = p.top(SPREAD)
        try:
            sp = parse_spread(top[0]) if top else dict.fromkeys(STATS, 0)
        except ValueError:
            sp = dict.fromkeys(STATS, 0)

    item = p.top(ITEM)
    nature = p.top(NATURE)
    moves = tuple(to_id(value) for value, _pct in (p.details.get(MOVE) or ())[:n_moves])

    return Build(
        forme_id=e.pokemon_id,
        display_name=e.display_name,
        types=e.types,
        base=dict(e.base),
        ability_id=likely_ability(e, regulation),
        item_id=to_id(item[0]) if item else None,
        nature=nature[0] if nature else None,
        sp=sp,
        moves=moves,
    )
