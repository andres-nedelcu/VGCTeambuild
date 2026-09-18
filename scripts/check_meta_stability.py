"""How much can you trust the current meta ranking? Read-only.

Usage: uv run python scripts/check_meta_stability.py [--regulation M-C] [--top 12]

Resamples the landed tournaments two ways:
  team-level        every team treated as independent (optimistic)
  tournament-level  whole events resampled, so teams that shared an event, an
                    organiser and a date stay together (honest)

A species whose tournament-level range is much wider than its team-level range is
not merely noisy: it is popular at some events and rare at others, so landing more
*events* will settle it while landing more teams will not.
"""

import argparse
import random
from collections import Counter, defaultdict

from vgc.db import connect
from vgc.regulations import current


def ranking(sample: list[list[str]]) -> list[tuple[str, float]]:
    counts = Counter(species for team in sample for species in team)
    return [(s, n / len(sample)) for s, n in counts.most_common()]


def bootstrap(by_event: dict[str, list[list[str]]], runs: int, cluster: bool):
    events, pct, ranks = list(by_event), defaultdict(list), defaultdict(list)
    teams = [t for v in by_event.values() for t in v]
    for _ in range(runs):
        if cluster:
            sample = [t for e in random.choices(events, k=len(events)) for t in by_event[e]]
        else:
            sample = random.choices(teams, k=len(teams))
        for position, (species, share) in enumerate(ranking(sample), 1):
            pct[species].append(share)
            ranks[species].append(position)
    return pct, ranks


def interval(values: list, lo: float = 0.025, hi: float = 0.975):
    ordered = sorted(values)
    return ordered[int(lo * len(ordered))], ordered[int(hi * len(ordered))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regulation", default=current())
    ap.add_argument("--runs", type=int, default=800)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    random.seed(args.seed)

    con = connect(read_only=True)
    try:
        rows = con.execute("""
            select s.tournament_id, s.player_id, list(distinct s.pokemon_id)
            from fact_tournament_set s
            join fact_tournament t on t.tournament_id = s.tournament_id
            where t.regulation = ?
            group by 1, 2
        """, [args.regulation]).fetchall()
    finally:
        con.close()
    if not rows:
        raise SystemExit(f"No landed teams for {args.regulation}. Run load_limitless.py first.")

    by_event = defaultdict(list)
    for tournament_id, _player, species in rows:
        by_event[tournament_id].append(species)
    actual = ranking([t for v in by_event.values() for t in v])
    print(f"{len(rows)} teams across {len(by_event)} tournaments ({args.regulation})\n")

    for label, cluster in (("TEAM-LEVEL (optimistic)", False),
                           ("TOURNAMENT-LEVEL (honest)", True)):
        pct, ranks = bootstrap(by_event, args.runs, cluster)
        print(f"=== {label} ===")
        print(f"{'species':<16}{'usage':>7}{'95% range':>17}{'rank range':>13}")
        for species, share in actual[:args.top]:
            lo, hi = interval(pct[species])
            rlo, rhi = interval(ranks[species])
            print(f"{species:<16}{100*share:>6.1f}%{100*lo:>8.1f}-{100*hi:<8.1f}"
                  f"{f'{rlo}-{rhi}':>13}")
        settled = [s for s, _ in actual[:args.top] if interval(ranks[s])[0] == interval(ranks[s])[1]]
        print(f"  ranks that never move: {', '.join(settled) or 'none'}\n")


if __name__ == "__main__":
    main()
