# VGC Teambuilding Dashboard — Project Outline

**Stack:** Python · DuckDB · Streamlit · Plotly
**Platform:** macOS
**Format:** Pokémon Champions VGC Doubles (current: Regulation M-C, Sep–Dec 2026)
**Last updated:** September 15, 2026

---

## 1. Purpose

You're building a local tool that answers one question fast:

> **"How does my team line up against the current meta?"**

You paste in a PokePaste link, pick any 1–6 Pokémon from it, and see:

- where the team is weak and resistant defensively
- whether your attacks cover the Pokémon people are actually using
- where your Pokémon sit on the speed ladder against the meta
- which common meta Pokémon threaten you the most

Everything rests on **two pillars**:

1. **Usage data (live):** which Pokémon are common and how they're built (moves, items, abilities, spreads).
2. **Pokémon data (static):** base stats, typings, the type chart, and move data.

---

## 2. Scope guardrails

Scope creep is the main risk to this project. These rules exist to keep it finishable.

1. **v1 is four visuals and one input.** The four visuals are listed in section 8. The one input is a PokePaste URL plus a regulation dropdown. Nothing else ships until those work end to end.
2. **New ideas go in the parking lot (section 12), not into code.** Review the parking lot only after v1 is done.
3. **Each new data source needs a working Phase 0-style spike first.** If you can't join it cleanly in an afternoon, it waits.
4. **Build for one user: you.** Don't add accounts, hosting, or polish until you've used the tool for real teambuilding.
5. **Heuristics before models.** Every score in v1 is a transparent formula you can explain in one sentence.

---

## 3. Shared data layer with VFC xV

The VFC xV project (the xG-style bring-4 team preview tool) needs the same usage, set, base-stat, and type data as this dashboard.

**Decision:** build the data pipeline once, as a reusable Python package (`vgc`) that writes to one DuckDB warehouse. This dashboard and the xV model are both consumers of that warehouse.

What this means in practice:

- Ingestion code, ID normalization, and the stat calculator live in `src/vgc/`. Neither app gets its own copy.
- The xV project opens the warehouse **read-only**. DuckDB allows only one writer at a time, so only the refresh script writes.
- Bring-4 recommendations belong to xV. They are not part of this dashboard.

---

## 4. Data sources

### 4.1 v1 sources

| Source | What it gives you | Access | Role |
|---|---|---|---|
| **championsbattledata.com** | Pokémon-level usage and attributes, with Showdown IDs (`showdownId`, `saved_name`, `base_name`) | Bulk zips and dated snapshot folders | **Primary live usage** |
| **Limitless API** (`https://play.limitlesstcg.com/api`) | Tournament list, standings with placings and records, teamlists when submitted | Public REST API | **Tournament usage** |
| **Showdown data files** (`play.pokemonshowdown.com/data/`) | Pokédex (base stats, types, abilities, formes), moves, items, type chart | Static download | **Static layer** |
| **PokePaste** (`pokepast.es`) | Your own team in Showdown export format | Paste URL | **Team input** |

**Limitless endpoints you'll use:**

- `GET /tournaments?game=VGC&format=...&limit=...&page=...` returns tournament IDs.
- `GET /tournaments/{id}/details` returns the format, whether teamlists were used, and the phase structure.
- `GET /tournaments/{id}/standings` returns placing, record, and the teamlist if one is available.
- `GET /tournaments/{id}/pairings` isn't needed for v1, but it's useful later for matchup data and xV.
- Before building, check the developer intro page for access rules and rate limits.

### 4.2 v1.1 source

| Source | What it gives you | Access | Notes |
|---|---|---|---|
| **Smogon chaos JSON** | Showdown ladder usage with moves, items, abilities, spreads, teammates, and checks | `https://www.smogon.com/stats/{YYYY-MM}/chaos/{format}-{rating}.json` | Filenames are **all lowercase**. The M-C format ID should be `gen9championsvgc2026regmc`. The first M-C file (2026-09) is expected in **early October 2026**. |

Smogon also publishes the same data at several rating cutoffs (for example 0, 1500, 1630, 1760). Pick one cutoff and record it. Mixing cutoffs silently will distort your usage numbers.

### 4.3 Reference only (no ingestion)

Use these to sanity-check your numbers, not as data feeds:

