"""Champions damage formula. Pure arithmetic — no warehouse, no I/O.

Everything here is derived from the pinned Showdown checkout in vendor/ at c23d2e9,
which is the same commit the static data was exported from. Citations are to that
tree. Kept free of database access on purpose: this is the one module whose output
is a *claim* rather than an annotation, so it has to be verifiable in isolation
against the reference implementation.

WHAT CHAMPIONS CHANGES. The mod overrides `statModify` (the stat formula this project
already verified against a 31-row reference table) and `modifyDamage` — but the
`modifyDamage` override is a copy of the generic one with a 4x/0.25x effectiveness
announcement added, and `getDamage` is not overridden at all. The mod ships its own
conditions.ts but does not touch weather. So: Champions stats, mainline damage.

THE CHAIN, in order (sim/battle-actions.ts:1718 onward):

    base = trunc(trunc(trunc(trunc(2*L/5 + 2) * BP * A) / D) / 50)      :1718
    base += 2                                                            :1725
    spread (0.75 in doubles, 0.5 free-for-all)                           :1737
    weather                                                              :1746
    critical hit x1.5                                                    :1751
    RANDOM ROLL, 85..100 in sixteenths                                   :1755
    STAB x1.5                                                            :1792
    type effectiveness, as repeated doubling or halving                  :1794
    burn (physical, halved)                                              :1815
    final modifiers -- Life Orb and friends                              :1826

The roll lands BEFORE STAB and type effectiveness, not after. That ordering, and the
fact that `modify` is 4096-step fixed point rather than a float multiply
(sim/battle.ts:2342), are the two things an implementation gets wrong and only
notices as an off-by-one against real values.

Two things happen BEFORE any of that, when the move is used rather than when damage
is computed: the move's own `onModifyType` / `onModifyMove` callbacks (:430-431) and
then the attacker's ability's (:438). That is where Weather Ball picks up its type
and its doubled power, so `weather_move` runs ahead of everything here.

HELD ITEMS, both sides. The attacker's are the stat and damage modifiers below; the
defender's are the eighteen resist berries (an `onSourceModifyDamage` that halves a
matching super-effective hit), the four terrain seeds (a one-stage defensive boost,
so a stat change rather than a damage one) and Focus Sash, which touches neither and
lives in `Result`'s verdict. The two sides' damage modifiers are both ModifyDamage
handlers and therefore CHAIN -- see `chain` and `damage_multiplier`.

WEATHER comes in two kinds and they enter in different places. Rain and sun scale the
MOVE (`weather_multiplier`); snow and sand scale a defensive STAT -- Ice Def and Rock
SpD respectively -- so they land in `defence_after_weather`, before the item modifier.
All four retype Weather Ball.

SCREENS are `onAnyModifyDamage` handlers, so they chain with the items above. The
reduction is 2732/4096 in doubles, NOT the 0.5 of singles.

NOT MODELLED, deliberately, and stated wherever a number is shown: abilities that
scale damage (Adaptability, Thick Fat, Multiscale, Guts and the rest), critical hits,
burn, multi-hit and fixed-damage moves, and Misty Terrain (which would also have to
halve Dragon damage, and is on 0.12% of teams). Abilities that change type
effectiveness *are* handled, because they arrive through vgc.typechart.effectiveness
before this module sees them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

LEVEL = 50
ROLLS = 16                     # 85..100 inclusive, sim/battle.ts:2391
SPREAD_DOUBLES = 0.75          # battle-actions.ts:1739
STAB = 1.5                     # battle-actions.ts:1789
RAIN_WATER, RAIN_FIRE = 1.5, 0.5     # data/conditions.ts:488-495
SUN_FIRE, SUN_WATER = 1.5, 0.5       # data/conditions.ts:562-568

RAIN, SUN = "rain", "sun"
# Snow and sand scale a STAT rather than the move: snow gives an Ice-type +50% Def
# and sand gives a Rock-type +50% SpD (data/conditions.ts, onModifyDef /
# onModifySpD at priority 10). Neither multiplies damage the way rain and sun do,
# which is why they are absent from `weather_multiplier` and present here instead.
SNOW, SAND = "snow", "sand"
WEATHERS = (RAIN, SUN, SNOW, SAND)
# (weather, defended type, which stat it protects)
WEATHER_DEFENCE = {SNOW: ("Ice", "def"), SAND: ("Rock", "spd")}
WEATHER_DEFENCE_BOOST = 1.5

# Terrain modifies BASE POWER, not damage — battle-actions.ts:1650 runs the BasePower
# event before the formula, where weather is applied afterwards at :1746. Different
# insertion points, so they are separate arguments here and must not be merged.
# The multiplier is chainModify([5325, 4096]), i.e. 5325/4096, not a clean 1.3.
GRASSY, PSYCHIC_T, ELECTRIC_T = "grassy", "psychic", "electric"
TERRAIN_BOOST = 5325 / 4096
TERRAIN_TYPE = {GRASSY: "Grass", PSYCHIC_T: "Psychic", ELECTRIC_T: "Electric"}
# Grassy Terrain also halves these against a grounded target (data/moves.ts:7695).
GRASSY_WEAKENED = ("earthquake", "bulldoze", "magnitude")


# Moves with their own terrain clause, applied ON TOP of the generic type boost —
# both are onBasePower handlers so they chain. Expanding Force in Psychic Terrain
# measures at 1.939x against 5325/4096 x 1.5 = 1.950 predicted, which is the rounding.
# Each verified against the simulator, measured ratio against predicted:
#   Expanding Force  psychic   1.939 / 1.950  (generic boost x its own 1.5)
#   Psyblade         electric  1.472 / 1.500  (Psychic-typed, so no generic boost)
#   Rising Voltage   electric  2.562 / 2.600  (Electric-typed, so generic x its own 2)
# Rising Voltage doubles via basePowerCallback rather than chainModify, which lands
# at the same value here because the callback runs before the BasePower event.
TERRAIN_MOVE_EXTRA = {
    (PSYCHIC_T, "expandingforce"): 1.5,
    (ELECTRIC_T, "psyblade"): 1.5,
    (ELECTRIC_T, "risingvoltage"): 2.0,
}

# Moves that also change target in terrain. Expanding Force becomes allAdjacentFoes
# under Psychic Terrain (data/moves.ts:4959), so it picks up the spread modifier —
# which matters more than the power boost when reading a psyspam matchup, because
# 1.95 x 0.75 nets to about 1.46 against a single target but hits both.
TERRAIN_MAKES_SPREAD = {(PSYCHIC_T, "expandingforce")}


def spreads_in_terrain(terrain: str | None, move_id: str) -> bool:
    return (terrain, move_id) in TERRAIN_MAKES_SPREAD


# Weather Ball reads the field for its TYPE as well as its power (data/moves.ts:20702).
# Both of its callbacks are singleEvents fired in useMoveInner -- ModifyType at
# battle-actions.ts:430 and ModifyMove at :431 -- so they land before getDamage sees
# the move at all. Three consequences, and none of them are optional:
#
#   * STAB and type effectiveness are judged against the NEW type, not Normal.
#   * The weather multiplier then applies to that new type, so rain gives Weather
#     Ball x1.5 as a Water move rather than the x1 it got as a Normal one.
#   * The doubling is `move.basePower *= 2`, a plain arithmetic doubling of the raw
#     50 rather than a chainModify, and it happens before the BasePower event -- so
#     terrain and a type item chain onto 100.
#
# It also runs BEFORE the -ate abilities' own ModifyType at :438, which is why
# `weather_move` is called ahead of `attack_type`: an Aerilate holder's Weather Ball
# is Flying in no weather and Water in rain, not Flying in both.
#
# Sandstorm (Rock) and snow (Ice) are in the move but not here, because this project
# models only rain and sun -- see WEATHER_BALL_TYPE staying keyed to those two.
WEATHER_BALL = "weatherball"
WEATHER_BALL_TYPE = {RAIN: "Water", SUN: "Fire", SNOW: "Ice", SAND: "Rock"}


def weather_move(move_id: str, move_type: str, base_power: int,
                 weather: str | None) -> tuple[str, int]:
    """The type and base power a weather-dependent move arrives with.

    A pass-through for every other move, so call sites can apply it unconditionally.
    """
    if move_id != WEATHER_BALL:
        return move_type, base_power
    typed = WEATHER_BALL_TYPE.get(weather or "")
    if typed is None:
        return move_type, base_power
    return typed, base_power * 2


def terrain_multiplier(terrain: str | None, move_type: str,
                       move_id: str = "") -> float:
    """Base-power multiplier from terrain. Assumes both sides are grounded, which is
    the common case and is stated in the app; a Flying or Levitating attacker gets no
    boost and is not modelled here."""
    if not terrain:
        return 1.0
    if terrain == GRASSY and move_id in GRASSY_WEAKENED:
        return 0.5
    mult = TERRAIN_BOOST if move_type == TERRAIN_TYPE.get(terrain) else 1.0
    return mult * TERRAIN_MOVE_EXTRA.get((terrain, move_id), 1.0)


def trunc(value: float) -> int:
    """Showdown's integer truncation. Every value here is non-negative."""
    return int(value)


