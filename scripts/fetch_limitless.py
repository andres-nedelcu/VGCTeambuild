"""Land Limitless tournaments for a regulation.

Usage:
  uv run python scripts/fetch_limitless.py --max 1                    # largest finished M-C event
  uv run python scripts/fetch_limitless.py --id 6aa0490ba4272c53be64aec8
  uv run python scripts/fetch_limitless.py --max 10 --pages 2
Completed tournaments are never re-pulled.
"""

import argparse

from vgc.ingest.limitless import fetch
from vgc.regulations import current


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regulation", default=current())
    ap.add_argument("--id", default=None, help="land one specific tournament")
    ap.add_argument("--max", type=int, default=1, help="max new tournaments to land")
    ap.add_argument("--min-players", type=int, default=16)
    ap.add_argument("--pages", type=int, default=1, help="list pages to scan (100 per page)")
    args = ap.parse_args()
    fetch(args.regulation, max_new=args.max, min_players=args.min_players,
          pages=args.pages, tournament_id=args.id)


if __name__ == "__main__":
    main()
