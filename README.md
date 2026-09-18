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