- **Pikalytics:** M-C usage, cores, and tournament teams
- **MunchStats**
- **Pokémon Zone:** compiles from Limitless and real-life events
- **MetaVGC** and **Champions Lab**

**Why they're reference only:** they have no official API, and scraping them is fragile and may conflict with their terms of use.

**Sanity check:** your M-C top 5 should roughly match Pikalytics. As of mid-September 2026 that was Rillaboom, Sneasler, Incineroar, Salamence, and Kingambit.

### 4.4 Known data gaps

These gaps in championsbattledata were identified earlier in the xV work. Handle each one explicitly.

| Gap | How to handle it |
|---|---|
| No regulation tagging | Tag the regulation yourself at ingest time, based on snapshot date and the regulation calendar in `config/regulations.yaml`. |
| Undefined "Current" window | Always ingest the **dated** snapshot folders, never "Current". |
| No win rates | Not needed for v1. Limitless standings can provide records later. |
| No team-level data | Limitless teamlists fill this gap. |
| Singles data is mixed in | Filter to Doubles/VGC only at the staging layer. |

---

## 5. Architecture

```
┌──────────────────────── INGEST (Python) ────────────────────────┐
│ static_showdown.py  championsbattledata.py  limitless.py        │
│ pokepaste.py        smogon.py (v1.1)                            │
└───────────────┬─────────────────────────────────────────────────┘
                ▼
     data/raw/{source}/{regulation}/{snapshot_date}/*.json|csv
     (immutable landed files, never edited)
                ▼
┌──────────────────── WAREHOUSE (DuckDB, SQL) ────────────────────┐
│ stg_*   : typed, cleaned, IDs normalized, Singles filtered out  │
│ dim_*   : static reference tables                               │
│ fact_*  : append-only live snapshots                            │
│ mart_*  : views the app reads (threats, coverage, speed tiers)  │
└───────────────┬─────────────────────────────────────────────────┘
                ▼
┌──────────── CONSUMERS (read-only connections) ──────────────────┐
│ Streamlit dashboard (this project)     VFC xV model             │
└─────────────────────────────────────────────────────────────────┘
```

**Principles:**

- **Raw files are immutable.** If a transform is wrong, rerun it from raw. Never re-download history.
- **Transforms are SQL files.** This keeps the logic in your strongest language and makes it reviewable.
- **Every live row carries `source`, `regulation`, and `snapshot_date`.** Regulation rollovers are then just a filter, not a migration.
- **Python handles fetching, parsing, and stat math.** SQL handles joining and aggregating.

---

## 6. Repository layout

```
vgc-teambuilding/
├── pyproject.toml              # managed with uv
├── README.md
├── .gitignore                  # ignores data/raw, *.duckdb, .venv
├── config/
│   ├── regulations.yaml        # reg code → start/end dates, format IDs per source
│   └── settings.yaml           # warehouse path, Smogon rating cutoff, top-N defaults
├── data/
│   ├── raw/                    # landed source files (gitignored)
│   └── warehouse.duckdb        # (gitignored)
├── sql/
│   ├── 00_schema.sql           # DDL for dim/fact tables
│   ├── staging/                # stg_*.sql
│   └── marts/                  # mart_*.sql views
├── src/vgc/
│   ├── __init__.py
│   ├── db.py                   # connect(read_only=...), run_sql_dir()
│   ├── ids.py                  # to_id(), forme/mega resolution
│   ├── stats.py                # calc_stat() — single place for the stat formula
│   ├── typechart.py            # effectiveness(atk_type, def_types, ability=None)
│   ├── scoring.py              # threat and coverage heuristics
│   └── ingest/
│       ├── static_showdown.py
│       ├── championsbattledata.py
│       ├── limitless.py
│       ├── pokepaste.py
│       └── smogon.py           # v1.1
├── scripts/
│   ├── refresh.py              # full pipeline: ingest → stage → marts
│   └── spike_phase0.py
├── app/
│   ├── streamlit_app.py        # entry: paste input + regulation selector
│   └── components/             # one module per visual
├── tests/
│   ├── test_ids.py
│   ├── test_stats.py
│   ├── test_typechart.py
│   └── test_pokepaste.py
└── docs/
    ├── PROJECT_OUTLINE.md      # this file
    ├── DECISIONS.md            # dated log of choices and why
    └── PARKING_LOT.md
```

