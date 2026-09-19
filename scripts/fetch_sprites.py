"""Fetch gen5 sprites into data/sprites/gen5/, with a fallback for the 10 formes
Phase A found with no sprite (see docs/briefs/6.2-sprites.md).

Reads data/sprites/coverage.json (from check_sprite_coverage.py) rather than
hitting the warehouse itself — safe to run with no writer lock held.
Idempotent: rerunning skips every file already on disk.

Usage: uv run python scripts/fetch_sprites.py [--delay 0.15]
"""

import argparse

from vgc.ingest.sprites import fetch_all


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.15, help="seconds between requests")
    args = ap.parse_args()

    counts = fetch_all(delay=args.delay)
    print(f"{counts['downloaded']} downloaded, {counts['built']} fallbacks built, "
          f"{counts['skipped']} already on disk.")


if __name__ == "__main__":
    main()