def modify(value: int, numerator: float, denominator: int = 1) -> int:
    """sim/battle.ts:2342. Fixed point in 4096ths, NOT a float multiply.

    The +2047 is Showdown's `+ 2048 - 1`, which rounds half up at the last step.
    """
    modifier = trunc(numerator * 4096 / denominator)
    return trunc((trunc(value * modifier) + 2047) / 4096)


def _apply_type(damage: int, multiplier: float) -> int:
    """battle-actions.ts:1794. Effectiveness is an exponent applied as repeated
    doubling or halving — and only the halving truncates."""
    if multiplier == 0:
        return 0
    while multiplier > 1:
        damage *= 2
        multiplier /= 2
    while multiplier < 1:
        damage = trunc(damage / 2)
        multiplier *= 2
    return damage


def weather_multiplier(weather: str | None, move_type: str) -> float:
    if weather == RAIN:
        return RAIN_WATER if move_type == "Water" else RAIN_FIRE if move_type == "Fire" else 1.0
    if weather == SUN:
        return SUN_FIRE if move_type == "Fire" else SUN_WATER if move_type == "Water" else 1.0
    return 1.0


def damage_rolls(*, base_power: int, attack: int, defense: int, type_mult: float,
                 stab: bool = False, spread: bool = True, weather_mult: float = 1.0,
                 final_mult: float = 1.0, base_power_mult: float = 1.0,
                 level: int = LEVEL) -> tuple[int, ...]:
    """The sixteen possible damage values, lowest first.

    `base_power_mult` covers everything applied by the BasePower event — terrain and
    type-boosting items — and lands before the formula, unlike weather.
    """
    if base_power <= 0 or type_mult == 0 or attack <= 0 or defense <= 0:
        return (0,) * ROLLS

    if base_power_mult != 1.0:
        base_power = max(1, modify(base_power, base_power_mult))

    base = trunc(trunc(trunc(trunc(2 * level / 5 + 2) * base_power * attack) / defense) / 50)
    base += 2
    if spread:
        base = modify(base, SPREAD_DOUBLES)
    if weather_mult != 1.0:
        base = modify(base, weather_mult)

    out = []
    for r in range(ROLLS):
        d = trunc(trunc(base * (100 - r)) / 100)
        if stab:
            d = modify(d, STAB)
        d = _apply_type(d, type_mult)
        if final_mult != 1.0:
            d = modify(d, final_mult)
        out.append(d)
    return tuple(sorted(out))


