"""Land one dated CBD snapshot.

Usage:
  uv run python scripts/fetch_cbd.py --season M6                  # latest M6 day
  uv run python scripts/fetch_cbd.py --season M6 --date 15_09_2026
Safe to rerun after an interruption: finished files are skipped.
"""

import argparse

from vgc.ingest.championsbattledata import fetch_snapshot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", required=True, help="CBD ranked season, e.g. M6")
    ap.add_argument("--date", default=None, help="DD_MM_YYYY; default = latest for the season")
    ap.add_argument("--format", default=None, help="CBD format; default from regulations.yaml")
    args = ap.parse_args()
    fetch_snapshot(args.season, args.date, args.format)


if __name__ == "__main__":
    main()
