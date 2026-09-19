"""Swaps: who comes out, who goes in, and what the trade costs.

The "what to add" view assumes a free slot. A locked team has none, so every addition
is really a swap — and the Pokémon leaving takes its contributions with it. A
candidate that closes two coverage holes is not obviously good if the one it replaces
was the team's only answer to something else.

So this reports both directions and does not net them into a verdict:

    closes   threats nothing on the team hit super effectively, that the incoming does
    opens    threats the OUTGOING was the only answer to, which become holes
    clears   flagged types (3+ weak, none resist) the swap resolves
    raises   flagged types the swap creates

Sorted by net holes, then net flags, then synergy — the same lexicographic rule the
add view uses, for the same reason: forsaking one matchup to cover a more important
one is a judgement call about *your* priorities, and a weighted score would quietly
make it for you.

One asymmetry worth stating wherever this is shown: your Pokémon are evaluated with
the moves in your paste, a candidate with the meta's commonly-run moves. The
comparison is "my actual Gardevoir" against "a typical Archaludon".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from vgc.cores import best_synergy, synergy_sources
from vgc.defense import defense_matrix, flagged_types, summarize
from vgc.megas import Forme, load_dex
from vgc.metafilter import MetaFilter
from vgc.offense import Attacker, Threat, attackers, coverage_matrix, holes, threats
from vgc.pressure import common_moves
from vgc.speed import meta_speed, team_speeds
from vgc.team import Member
from vgc.typechart import attack_type


@dataclass(frozen=True)
class Swap:
    out_slot: int
    out_name: str
    out_species_id: str
    in_forme_id: str
    in_species_id: str
    in_name: str
    in_usage: float
    holes_closed: tuple[str, ...]
    holes_opened: tuple[str, ...]
    out_sole_cover: tuple[str, ...]   # what the outgoing is the ONLY answer to
    flags_cleared: tuple[str, ...]
    flags_raised: tuple[str, ...]
    partner: str | None
    lift: float
    out_speed: int | None
    in_likely_speed: int | None

    @property
    def net_holes(self) -> int:
        return len(self.holes_closed) - len(self.holes_opened)

    @property
    def net_flags(self) -> int:
        return len(self.flags_cleared) - len(self.flags_raised)

    @property
    def rank_key(self) -> tuple:
        return (self.net_holes, self.net_flags, self.lift, self.in_usage)


def _move_types(threat: Threat, moves_by_forme) -> tuple[str, ...]:
    moves = moves_by_forme.get(threat.forme_id, [])
    return tuple(dict.fromkeys(
        attack_type(listed, threat.ability_id) for _i, _n, listed, _s in moves))


def sole_coverage(regulation: str, team: Sequence[Member], formes: Sequence[Forme],
                  filt: MetaFilter | None = None, top_n: int = 20) -> dict[int, tuple[str, ...]]:
    """slot -> threats that Pokémon is the team's ONLY super-effective answer to.

    The standing cost of removing it, independent of whoever replaces it. Every hole
    a swap opens is drawn from this set, so it is the right thing to look at first
    when deciding who can be afforded off the team at all.
    """
    filt = filt or MetaFilter()
    meta = threats(regulation, top_n, filt)
    if not meta:
        return {}
    base = attackers(team, formes)
    base_holes = set(holes(coverage_matrix(base, meta)))
    out = {}
    for a in base:
        kept = [x for x in base if x.slot != a.slot]
        opened = set(holes(coverage_matrix(kept, meta))) - base_holes if kept else set()
        out[a.slot] = tuple(sorted(opened))
    return out


def swaps(regulation: str, team: Sequence[Member], formes: Sequence[Forme],
          filt: MetaFilter | None = None, top_n: int = 20,
          out_slot: int | None = None) -> list[Swap]:
    """Every (out, in) swap worth considering, best first.

    `out_slot` limits it to replacing one Pokémon; None considers all of them.
    """
    filt = filt or MetaFilter()
    meta = threats(regulation, top_n, filt)
    if not meta:
        return []

    dex = load_dex()
    moves_by_forme = common_moves(regulation, filt)
    base_attackers = attackers(team, formes)
    base_holes = set(holes(coverage_matrix(base_attackers, meta)))
    base_flags = set(flagged_types(summarize(defense_matrix(formes))))

    mine = {m.pokemon_id for m in team}
    by_slot = {m.slot: m for m in team}
    # Attributed once, then filtered per slot: querying the cores marts inside the
    # slot loop cost about a second of the render, for identical data each time.
    sources = synergy_sources(regulation, [(m.pokemon_id, m.item_id) for m in team], filt)
    speeds = {s.slot: s.speed for s in team_speeds(team, formes)}
    likely = dict(zip(*(lambda df: (df["display_name"], df["likely_spe"]))(
        meta_speed(regulation, None, filt))))

    slots = [f.slot for f in formes] if out_slot is None else [out_slot]
    out: list[Swap] = []

    for slot in slots:
        leaving = next((f for f in formes if f.slot == slot), None)
        if leaving is None:
            continue
        kept_formes = [f for f in formes if f.slot != slot]
        kept_attackers = [a for a in base_attackers if a.slot != slot]
        synergy = best_synergy(sources, exclude=by_slot[slot].pokemon_id)
        # Holes that open from the removal alone. Every hole a swap opens is one of
        # these, so it is the standing cost of taking this Pokemon off the team.
        sole = tuple(sorted(
            set(holes(coverage_matrix(kept_attackers, meta))) - base_holes))

        for c in meta:
            if c.species_id in mine or c.forme_id in mine:
                continue
            species = dex.get(c.forme_id)
            incoming = Forme(slot, c.species_id, c.forme_id, c.display_name, c.types,
                             c.ability_id, bool(species.is_mega) if species else False)
            attacker = Attacker(slot, c.display_name, _move_types(c, moves_by_forme))

            new_holes = set(holes(coverage_matrix(kept_attackers + [attacker], meta)))
            new_flags = set(flagged_types(summarize(defense_matrix(kept_formes + [incoming]))))

            partner, lift = synergy.get(c.species_id, (None, 0.0))
            speed = likely.get(c.display_name)
            out.append(Swap(
                out_slot=slot,
                out_name=leaving.display_name,
                out_species_id=by_slot[slot].pokemon_id,
                in_forme_id=c.forme_id,
                in_species_id=c.species_id,
                in_name=c.display_name,
                in_usage=c.usage_pct,
                holes_closed=tuple(sorted(base_holes - new_holes)),
                holes_opened=tuple(sorted(new_holes - base_holes)),
                out_sole_cover=sole,
                flags_cleared=tuple(sorted(base_flags - new_flags)),
                flags_raised=tuple(sorted(new_flags - base_flags)),
                partner=partner,
                lift=lift,
                out_speed=speeds.get(slot),
                in_likely_speed=None if speed is None or speed != speed else int(speed),
            ))

    return sorted(out, key=lambda s: s.rank_key, reverse=True)