---

## 7. Data model

### 7.1 Join key: Showdown ID

Every table joins on `pokemon_id`, which is the Showdown ID. To produce one, lowercase the name and strip everything that isn't a letter or digit. For example:

- `Floette-Eternal` → `floetteeternal`
- `Mr. Rime` → `mrrime`

`src/vgc/ids.py` owns this logic. Every ingest module must call it before writing to staging, with no exceptions.

**Forme and Mega handling (open decision, settle in Phase 0):** sources disagree on how to represent Megas. Some list `Salamence-Mega` as its own entry, while others list base Salamence holding a Mega Stone. Proposed rule:

- `pokemon_id` stays at the **battle forme** actually used, for example `salamencemega`.
- A `base_species_id` column (for example `salamence`) allows rolling usage up to the species level.
- `dim_pokemon.is_mega` and `dim_pokemon.base_species_id` make both views possible.

Log the final choice in `DECISIONS.md`.

**Champions-specific formes:** Champions has added new Megas, for example Mega Garchomp Z, which has 151 base Speed, Levitate, and loses its Ground typing. These may be missing from the mainline Showdown `pokedex.json`, or may only exist in a Champions mod data file. Phase 0 must confirm every Pokémon in the M-C top 50 resolves to a `dim_pokemon` row.

### 7.2 Static tables

```sql
CREATE TABLE dim_pokemon (
    pokemon_id       VARCHAR PRIMARY KEY,
    display_name     VARCHAR,
    base_species_id  VARCHAR,
    is_mega          BOOLEAN,
    type1            VARCHAR,
    type2            VARCHAR,          -- NULL if single type
    hp INT, atk INT, def INT, spa INT, spd INT, spe INT,
    abilities        VARCHAR[],
    data_source      VARCHAR,          -- 'showdown' | 'showdown_champions_mod' | 'manual'
    loaded_at        TIMESTAMP
);

CREATE TABLE dim_type_chart (
    atk_type    VARCHAR,
    def_type    VARCHAR,
    multiplier  DOUBLE,                -- 0, 0.5, 1, 2
    PRIMARY KEY (atk_type, def_type)
);

CREATE TABLE dim_move (
    move_id      VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    type         VARCHAR,
    category     VARCHAR,              -- Physical | Special | Status
    base_power   INT,
    accuracy     INT,
    priority     INT,
    target       VARCHAR,              -- used to flag spread moves
    is_spread    BOOLEAN
);

CREATE TABLE dim_item (
    item_id      VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    is_mega_stone BOOLEAN,
    mega_forme_id VARCHAR
);

-- Minimal v1 table: abilities that change type interactions
CREATE TABLE dim_ability_type_modifier (
    ability_id  VARCHAR,
    atk_type    VARCHAR,
    multiplier  DOUBLE,                -- e.g. levitate/ground = 0, thickfat/fire = 0.5
    PRIMARY KEY (ability_id, atk_type)
);
```

**Scope for `dim_ability_type_modifier`:** it's hand-maintained, with roughly 10–15 rows. It covers abilities like Levitate, Flash Fire, Water Absorb, Storm Drain, Volt Absorb, Lightning Rod, Sap Sipper, Thick Fat, and Earth Eater. It's in v1 because Levitate alone changes the type chart for major meta Pokémon. Anything beyond type immunities and resistances goes in the parking lot.

### 7.3 Live tables (append-only)

