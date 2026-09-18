"""Full pipeline in one command: fetch -> load -> marts.

Usage:
  uv run python scripts/refresh.py                # fetch, load, rebuild
  uv run python scripts/refresh.py --no-fetch     # rebuild from what is already landed
  uv run python scripts/refresh.py --max 30       # land more tournaments this run

Every step is idempotent, so an interrupted run is fixed by running it again.

Fetch steps are allowed to fail without stopping the run: no network, or a CBD
season that is not published yet, should still leave you with a rebuilt warehouse
from whatever is already on disk. Load and mart steps are required, and the exit
code is non-zero if any step failed, so a scheduled run surfaces problems.
"""

import argparse
import subprocess
import sys
from datetime import date

from vgc.freshness import sources
from vgc.regulations import current, load as load_regulations

HERE = "scripts"


def run(title: str, argv: list[str], required: bool) -> bool:
    print(f"\n=== {title} ===", flush=True)
    code = subprocess.run([sys.executable, *argv]).returncode
    if code:
        print(f"--- {title}: FAILED (exit {code})"
              f"{'' if required else ' — continuing, this step is optional'}", flush=True)
    return code == 0


def fetch_cbd(regulation: str) -> bool:
    """Try the regulation's CBD seasons newest first; later ones may not exist yet."""
    seasons = load_regulations()["regulations"][regulation].get("cbd_seasons") or []
    for season in reversed(seasons):
        if run(f"fetch CBD {season}", [f"{HERE}/fetch_cbd.py", "--season", season], False):
            return True
    print(f"--- no CBD season landed for {regulation} (tried {list(reversed(seasons))})")
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regulation", default=current())
    ap.add_argument("--max", type=int, default=20, help="max new tournaments to land")
    ap.add_argument("--pages", type=int, default=3, help="tournament list pages to scan")
    ap.add_argument("--no-fetch", action="store_true", help="skip the network steps")
    args = ap.parse_args()
    reg = args.regulation

    failures = []
    if not args.no_fetch:
        if not fetch_cbd(reg):
            failures.append("fetch CBD")
        if not run("fetch Limitless tournaments",
                   [f"{HERE}/fetch_limitless.py", "--regulation", reg,
                    "--max", str(args.max), "--pages", str(args.pages)], False):
            failures.append("fetch Limitless")

    for title, argv in (
        ("load CBD", [f"{HERE}/load_cbd.py", reg]),
        ("load Limitless", [f"{HERE}/load_limitless.py", "--regulation", reg]),
        ("build marts", [f"{HERE}/build_marts.py"]),
    ):
        # Keep going after a failure: the marts are views, so rebuilding them on
        # partially reloaded facts still leaves the app working.
        if not run(title, argv, True):
            failures.append(title)

    print(f"\n=== data freshness ({reg}) ===")
    today = date.today()
    for s in sources(reg):
        stamp = s.as_of.isoformat() if s.as_of else "—"
        print(f"  {s.name:<24} {stamp:<12} {s.age_label(today):<10} {s.detail}")

    if failures:
        print(f"\nFAILED steps: {', '.join(failures)}")
        raise SystemExit(1)
    print("\nrefresh complete")


if __name__ == "__main__":
    main()
