"""One build against one build, in either direction.

`vgc.incoming` and `vgc.outgoing` each answer a question about *your team versus the
top N of the meta*. They share a damage loop and differ only in which side is known.
This module is that loop with the team assumption removed: two `Build`s, one move at
a time, and no opinion about where either came from.

It deliberately does NOT reimplement the formula. Every number goes through the same
`vgc.damage` calls in the same order, and `tests/test_matchup.py` pins that by
reproducing `outgoing()` and `incoming()` row for row from this module — so if this
ever drifts from the two modules already verified against Showdown's simulator, the
suite says so.

TWO FIGURES, AS EVERYWHERE ELSE. Damage is only as certain as the softer side's
investment, so every matchup reports:

    as_set   both builds exactly as specified
    worst    the same hit with the *unknown* side at its legal extreme

Which side is unknown is the caller's to state, because only the caller knows:

    unknown=DEFENDER   their bulk is a guess (32 HP, 32 in that defence, boosting
                       nature). This is the outgoing case — modal defensive shares
                       run 0.63-0.67, the softest data in the set.
    unknown=ATTACKER   their offence is a guess (32 SP, boosting nature). The
                       incoming case. Attacking shares run ~0.89, so this figure
                       moves less, but survival is not planned on the median.
    unknown=None       both sides come from a paste or from explicit input, so one
                       figure is the honest answer and `worst` equals `as_set`.

The item is held fixed in both figures on purpose, matching `vgc.incoming`: widening
two axes at once turns a worst case into speculation.

Same exclusions as `vgc.damage` — no crits, no burn, no screens, and abilities are
modelled through the generic stat stage rather than individually.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Sequence

from vgc.damage import (FOCUS_SASH, PHYSICAL, Result, attack_after_item,
                        base_power_multiplier, boosted, damage_multiplier,
                        damage_rolls, defence_after_item, defence_after_weather,
                        seed_boost, spreads_in_terrain, weather_move,
                        weather_multiplier)
from vgc.db import session
from vgc.megas import Forme
from vgc.stats import STATS, calc_stat, nature_mod, sp_from_investment
from vgc.team import Member
from vgc.typechart import attack_type, effectiveness

MAX_SP = 32       # the most a single stat can hold
BOOSTING = 1.1    # a nature that raises the stat in question

ATTACKER, DEFENDER = "attacker", "defender"
UNKNOWN_SIDES = (ATTACKER, DEFENDER, None)


@dataclass(frozen=True)
class Build:
    """A concrete Pokémon: what it is, what it holds, and what it invested.

    The same shape whether it came from a paste, from the meta's most common build,
    or from someone typing into the app — which is the point. Nothing downstream
    needs to know the difference.
    """

    forme_id: str
    display_name: str
    types: tuple[str, ...]
    base: dict[str, int]
    ability_id: str | None = None
    item_id: str | None = None
    nature: str | None = None
    sp: dict[str, int] = field(default_factory=lambda: dict.fromkeys(STATS, 0))
    moves: tuple[str, ...] = ()

    def stat(self, key: str) -> int:
        """The finished stat. HP ignores nature, which calc_stat already handles."""
        return calc_stat(self.base[key], self.sp.get(key, 0),
                         nature_mod(self.nature, key), stat=key)

    @property
    def hp(self) -> int:
        return self.stat("hp")

    def max_stat(self, key: str) -> int:
        """That stat at the legal ceiling: 32 SP and a nature that raises it.

        HP takes no nature, so its ceiling is just 32 SP — and 32 HP plus 32 in one
        defence is 64 of the 66 SP available, which is why the bulkiest legal build
        is reachable at all.
        """
        return calc_stat(self.base[key], MAX_SP,
                         1.0 if key == "hp" else BOOSTING, stat=key)


def from_member(member: Member, forme: Forme) -> Build:
    """One of your own Pokémon. Exact: everything here came from the paste."""
    try:
        sp = sp_from_investment(member.investment)
    except ValueError:
        sp = dict.fromkeys(STATS, 0)
    return Build(
        forme_id=forme.forme_id,
        display_name=forme.display_name,
        types=forme.types,
        base=base_stats(forme.forme_id),
        ability_id=forme.ability_id,
        item_id=member.item_id,
        nature=member.nature,
        sp=dict(sp),
        moves=tuple(member.moves or ()),
    )


def team_builds(team: Sequence[Member], formes: Sequence[Forme]) -> list[Build]:
    by_slot = {m.slot: m for m in team}
    return [from_member(by_slot[f.slot], f) for f in formes if f.slot in by_slot]


@lru_cache(maxsize=1)
def _base_stats() -> dict[str, dict[str, int]]:
    with session() as con:
        rows = con.execute(
            'select pokemon_id, hp, atk, "def", spa, spd, spe from dim_pokemon'
        ).fetchall()
    return {r[0]: dict(zip(STATS, (int(v) for v in r[1:]))) for r in rows}


def base_stats(pokemon_id: str) -> dict[str, int]:
    stats = _base_stats().get(pokemon_id)
    if stats is None:
        raise LookupError(f"No base stats for {pokemon_id!r}")
    return dict(stats)


@lru_cache(maxsize=1)
def move_data() -> dict[str, tuple]:
    """move_id -> (display_name, type, category, base_power, is_spread)."""
    with session() as con:
        rows = con.execute("""
            select move_id, display_name, type, category, base_power, is_spread
            from dim_move
        """).fetchall()
    return {r[0]: (r[1], r[2], r[3], int(r[4] or 0), bool(r[5])) for r in rows}


def clear_cache() -> None:
    _base_stats.cache_clear()
    move_data.cache_clear()


def damaging(moves: Sequence[str]) -> list[str]:
    """The subset of these move ids that actually deal damage."""
    data = move_data()
    return [m for m in moves if m in data and data[m][3] > 0]


@dataclass(frozen=True)
class Matchup:
    """One move, from one build into another, with its two figures."""

    attacker: Build
    defender: Build
    move_id: str
    move_name: str
    move_type: str          # the type it ATTACKS as, so Aerilate is already applied
    category: str
    as_set: Result
    worst: Result
    unknown: str | None

    @property
    def kos(self) -> bool:
        """A one-hit KO that survives not knowing what the unknown side invested."""
        return self.worst.low >= self.worst.defender_hp

    @property
    def as_set_kos(self) -> bool:
        return self.as_set.low >= self.as_set.defender_hp

    @property
    def certain(self) -> bool:
        """Nothing is being guessed, so the two figures are the same number."""
        return self.unknown is None

    @property
    def hits_to_ko(self) -> int | None:
        return self.as_set.guaranteed_hits


def versus(attacker: Build, defender: Build, *, weather: str | None = None,
           terrain: str | None = None, atk_stage: int = 0, def_stage: int = 0,
           unknown: str | None = DEFENDER, screen: str | None = None,
           moves: Sequence[str] | None = None) -> list[Matchup]:
    """Every damaging move the attacker has, against this defender, hardest first.

    `atk_stage` / `def_stage` are ordinary stat stages, which is how this models the
    abilities the project deliberately does not hardcode: Intimidate is -1 Atk,
    Stamina +1 Def per hit, Swords Dance +2. One control instead of an ability graph.
    """
    if unknown not in UNKNOWN_SIDES:
        raise ValueError(f"unknown must be one of {UNKNOWN_SIDES}, got {unknown!r}")
    data = move_data()
    out: list[Matchup] = []

    for move_id in damaging(moves if moves is not None else attacker.moves):
        name, listed_type, category, base_power, is_spread = data[move_id]
        # The move's own ModifyType runs before the ability's, so this comes first.
        listed_type, base_power = weather_move(move_id, listed_type, base_power, weather)
        move_type = attack_type(listed_type, attacker.ability_id)
        akey = "atk" if category == PHYSICAL else "spa"
        dkey = "def" if category == PHYSICAL else "spd"

        mult = effectiveness(move_type, defender.types, defender.ability_id)
        stab = move_type in attacker.types

        # A terrain seed is a stat change, not a damage modifier, so it stacks onto
        # the stage the caller passed rather than entering the chain.
        seed = seed_boost(defender.item_id, terrain, dkey)

        def roll(attack_raw: int, defence_raw: int, hp: int) -> Result:
            # Stage first, item second: sim/pokemon.ts:583 boosts before
            # battle.modify(), so base -> stage -> item is the only correct order.
            return Result(name, move_type, damage_rolls(
                base_power=base_power,
                attack=attack_after_item(boosted(attack_raw, atk_stage),
                                         attacker.item_id, category),
                # base -> stage -> weather -> item: snow and sand scale the stat at
                # onModify*Priority 10, ahead of every other stat modifier.
                defense=defence_after_item(
                    defence_after_weather(boosted(defence_raw, def_stage + seed),
                                          weather, defender.types, category),
                    defender.item_id, category),
                type_mult=mult, stab=stab,
                spread=is_spread or spreads_in_terrain(terrain, move_id),
                weather_mult=weather_multiplier(weather, move_type),
                final_mult=damage_multiplier(attacker.item_id, defender.item_id,
                                             move_type, mult, screen, category),
                base_power_mult=base_power_multiplier(
                    attacker.item_id, move_type, terrain, move_id)),
                hp, mult, stab,
                defender_sash=defender.item_id == FOCUS_SASH)

        as_set = roll(attacker.stat(akey), defender.stat(dkey), defender.hp)
        if unknown == DEFENDER:
            worst = roll(attacker.stat(akey), defender.max_stat(dkey),
                         defender.max_stat("hp"))
        elif unknown == ATTACKER:
            worst = roll(attacker.max_stat(akey), defender.stat(dkey), defender.hp)
        else:
            worst = as_set

        out.append(Matchup(attacker=attacker, defender=defender, move_id=move_id,
                           move_name=name, move_type=move_type, category=category,
                           as_set=as_set, worst=worst, unknown=unknown))

    return sorted(out, key=lambda m: m.worst.low, reverse=True)


def best(attacker: Build, defender: Build, **kwargs) -> Matchup | None:
    """The attacker's hardest hit on this defender, or None if it has no damage."""
    rows = versus(attacker, defender, **kwargs)
    return rows[0] if rows else None


def with_spread(build: Build, nature: str | None, sp: dict[str, int]) -> Build:
    """A copy carrying a different spread — how the app applies the build panel."""
    return replace(build, nature=nature, sp=dict(sp))
