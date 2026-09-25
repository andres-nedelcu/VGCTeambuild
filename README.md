# VGC Teambuilding Dashboard

Local tool for answering: **"How does my team line up against the current Pokémon Champions VGC meta?"**

See `docs/PROJECT_OUTLINE.md` for scope, data model, and phases.

## Setup (macOS)

```bash
brew install uv git duckdb          # duckdb CLI is optional
uv sync                             # creates .venv and installs everything
uv run python scripts/init_warehouse.py
uv run pytest
uv run streamlit run app/streamlit_app.py
```

## Keeping the meta current

```bash
uv run python scripts/refresh.py              # fetch, load and rebuild everything
uv run python scripts/refresh.py --no-fetch   # rebuild offline from what is landed
uv run python scripts/check_meta_stability.py # is the ranking trustworthy yet?
```

Every step is idempotent, so rerunning after an interruption is always safe, and
completed tournaments are never re-pulled. Weekly is a sensible cadence; to
automate it, see `ops/local.vgc.refresh.plist`.

The app header shows how old each source is.

## Rules of the road

- Only `scripts/refresh.py` (and `init_warehouse.py`) write to the warehouse. Everything else opens it read-only.
- Raw files in `data/raw/` are never edited. Fix transforms and rerun.
- New ideas go in `docs/PARKING_LOT.md`, not in code.

## How this was built

This project was built over seven working days with Claude (Opus 5) as a coding
pair. The split is worth stating plainly, because the repository records it either
way:

- **I owned** direction, domain judgement, priorities, constraints and acceptance —
  what the tool should say, and whether what it says is true.
- **Claude wrote** the code, SQL, tests and pipeline scripts, and drafted the docs.

Commits Claude co-authored carry a `Co-Authored-By` trailer, so `git log` shows the
division of labour directly.

The document I would actually point at is `docs/DECISIONS.md`: 147 dated entries,
each recording a consequential call and the reasoning behind it, including the ones
that turned out to be wrong and why they were reversed. A few that shaped everything
downstream:

- **Usage ranking comes from tournament teamlists, not the ranked ladder.** The two
  metas genuinely differ, and event preparation is the actual use case.
- **Offline operation is a hard requirement, not a nice-to-have.** Sprites are cached
  and committed rather than hotlinked, and a test blocks network sockets and drives
  every tab.
- **Exactly one script may write to the warehouse.** Everything else opens it
  read-only, which is what makes every step safe to rerun after an interruption.
- **The tool refuses to claim more than the data supports.** `check_meta_stability.py`
  exists to answer whether the ranking is trustworthy yet, rather than presenting a
  thin sample as if it were settled.

375 tests cover the damage engine against a pinned Pokémon Showdown checkout, the
ingest and transform pipeline, and the app itself.