```sql
CREATE TABLE fact_usage (
    source         VARCHAR,     -- 'cbd' | 'limitless' | 'smogon'
    regulation     VARCHAR,     -- 'M-C'
    snapshot_date  DATE,
    pokemon_id     VARCHAR,
    usage_pct      DOUBLE,
    rank           INT,
    sample_size    INT,         -- teams or battles; record which in DECISIONS.md
    loaded_at      TIMESTAMP,
    PRIMARY KEY (source, regulation, snapshot_date, pokemon_id)
);

CREATE TABLE fact_usage_detail (
    source         VARCHAR,
    regulation     VARCHAR,
    snapshot_date  DATE,
    pokemon_id     VARCHAR,
    detail_type    VARCHAR,     -- 'move' | 'item' | 'ability' | 'spread' | 'teammate'
    detail_value   VARCHAR,     -- move_id, item_id, ability_id, spread string, pokemon_id
    pct            DOUBLE,
    loaded_at      TIMESTAMP,
    PRIMARY KEY (source, regulation, snapshot_date, pokemon_id, detail_type, detail_value)
);

CREATE TABLE fact_tournament (
    tournament_id  VARCHAR PRIMARY KEY,
    name           VARCHAR,
    regulation     VARCHAR,
    event_date     DATE,
    players        INT,
    has_teamlists  BOOLEAN,
    is_online      BOOLEAN,
    loaded_at      TIMESTAMP
);

CREATE TABLE fact_tournament_set (
    tournament_id  VARCHAR,
    player_id      VARCHAR,
    placing        INT,
    wins INT, losses INT, ties INT,
    slot           INT,         -- 1–6
    pokemon_id     VARCHAR,
    item_id        VARCHAR,
    ability_id     VARCHAR,
    moves          VARCHAR[],
    PRIMARY KEY (tournament_id, player_id, slot)
);
```

### 7.4 Your team

```sql
CREATE TABLE my_team (
    paste_id    VARCHAR,
    team_name   VARCHAR,
    slot        INT,
    pokemon_id  VARCHAR,
    nickname    VARCHAR,
    item_id     VARCHAR,
    ability_id  VARCHAR,
    nature      VARCHAR,
    investment  JSON,           -- raw stat investment as parsed; see 7.5
    moves       VARCHAR[],
    loaded_at   TIMESTAMP,
    PRIMARY KEY (paste_id, slot)
);
```

### 7.5 Stat calculation

**Verify before building speed tiers:** Champions does not handle stat investment the same way as the classic EV/IV system. Before Phase 2:

1. Confirm the exact Champions stat formula at level 50, and how investment is represented in a Showdown export for this format.
2. Put the formula in **one function**, `vgc.stats.calc_stat(base, investment, nature_mod, level=50, stat='spe')`.
3. Write `tests/test_stats.py` using at least three known in-game stat values from your own Pokémon.

If the formula is wrong, every speed tier is quietly wrong. Keeping it in a single function makes a correction a one-line change.

### 7.6 Mart views (what the app reads)

| View | Grain | Purpose |
|---|---|---|
| `mart_meta_top` | pokemon × regulation × source (latest snapshot) | Top-N meta list with types and base stats joined |
| `mart_meta_common_moves` | pokemon × move | Damaging moves above a usage threshold (default 20%) |
| `mart_meta_speed` | pokemon × speed variant | Calculated Speed at common spreads, or min / neutral max / positive max bands when spreads are missing |
| `mart_team_defense` | my pokemon × attacking type | Multiplier after abilities are applied |

The threat and coverage scores are computed in Python (`scoring.py`) from these views. That keeps the formulas unit-testable.

---

## 8. v1 features

### Input panel (sidebar)

- **PokePaste URL.** Fetch the paste and parse the Showdown export format into `my_team`.
  - In Phase 0, verify whether `pokepast.es/{id}/json` or `/raw` is the cleaner endpoint.
- **Pokémon selector:** multiselect of 1–6 Pokémon from the paste. Default is all six.
- **Regulation dropdown.** Default is the current regulation.
- **Usage source toggle:** CBD / Limitless / (Smogon in v1.1).
- **Top-N slider.** Default is 20.

### Visual 1: Defensive type grid

- **What it shows:** a heatmap with your selected Pokémon as rows and the 18 attacking types as columns. Cells are colored 0, ¼, ½, 1, 2, or 4.
- **Summary rows:** the count of weak Pokémon and the count of resistant or immune Pokémon, per type.
- **Flag rule:** any type where weak count ≥ 3 **and** resist count = 0.
- **Logic:** the type chart plus abilities, via `typechart.effectiveness()`.
- **Done when:** a paste with a Levitate user shows Ground as 0 for that Pokémon.

### Visual 2: Offensive coverage vs. the meta

- **What it shows:** meta Pokémon (top N) as rows and your selected Pokémon as columns. Each cell is the best effectiveness any of that Pokémon's damaging moves achieves.
- **Weighted gap score:** `usage_pct × (1 if best multiplier < 1 across your whole selection else 0)`, summed. This surfaces "nothing on my team hits Pokémon X super effectively (or even neutrally), and X is on 30% of teams."
- **Done when:** the meta Pokémon with no neutral-or-better hit from your team are highlighted and sorted by usage.

