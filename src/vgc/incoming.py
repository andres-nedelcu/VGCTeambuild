"""What the meta actually does to your team, in HP rather than type multipliers.

Visual 4 ranks threats by type pressure and says so: it ignores base power, stats,
bulk and items, so a 4x hit from a weak move still reads as 4x. This answers the
question that leaves open — does it actually KO — by putting real numbers through
vgc.damage, which is pinned against Showdown's own simulator.

The two sides are known to different degrees, and the app says so wherever this is
shown:

  YOUR side is exact. Species, nature, investment and item come from your paste.
  THEIR side is the meta's most common build. Attacking investment is a safe
    assumption -- the modal Atk share averages 0.887 across species and SpA 0.893,
    so attackers essentially always run max offence -- but the item and moves are
    "what most people bring", not what the player in front of you brought.

NOT MODELLED, and listed in the caption rather than buried here: abilities that scale
damage, screens, terrain move boosts, critical hits, burn, Intimidate and stat
stages. Weather IS modelled, because it is a plain multiplier in the chain and it is
often the whole story -- rain turns a 4x Fire hit into 2x, which is the difference
between Golisopod-Mega dying and living.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from vgc.damage import (Result, attack_after_item, base_power_multiplier, boosted,
                        damage_rolls, defence_after_item, final_multiplier,
                        spreads_in_terrain, weather_move, weather_multiplier)
from vgc.db import session
from vgc.megas import Forme
from vgc.metafilter import MetaFilter
from vgc.offense import Threat, threats
from vgc.stats import calc_stat, nature_mod, sp_from_investment
from vgc.team import Member
from vgc.typechart import attack_type, effectiveness

BUILD_CMD = "uv run python scripts/build_marts.py"


MAX_SP = 32          # the most a single stat can hold
BOOSTING = 1.1       # a +Atk / +SpA nature
# Below this share, the modal investment is close to a coin flip and the "likely"
# figure should not be leaned on. Raichu is the worked example: its modal SpA is 0
# at 0.45, so 55% of them invest something.
SHAKY = 0.6


@dataclass(frozen=True)
class Incoming:
    threat: Threat
    target_slot: int
    target_name: str
    likely: Result          # the meta's modal offensive investment
    worst: Result           # 32 SP and a boosting nature, the legal maximum
    investment_share: float  # how dominant that modal investment actually is

    @property
    def kos(self) -> bool:
        """Worst case, because survival planning is not done on the median."""
        return self.worst.low >= self.worst.defender_hp

    @property
    def likely_kos(self) -> bool:
        return self.likely.low >= self.likely.defender_hp

    @property
    def confident(self) -> bool:
        return self.investment_share >= SHAKY


def team_bulk(team: Sequence[Member], formes: Sequence[Forme]) -> dict[int, dict]:
    """Exact HP / Def / SpD for each of your Pokémon, from the paste."""
    with session() as con:
        base = {r[0]: r[1:] for r in con.execute(
            "select pokemon_id, hp, \"def\", spd from dim_pokemon").fetchall()}
    by_slot = {m.slot: m for m in team}
    out = {}
    for f in formes:
        member = by_slot[f.slot]
        sp = sp_from_investment(member.investment)
        hp_b, def_b, spd_b = base[f.forme_id]
        out[f.slot] = {
            "hp": calc_stat(hp_b, sp["hp"], 1.0, stat="hp"),
            "def": calc_stat(def_b, sp["def"], nature_mod(member.nature, "def"), stat="def"),
            "spd": calc_stat(spd_b, sp["spd"], nature_mod(member.nature, "spd"), stat="spd"),
            "item": member.item_id,
        }
    return out


def _threat_builds(regulation: str, filt: MetaFilter) -> dict:
    """Modal offensive investment, nature and item per species, plus common moves."""
    with session() as con:
        try:
            inv = con.execute(f"""
                select pokemon_id, stat, sp, share from {filt.call('meta_investment')}
                where stat in ('atk', 'spa')
            """, filt.params(regulation)).fetchall()
            nat = con.execute("""
                select pokemon_id, detail_value from (
                    select pokemon_id, detail_value,
                           row_number() over (partition by pokemon_id order by pct desc,
                                              detail_value) as rn
                    from mart_build_detail where detail_type = 'nature')
                where rn = 1
            """).fetchall()
            item = con.execute("""
                select pokemon_id, detail_value from (
                    select pokemon_id, detail_value,
                           row_number() over (partition by pokemon_id order by pct desc,
                                              detail_value) as rn
                    from mart_build_detail where detail_type = 'item')
                where rn = 1
            """).fetchall()
            moves = con.execute(f"""
                select c.forme_id, c.species_id, c.move_name, c.move_type, c.category,
                       c.base_power, c.is_spread, p.hp, p.atk, p.spa, c.move_id
                from {filt.call('meta_common_moves')} c
                join dim_pokemon p on p.pokemon_id = c.forme_id
                where c.base_power > 0
            """, filt.params(regulation)).fetchall()
        except Exception as e:  # noqa: BLE001
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e
    sp = {}
    for pid, stat, value, share in inv:
        sp.setdefault(pid, {})[stat] = (int(value), float(share))
    return {"sp": sp, "nature": dict(nat), "item": dict(item), "moves": moves}


def incoming(regulation: str, team: Sequence[Member], formes: Sequence[Forme],
             filt: MetaFilter | None = None, top_n: int = 20,
             weather: str | None = None, atk_stage: int = 0,
             def_stage: int = 0, terrain: str | None = None) -> list[Incoming]:
    """The hardest hit each meta threat has on each of your Pokémon, worst first.

    `atk_stage` and `def_stage` are ordinary stat stages, which is how this models
    the abilities it deliberately does not hardcode: Intimidate is the attacker at
    -1, Stamina is the defender at +1 per hit taken, Swords Dance is +2. One control
    instead of an ability graph.
    """
    filt = filt or MetaFilter()
    meta = threats(regulation, top_n, filt)
    if not meta:
        return []
    builds = _threat_builds(regulation, filt)
    bulk = team_bulk(team, formes)
    by_forme = {t.forme_id: t for t in meta}
    by_slot = {f.slot: f for f in formes}

    out: list[Incoming] = []
    for forme_id, species_id, move_name, listed_type, category, base_power, spread, \
            hp_b, atk_b, spa_b, move_id in builds["moves"]:
        threat = by_forme.get(forme_id)
        if threat is None:
            continue
        # The move reads the weather before the ability does, so this runs first.
        listed_type, base_power = weather_move(
            move_id, listed_type, int(base_power), weather)
        move_type = attack_type(listed_type, threat.ability_id)
        nature = builds["nature"].get(species_id)
        sp = builds["sp"].get(species_id, {})
        item = builds["item"].get(species_id)

        key = "atk" if category == "Physical" else "spa"
        base_stat = atk_b if category == "Physical" else spa_b
        modal_sp, share = sp.get(key, (0, 0.0))
        likely_raw = calc_stat(base_stat, modal_sp, nature_mod(nature, key), stat=key)
        # The legal ceiling, which is what "can this kill me" actually asks. Item is
        # held at the modal one in both: widening two axes at once turns a worst case
        # into speculation.
        worst_raw = calc_stat(base_stat, MAX_SP, BOOSTING, stat=key)
        # Stage first, item second: sim/pokemon.ts:583 boosts before battle.modify().
        likely_attack = attack_after_item(boosted(likely_raw, atk_stage), item, category)
        worst_attack = attack_after_item(boosted(worst_raw, atk_stage), item, category)

        for slot, mine in bulk.items():
            target = by_slot[slot]
            mult = effectiveness(move_type, target.types, target.ability_id)
            defence = defence_after_item(
                boosted(mine["def"] if category == "Physical" else mine["spd"],
                        def_stage),
                mine["item"], category)
            def roll(attack: int) -> Result:
                return Result(move_name, move_type, damage_rolls(
                    base_power=base_power, attack=attack, defense=defence,
                    type_mult=mult, stab=move_type in threat.types, spread=bool(spread) or spreads_in_terrain(terrain, move_id),
                    weather_mult=weather_multiplier(weather, move_type),
                    final_mult=final_multiplier(item, mult),
                    base_power_mult=base_power_multiplier(
                        item, move_type, terrain, move_id)),
                    mine["hp"], mult, move_type in threat.types)

            out.append(Incoming(
                threat=threat, target_slot=slot, target_name=target.display_name,
                likely=roll(likely_attack), worst=roll(worst_attack),
                investment_share=share))

    # One row per (threat, target): the move that hurts most on its worst roll.
    best: dict[tuple[str, int], Incoming] = {}
    for hit in out:
        key = (hit.threat.forme_id, hit.target_slot)
        if key not in best or hit.worst.low > best[key].worst.low:
            best[key] = hit
    return sorted(best.values(), key=lambda h: h.worst.low_pct, reverse=True)


OHKO, TWO, THREE, SAFE = "OHKO", "2HKO", "3HKO", "Cannot threaten it"
TIERS = (OHKO, TWO, THREE, SAFE)


def tier(hit: Incoming) -> str:
    """Which KO bracket this hit falls in, on the worst case.

    Grouped rather than sorted because the shape is the answer: "three things OHKO
    this" is the fact that decides whether it can be left on the field, and a flat
    ranked list makes you count rows to find it.
    """
    hits = hit.worst.guaranteed_hits
    if hits is None:
        return SAFE
    return {1: OHKO, 2: TWO, 3: THREE}.get(hits, SAFE)


def against(rows: Sequence[Incoming], slot: int) -> dict[str, list[Incoming]]:
    """Everything aimed at one of your Pokémon, bucketed by KO tier, worst first."""
    out: dict[str, list[Incoming]] = {t: [] for t in TIERS}
    for hit in rows:
        if hit.target_slot == slot:
            out[tier(hit)].append(hit)
    for bucket in out.values():
        bucket.sort(key=lambda h: h.worst.low_pct, reverse=True)
    return out