@dataclass(frozen=True)
class Result:
    move_name: str
    move_type: str
    rolls: tuple[int, ...]
    defender_hp: int
    type_mult: float
    stab: bool
    assumptions: tuple[str, ...] = ()
    # Focus Sash does NOT change the damage — `onDamage` at data/items.ts:2272 returns
    # `target.hp - 1` only when the target is at full HP and the hit would kill. So it
    # belongs here, in the verdict, and not anywhere in the chain above. It is the
    # most-held item in the format at 10.19%, and the tool used to ignore it entirely.
    defender_sash: bool = False

    @property
    def low(self) -> int:
        return self.rolls[0]

    @property
    def high(self) -> int:
        return self.rolls[-1]

    @property
    def low_pct(self) -> float:
        return 100.0 * self.low / self.defender_hp if self.defender_hp else 0.0

    @property
    def high_pct(self) -> float:
        return 100.0 * self.high / self.defender_hp if self.defender_hp else 0.0

    def _sashed(self, hits: int | None) -> int | None:
        """A Sash only ever converts a one-hit KO into two.

        It triggers at full HP and leaves 1 HP, so the first hit cannot kill. If the
        hit was not a OHKO anyway the Sash never fires, and the count is unchanged —
        the holder is no longer at full HP by the time the second hit lands.
        """
        if not self.defender_sash or hits is None:
            return hits
        return 2 if hits == 1 else hits

    @property
    def guaranteed_hits(self) -> int | None:
        """Hits to KO on the worst roll every time. None if it cannot KO at all."""
        if self.low <= 0:
            return None
        return self._sashed(-(-self.defender_hp // self.low))

    @property
    def possible_hits(self) -> int | None:
        """Hits to KO if every roll is the best. None if it cannot KO at all."""
        if self.high <= 0:
            return None
        return self._sashed(-(-self.defender_hp // self.high))

    def verdict(self) -> str:
        """The phrasing damage calculators use: guaranteed, or possible-but-not-certain."""
        if self.high <= 0:
            return "no damage"
        best, worst = self.possible_hits, self.guaranteed_hits
        if best == worst:
            return f"guaranteed {best}HKO" if best > 1 else "guaranteed OHKO"
        label = "OHKO" if best == 1 else f"{best}HKO"
        return f"possible {label}"


# Items that scale a stat rather than the damage. Applied with the same 4096-step
# rounding Showdown uses for stat modifiers, not a float multiply.
ATTACK_ITEMS = {"choiceband": ("atk", 1.5), "choicespecs": ("spa", 1.5)}
DEFENCE_ITEMS = {"assaultvest": ("spd", 1.5), "eviolite": ("both", 1.5)}
# Items applied at the very end of the chain (battle-actions.ts:1826, ModifyDamage).
FINAL_ITEMS = {"lifeorb": 1.3, "muscleband": 1.1, "wiseglasses": 1.1}
EXPERT_BELT = 1.2   # only against a super effective hit

# Type-boosting held items, x1.2 on the matching type, applied to BASE POWER.
TYPE_ITEMS = {
    "miracleseed": "Grass", "charcoal": "Fire", "mysticwater": "Water",
    "magnet": "Electric", "nevermeltice": "Ice", "blackbelt": "Fighting",
    "poisonbarb": "Poison", "softsand": "Ground", "sharpbeak": "Flying",
    "twistedspoon": "Psychic", "silverpowder": "Bug", "hardstone": "Rock",
    "spelltag": "Ghost", "dragonfang": "Dragon", "blackglasses": "Dark",
    "metalcoat": "Steel", "fairyfeather": "Fairy", "silkscarf": "Normal",
}
TYPE_ITEM_BOOST = 1.2


def base_power_multiplier(item_id: str | None, move_type: str,
                          terrain: str | None = None, move_id: str = "") -> float:
    """Everything the BasePower event applies, combined.

    Showdown's chainModify accumulates the modifiers and applies them **once**, so
    these are multiplied together here and handed to a single modify() rather than
    applied one at a time — two sequential modify() calls round differently.
    """
    mult = terrain_multiplier(terrain, move_type, move_id)
    if TYPE_ITEMS.get(item_id or "") == move_type:
        mult *= TYPE_ITEM_BOOST
    return mult

PHYSICAL, SPECIAL = "Physical", "Special"

# sim/pokemon.ts:583. Stages are applied to the STAT, before any item modifier —
# `modifyStat` boosts first and calls battle.modify() afterwards — so the order here
# is base stat -> boost -> item, and reversing it is wrong by a point or two.
#
# One generic control covers most of what would otherwise need an ability model:
# Intimidate is -1 Atk, Stamina is +N Def, Swords Dance +2, Nasty Plot +2 SpA.
BOOST_TABLE = (1, 1.5, 2, 2.5, 3, 3.5, 4)
MAX_STAGE = 6


def boosted(stat: int, stage: int) -> int:
    """A stat at a given stage, clamped to +/-6."""
    stage = max(-MAX_STAGE, min(MAX_STAGE, stage))
    if stage >= 0:
        return trunc(stat * BOOST_TABLE[stage])
    return trunc(stat / BOOST_TABLE[-stage])


def attack_after_item(stat: int, item_id: str | None, category: str) -> int:
    """Choice Band / Specs scale the attacking stat, and only the matching one."""
    entry = ATTACK_ITEMS.get(item_id or "")
    if not entry:
        return stat
    which, mult = entry
    wanted = "atk" if category == PHYSICAL else "spa"
    return modify(stat, mult) if which == wanted else stat


def defence_after_item(stat: int, item_id: str | None, category: str) -> int:
    """Assault Vest scales Special Defence only; Eviolite scales both."""
    entry = DEFENCE_ITEMS.get(item_id or "")
    if not entry:
        return stat
    which, mult = entry
    wanted = "def" if category == PHYSICAL else "spd"
    return modify(stat, mult) if which in (wanted, "both") else stat


def final_multiplier(item_id: str | None, type_mult: float) -> float:
    """The ATTACKER's multipliers, applied after the minimum-damage check."""
    item_id = item_id or ""
    if item_id == "expertbelt":
        return EXPERT_BELT if type_mult > 1 else 1.0
    return FINAL_ITEMS.get(item_id, 1.0)


# Resist berries. Every one is an `onSourceModifyDamage` handler that chainModifies
# 0.5 when the move's type matches and `typeMod > 0` (data/items.ts). They are the
# defender's side of the same ModifyDamage event the attacker's Life Orb fires on,
# which is why they have to chain with it rather than being applied separately.
#
# CHILAN BERRY IS THE EXCEPTION and the reason this table carries a flag rather than
# just a type: it halves Normal-type damage with no effectiveness condition at all.
# The other seventeen require the hit to be super effective.
RESIST_BERRIES: dict[str, tuple[str, bool]] = {
    "babiriberry": ("Steel", True), "chartiberry": ("Rock", True),
    "chilanberry": ("Normal", False), "chopleberry": ("Fighting", True),
    "cobaberry": ("Flying", True), "colburberry": ("Dark", True),
    "habanberry": ("Dragon", True), "kasibberry": ("Ghost", True),
    "kebiaberry": ("Poison", True), "occaberry": ("Fire", True),
    "passhoberry": ("Water", True), "payapaberry": ("Psychic", True),
    "rindoberry": ("Grass", True), "roseliberry": ("Fairy", True),
    "shucaberry": ("Ground", True), "tangaberry": ("Bug", True),
    "wacanberry": ("Electric", True), "yacheberry": ("Ice", True),
}
BERRY_REDUCTION = 0.5

# Terrain seeds: consumed on entry in the matching terrain for a one-stage boost
# (data/items.ts, `boosts`). A stat change, not a damage modifier, so it enters where
# the stat stages do — before the item modifier, per sim/pokemon.ts:583.
# Misty is listed for completeness; this project models only the three terrains in
# TERRAIN_TYPE, so misty never fires.
SEEDS: dict[str, tuple[str, str]] = {
    "grassyseed": (GRASSY, "def"), "electricseed": (ELECTRIC_T, "def"),
    "psychicseed": (PSYCHIC_T, "spd"), "mistyseed": ("misty", "spd"),
}

FOCUS_SASH = "focussash"


def resist_berry_multiplier(item_id: str | None, move_type: str,
                            type_mult: float) -> float:
    """The DEFENDER's berry, 0.5 or 1.0."""
    entry = RESIST_BERRIES.get(item_id or "")
    if entry is None:
        return 1.0
    berry_type, needs_super_effective = entry
    if move_type != berry_type:
        return 1.0
    if needs_super_effective and type_mult <= 1:
        return 1.0
    return BERRY_REDUCTION


def seed_boost(item_id: str | None, terrain: str | None, stat: str) -> int:
    """Extra defensive stages from a terrain seed: 1 or 0."""
    entry = SEEDS.get(item_id or "")
    if entry is None or terrain is None:
        return 0
    seed_terrain, seed_stat = entry
    return 1 if seed_terrain == terrain and seed_stat == stat else 0


def chain(modifier: float, numerator: float, denominator: int = 1) -> float:
    """Accumulate a modifier the way sim/battle.ts:2321 does.

    `runEvent` collects every handler's `chainModify` into one `event.modifier` and
    applies it ONCE at battle.ts:932. So an attacker's Life Orb and a defender's
    Chople Berry are not two sequential `modify()` calls — they compose here, with a
    rounding step between them, and the result is handed to a single `modify()`.
    Multiplying the two as plain floats agrees on most pairs and is not the same
    operation, which is exactly the class of error that only shows on one roll in
    sixteen.
    """
    previous = trunc(modifier * 4096)
    nxt = trunc(numerator * 4096 / denominator)
    return ((previous * nxt + 2048) >> 12) / 4096


# Screens. All three are `onAnyModifyDamage` handlers (data/moves.ts), so they land
# in the same event as Life Orb and the resist berries and chain with them.
#
# THE MULTIPLIER IS 2732/4096 IN DOUBLES, NOT 0.5. The source reads
# `if (this.activePerHalf > 1) return this.chainModify([2732, 4096]);` and only falls
# through to 0.5 in singles. This format is doubles, so 0.5 would be wrong on every
# screened hit — measured at 0.664 against the simulator before this was written.
#
# A critical hit and an Infiltrator user both bypass a screen; neither is modelled,
# so neither is represented here.
REFLECT, LIGHT_SCREEN, AURORA_VEIL = "reflect", "lightscreen", "auroraveil"
SCREENS = (REFLECT, LIGHT_SCREEN, AURORA_VEIL)
SCREEN_DOUBLES = 2732 / 4096


def screen_multiplier(screen: str | None, category: str) -> float:
    """Reflect covers Physical, Light Screen covers Special, Aurora Veil covers both.

    Aurora Veil additionally requires snow to have been up when it was *set*, which
    is a turn-order fact rather than a damage one — the caller owns that, and the app
    says so where the control lives.
    """
    if screen is None:
        return 1.0
    if screen == AURORA_VEIL:
        return SCREEN_DOUBLES
    if screen == REFLECT and category == PHYSICAL:
        return SCREEN_DOUBLES
    if screen == LIGHT_SCREEN and category == SPECIAL:
        return SCREEN_DOUBLES
    return 1.0


def defence_after_weather(stat: int, weather: str | None,
                          defender_types: Sequence[str], category: str) -> int:
    """Snow's Ice Def and sand's Rock SpD, applied to the STAT.

    `onModifyDefPriority: 10` with the comment "This should be applied directly to
    the stat before any of the other modifiers are chained", so the order is
    base -> stage -> weather -> item, and this sits between `boosted` and
    `defence_after_item`.
    """
    entry = WEATHER_DEFENCE.get(weather or "")
    if entry is None:
        return stat
    needed_type, protects = entry
    wanted = "def" if category == PHYSICAL else "spd"
    if protects != wanted or needed_type not in defender_types:
        return stat
    return modify(stat, WEATHER_DEFENCE_BOOST)


def damage_multiplier(attacker_item: str | None, defender_item: str | None,
                      move_type: str, type_mult: float,
                      screen: str | None = None, category: str = PHYSICAL) -> float:
    """Everything the ModifyDamage event applies, from both sides, chained once."""
    modifier = chain(1.0, final_multiplier(attacker_item, type_mult))
    modifier = chain(modifier, resist_berry_multiplier(defender_item, move_type, type_mult))
    return chain(modifier, screen_multiplier(screen, category))