### Visual 3: Speed tier ladder

- **What it shows:** a vertical ladder of calculated Speed stats, with your Pokémon (at their actual investment) highlighted among the top-N meta Pokémon.
- **Meta Pokémon placement:** use common spreads from `fact_usage_detail` when available. Otherwise, show a band from minimum Speed to maximum Speed with a positive nature.
- **Markers:** Choice Scarf users (item usage > 20%) get a ×1.5 marker.
- **Done when:** hovering any point shows the Pokémon, its Speed, the spread assumption, and the source.
- **v1.1:** Tailwind (×2) and Trick Room (reverse order) toggles.

### Visual 4: Threat list

- **What it shows:** a ranked table of meta Pokémon.
- **Heuristic (v1):**
  ```
  for each meta Pokémon m in top N:
      for each of my selected Pokémon t:
          hit(m, t) = max over m's common damaging moves mv of
                      effectiveness(mv.type, t) × (1.5 if mv.type in m.types else 1)
      threat(m) = usage_pct(m) × mean_t( hit(m, t) )
  ```
- **Extra column:** "hits N of your Pokémon super effectively."
- **Done when:** the table is sortable and each row expands to show which move drives the score.

**Limit of the heuristic:** it ignores base power, attacking stats, bulk, and items. It measures type pressure, not damage. Say so in a tooltip. Real damage calculation is in the parking lot.

---

## 9. Phases and acceptance criteria

### Phase 0: Data spike (1 weekend)

**Goal:** prove the joins work before building anything.

- [ ] Set up the environment (next session)
- [ ] Download `pokedex.json`, `moves.json`, `items`, and the type chart from Showdown, and load them into `dim_*`
- [ ] Download one dated M-C snapshot from championsbattledata and land it in `data/raw/cbd/M-C/{date}/`
- [ ] Pull one M-C tournament with teamlists from the Limitless API
- [ ] Parse one of your own PokePastes
- [ ] Settle the Mega and forme ID rule, and log it in `DECISIONS.md`

**Exit criteria:**

- [ ] 100% of the M-C top 50 (CBD) resolve to a `dim_pokemon` row
- [ ] 100% of your paste's Pokémon, items, and moves resolve
- [ ] The Limitless teamlist format is documented (field names, how moves and items appear)

If any of these fail, fix the join logic before moving on. This phase decides whether the project works.

### Phase 1: Static layer and Visual 1

- [ ] `sql/00_schema.sql` with all DDL
- [ ] `ids.py`, `typechart.py`, `pokepaste.py` with tests passing
- [ ] `dim_ability_type_modifier` populated
- [ ] Streamlit app with the sidebar input and Visual 1

**Exit criteria:** you can paste any team and see a correct defensive grid in under 5 seconds.

At the end of Phase 1 the tool is already useful. That's intentional.

### Phase 2: Live usage and Visuals 2–4

- [ ] `championsbattledata.py` ingest with regulation tagging and Singles filtering
- [ ] `limitless.py` ingest: tournaments → standings → `fact_tournament_set`, then aggregated into `fact_usage` with `source='limitless'`
- [ ] `stats.py` verified against in-game values (section 7.5)
- [ ] Mart views built
- [ ] Visuals 2, 3, and 4

**Exit criteria:**

- [ ] Your M-C top 10 roughly matches Pikalytics
- [ ] All four visuals render for a real team
- [ ] The source toggle works

### Phase 3: Refresh and Smogon

- [ ] `scripts/refresh.py` runs the full pipeline idempotently (rerunning never duplicates rows)
- [ ] Optional: schedule it weekly with `launchd`
- [ ] Once the October files are published, add `smogon.py` for `gen9championsvgc2026regmc` at one fixed rating cutoff
- [ ] Add a "data freshness" line to the app: latest snapshot date per source

**Exit criteria:** one command refreshes everything, and the app shows how old each source's data is.

### v1 done

Use it to build or adjust at least one real team before touching the parking lot.

---

## 10. Validation and testing

