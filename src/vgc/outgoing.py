"""What your team does to the meta — the mirror of vgc.incoming.

Incoming asks "does this kill me". This asks "does this kill them", and the
uncertainty sits on the other foot. For incoming, the unknown was their *offensive*
investment, which is nearly always maxed (modal Atk share 0.887, SpA 0.893). For
outgoing, the unknown is their *defensive* investment, and that is the softest thing
in the whole dataset: modal HP 0.627, Def 0.636, SpD 0.670. Barely two thirds.

So a single damage figure would be misleading in a way the incoming one is not, and
every row reports two:

    likely    against the meta's modal defensive spread and nature
    bulkiest  against 32 HP / 32 in the relevant defence and a boosting nature,
              which is the most any legal Champions build can have

A KO that still lands against `bulkiest` is one you can rely on in a game no matter
what they brought. That distinction is the point of this module, and the app colours
it differently rather than burying it in a number.

Your side is exact: species, nature, investment, item and moves from your paste.
Same exclusions as vgc.damage — no crits, no burn, no screens, no terrain, and
abilities are handled through the generic stat stage rather than individually.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from vgc.damage import (PHYSICAL, Result, attack_after_item, base_power_multiplier,
                        boosted, damage_rolls, defence_after_item, damage_multiplier,
                        seed_boost, FOCUS_SASH,
                        spreads_in_terrain, weather_move, weather_multiplier)
from vgc.db import session
from vgc.megas import Forme
from vgc.metafilter import MetaFilter
from vgc.offense import Threat, threats
from vgc.stats import calc_stat, nature_mod, sp_from_investment
from vgc.team import Member
from vgc.typechart import attack_type, effectiveness

BUILD_CMD = "uv run python scripts/build_marts.py"
MAX_SP = 32
BOOSTING = 1.1

ALWAYS, LIKELY, NEVER = "Always", "Usually", "No KO"


@dataclass(frozen=True)
class Outgoing:
    move_id: str
    attacker_slot: int
    attacker_name: str
    attacker_forme_id: str
    threat: Threat
    likely: Result      # against their common bulk
    bulkiest: Result    # against the most defensive legal build

    @property
    def always_kos(self) -> bool:
        """KOs in one hit even at their maximum investment — relies on nothing."""
        return self.bulkiest.low >= self.bulkiest.defender_hp

    @property
    def likely_kos(self) -> bool:
        return self.likely.low >= self.likely.defender_hp

    @property
    def certainty(self) -> str:
        if self.always_kos:
            return ALWAYS
        return LIKELY if self.likely_kos else NEVER

    @property
    def hits_to_ko(self) -> int | None:
        """Guaranteed hits to KO their common build."""
        return self.likely.guaranteed_hits

    @property
    def hits_to_ko_bulkiest(self) -> int | None:
        return self.bulkiest.guaranteed_hits


def _meta_bulk(regulation: str, filt: MetaFilter) -> dict:
    with session() as con:
        try:
            inv = con.execute(f"""
                select pokemon_id, stat, sp from {filt.call('meta_investment')}
                where stat in ('hp', 'def', 'spd')
            """, filt.params(regulation)).fetchall()
            nat = con.execute("""
                select pokemon_id, detail_value from (
                    select pokemon_id, detail_value,
                           row_number() over (partition by pokemon_id
                                              order by pct desc, detail_value) as rn
                    from mart_build_detail where detail_type = 'nature')
                where rn = 1
            """).fetchall()
            item = con.execute("""
                select pokemon_id, detail_value from (
                    select pokemon_id, detail_value,
                           row_number() over (partition by pokemon_id
                                              order by pct desc, detail_value) as rn
                    from mart_build_detail where detail_type = 'item')
                where rn = 1
            """).fetchall()
            base = con.execute(
                'select pokemon_id, hp, "def", spd from dim_pokemon').fetchall()
        except Exception as e:  # noqa: BLE001
            raise LookupError(f"The meta marts are not built. Run: {BUILD_CMD}") from e
    sp: dict[str, dict[str, int]] = {}
    for pid, stat, value in inv:
        sp.setdefault(pid, {})[stat] = int(value)
    return {"sp": sp, "nature": dict(nat), "item": dict(item),
            "base": {r[0]: r[1:] for r in base}}


def _my_moves(team: Sequence[Member]) -> dict[int, list[tuple]]:
    with session() as con:
        rows = con.execute("""
            select move_id, display_name, type, category, base_power, is_spread
            from dim_move
        """).fetchall()
    by_id = {r[0]: (r[0], *r[1:]) for r in rows}
    out: dict[int, list[tuple]] = {}
    for member in team:
        picked = []
        for move_id in (member.moves or []):
            info = by_id.get(move_id)
            if info and info[4] and int(info[4]) > 0:
                picked.append(info)
        out[member.slot] = picked
    return out


def outgoing(regulation: str, team: Sequence[Member], formes: Sequence[Forme],
             filt: MetaFilter | None = None, top_n: int = 20,
             weather: str | None = None, atk_stage: int = 0, def_stage: int = 0,
             terrain: str | None = None, per_move: bool = False) -> list[Outgoing]:
    """Your best hit on each meta threat, from each of your Pokémon."""
    filt = filt or MetaFilter()
    meta = threats(regulation, top_n, filt)
    if not meta:
        return []
    bulk = _meta_bulk(regulation, filt)
    moves = _my_moves(team)
    by_slot = {m.slot: m for m in team}

    with session() as con:
        my_base = {r[0]: r[1:] for r in con.execute(
            'select pokemon_id, atk, spa from dim_pokemon').fetchall()}

    out: list[Outgoing] = []
    for forme in formes:
        member = by_slot[forme.slot]
        sp = sp_from_investment(member.investment)
        atk_b, spa_b = my_base[forme.forme_id]

        for move_id, name, move_type_raw, category, base_power, spread in moves[forme.slot]:
            # The move reads the weather before the ability does: Weather Ball is
            # Water in rain even on an Aerilate holder.
            move_type_raw, base_power = weather_move(
                move_id, move_type_raw, int(base_power), weather)
            move_type = attack_type(move_type_raw, forme.ability_id)
            key = "atk" if category == PHYSICAL else "spa"
            raw = calc_stat(atk_b if category == PHYSICAL else spa_b,
                            sp[key], nature_mod(member.nature, key), stat=key)
            attack = attack_after_item(boosted(raw, atk_stage), member.item_id, category)

            for threat in meta:
                hp_b, def_b, spd_b = bulk["base"][threat.forme_id]
                species = threat.species_id or threat.forme_id
                their_sp = bulk["sp"].get(species, {})
                their_nat = bulk["nature"].get(species)
                their_item = bulk["item"].get(species)
                dkey = "def" if category == PHYSICAL else "spd"
                dbase = def_b if category == PHYSICAL else spd_b

                likely_hp = calc_stat(hp_b, their_sp.get("hp", 0), 1.0, stat="hp")
                likely_def = calc_stat(dbase, their_sp.get(dkey, 0),
                                       nature_mod(their_nat, dkey), stat=dkey)
                # The most any legal build can have: 32 HP and 32 in that defence is
                # 64 of the 66 SP, plus a nature that boosts it.
                bulk_hp = calc_stat(hp_b, MAX_SP, 1.0, stat="hp")
                bulk_def = calc_stat(dbase, MAX_SP, BOOSTING, stat=dkey)

                mult = effectiveness(move_type, threat.types, threat.ability_id)
                stab = move_type in forme.types

                def roll(defence: int, hp: int) -> Result:
                    return Result(name, move_type, damage_rolls(
                        base_power=base_power,
                        attack=attack,
                        defense=defence_after_item(
                            boosted(defence, def_stage
                                    + seed_boost(their_item, terrain, dkey)),
                            their_item, category),
                        type_mult=mult, stab=stab, spread=bool(spread) or spreads_in_terrain(terrain, move_id),
                        weather_mult=weather_multiplier(weather, move_type),
                        final_mult=damage_multiplier(member.item_id, their_item,
                                                     move_type, mult),
                        base_power_mult=base_power_multiplier(
                            member.item_id, move_type, terrain, move_id)),
                        hp, mult, stab,
                        defender_sash=their_item == FOCUS_SASH)

                out.append(Outgoing(
                    move_id=move_id, attacker_slot=forme.slot, attacker_name=forme.display_name,
                    attacker_forme_id=forme.forme_id, threat=threat,
                    likely=roll(likely_def, likely_hp),
                    bulkiest=roll(bulk_def, bulk_hp)))

    if per_move:
        # Every move against every threat, for "pick one attacker and one move".
        return sorted(out, key=lambda h: h.bulkiest.low_pct, reverse=True)

    # One row per (your Pokemon, threat): the move that kills fastest through bulk.
    best: dict[tuple[int, str], Outgoing] = {}
    for hit in out:
        key = (hit.attacker_slot, hit.threat.forme_id)
        cur = best.get(key)
        if cur is None or hit.bulkiest.low > cur.bulkiest.low:
            best[key] = hit
    return sorted(best.values(), key=lambda h: h.bulkiest.low_pct, reverse=True)