| Check | How |
|---|---|
| Type chart correctness | Unit tests for known matchups: Ground vs Flying = 0; Fire vs Water/Ground = 0.5; Ice vs Dragon/Flying = 4 |
| Ability overrides | Test that Levitate zeroes Ground and Thick Fat halves Fire and Ice |
| ID resolution | A staging query that lists every `pokemon_id` in `fact_*` with no match in `dim_pokemon`. It must return 0 rows. |
| Stat formula | At least 3 known in-game values |
| Idempotent refresh | Run `refresh.py` twice and confirm row counts are unchanged |
| Usage sanity | Top 10 per source compared by eye against Pikalytics / MunchStats |
| Regulation leakage | No M-B rows appear when M-C is selected |

---

## 11. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Champions-only formes missing from Showdown mainline data | Meta Pokémon silently dropped | Phase 0 exit criteria; `data_source='manual'` fallback rows |
| Champions stat formula differs from mainline | Wrong speed tiers | Single `calc_stat()` plus tests against in-game values |
| Source format changes or site goes down | Refresh breaks | Raw files are immutable, so the last good snapshot keeps working. Each ingest fails loudly instead of partially. |
| Smogon M-C stats not out until October | No ladder data for weeks | CBD and Limitless cover v1. Smogon is v1.1 by design. |
| Mixing sample types (teams vs battles) | Misleading usage comparisons | `sample_size` semantics recorded per source. The app shows one source at a time. |
| Limitless API access limits | Slow or blocked ingest | Check the developer docs. Cache raw responses, and never re-pull completed tournaments. |
| DuckDB write lock when xV also runs | Crashes | Only `refresh.py` writes. All consumers use `read_only=True`. |
| Scope creep | Project never finishes | Section 2 guardrails and the parking lot |

---

## 12. Parking lot (not v1)

Add ideas here instead of building them.

- Damage calculator integration (a real damage-based threat score)
- Tailwind and Trick Room toggles on the speed ladder *(first candidate for v1.1)*
- Intimidate, weather, and terrain adjustments
- Win-rate views from Limitless records
- Teammate cores and common pairs
- Meta trend lines across snapshots (the data model already supports this)
- Head-to-head comparison of two of your own teams
- Replay parsing
- Bring-4 recommendations (**belongs to VFC xV**)
- ML of any kind
- Hosting on Streamlit Community Cloud
- Sprites and visual polish

---

## 13. Decisions log (seed entries)

Copy these into `docs/DECISIONS.md` and keep adding to it.

| Date | Decision | Why |
|---|---|---|
| 2026-09-15 | Python + DuckDB + Streamlit | SQL-first transforms, native on macOS, free hosting option later |
| 2026-09-15 | Power BI ruled out | Power BI Desktop is Windows-only |
| 2026-09-15 | Shared `vgc` data package with VFC xV | Avoids maintaining two pipelines for the same sources |
| 2026-09-15 | Showdown ID as universal join key | CBD already provides `showdownId`, and Showdown data is the static source |
| 2026-09-15 | Ingest dated CBD snapshots only, never "Current" | The "Current" window is undefined |
| 2026-09-15 | Pikalytics and similar sites are reference only | No official API; scraping is fragile |
| 2026-09-15 | Smogon deferred to v1.1 | M-C chaos files not expected until early October 2026 |
| TBD (Phase 0) | Mega and forme ID rule | Sources disagree on representation |
| TBD (Phase 0) | Champions stat formula | Must be verified against in-game values |
| TBD (Phase 3) | Smogon rating cutoff | Pick one and never mix |

---

## 14. Next session: environment setup

Tomorrow's goal is a working, empty skeleton, so that the following session starts directly on Phase 0 data pulls.

1. Install the tooling with Homebrew: `uv`, `git`, and optionally the `duckdb` CLI.
2. Create the repo and the folder structure from section 6.
3. Initialize the project with `uv` and add the dependencies: `duckdb`, `streamlit`, `plotly`, `pandas`, `requests`, `pyyaml`, `pytest`.
4. Add `.gitignore`, `config/regulations.yaml`, and `config/settings.yaml` with M-C (and M-B for history).
5. Create an empty `warehouse.duckdb` and run `sql/00_schema.sql`.
6. Add a "hello world" Streamlit page that connects read-only to the warehouse and lists its tables.
7. Place this outline in `docs/` and add `DECISIONS.md` and `PARKING_LOT.md`.

**Done when:** `uv run streamlit run app/streamlit_app.py` opens in the browser and shows the empty tables, and `uv run pytest` runs (even if no tests exist yet).
