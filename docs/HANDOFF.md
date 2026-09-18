# VGC Teambuilding — state at end of v1, and what's next

Written 2026-09-18, at the end of the session that completed Phases 2 and 3.
Read this first, then `DECISIONS.md` (why things are the way they are) and
`PROJECT_OUTLINE.md` (original scope and data model).

---

## 1. What this is

A local teambuilding tool answering **"how does my team line up against the
current Pokémon Champions VGC meta?"** Built for Andres, who plays ranked ladder
regularly and is preparing for locals this season with the goal of **making Day 2
of the Toronto Regional in April**.

That goal drives one important choice: **the meta rates come from tournament
teamlists, not the ranked ladder.** The ladder and tournament metas genuinely
differ (see §5), and tournament data is the right reference for event prep.

---

## 2. Current state

Everything in Phases 0–3 is done. Four visuals, two live data sources, a
one-command refresh. 155 tests passing.

### Data currently landed (M-C)

| | |
|---|---|
| Tournaments | 19 events, 1,553 teams, 9,318 teamlist rows |
| Champions Battle Data | 262 species, snapshot 2026-09-19 |
| Detail rows | 13,650 (move / item / ability / nature / spread) |

### The four visuals

| Tab | Question it answers | Source module |
|---|---|---|
| Defensive grid | What types threaten my team? | `vgc/defense.py` |
| Offensive coverage | Can I hit the meta's threats? | `vgc/offense.py` |
| Speed tiers | Who do I outspeed? | `vgc/speed.py` |
| Threat list | How hard does the meta hit me? | `vgc/pressure.py` |

### Which source feeds what — this trips people up

| What you see | Source | Population |
|---|---|---|
| Usage ranking, who counts as a threat | **Limitless tournaments only** | 1,553 tournament teams |
| Builds: moves, items, abilities, Scarf flag, Mega stone share | **CBD preferred**, Limitless teamlists as fallback | Champions ranked ladder |
| Base stats, types, type chart, move data, stone→forme map | **Showdown `champions` mod**, pinned `c23d2e9` | Static reference |
| Your team | A PokePaste loaded via `scripts/load_paste.py` | — |

**No Showdown/Smogon ladder usage data is used anywhere.** Smogon is deferred
until the M-C files publish in October.

### Pipeline

```
fetch_cbd.py ─┐                      ┌─ load_cbd.py ─┐
              ├─→ data/raw/ (JSON) ──┤               ├─→ DuckDB facts ─→ marts ─→ app
fetch_limitless.py ─┘                └─ load_limitless.py ─┘
```

All of it runs with one command:

```bash
uv run python scripts/refresh.py              # fetch, load, rebuild
uv run python scripts/refresh.py --no-fetch   # rebuild offline from what's landed
uv run python scripts/check_meta_stability.py # is the ranking trustworthy yet?
uv run streamlit run app/streamlit_app.py
```

Every loader is idempotent — proven by running twice and diffing row counts.
Completed tournaments are never re-pulled.

---

## 3. Load-bearing decisions

Full list in `DECISIONS.md`. The ones most likely to matter next:

- **Usage weight is Limitless-only.** CBD publishes no species ranking, so there
  is nothing to rank with. This killed the outline's "source toggle" criterion,
  which is logged as dropped.
- **Megas are split into forme variants in the marts.** Every source lists base
  species + stone; the mart divides a species' usage by stone share and drops
  variants under 10%. So `Salamence-Mega` and `Salamence` are separate rows.
- **Speed benchmarks come from base Speed alone** — max +Spe / max neutral /
  uninvested / uninvested −Spe, plus Choice Scarf on the two max columns. CBD is
  used *only* to flag when Scarf is common (>20%). This deliberately quarantines
  uncertainty: CBD never produces a Speed number, so it can only move a marker.
- **Type pressure, not damage.** Visuals 2 and 4 ignore base power, attacking
  stats, bulk and items. Stated in both captions.
- **Teamlist junk is dropped and reported, not fatal.** Species is the join key
  and still fails the load; item/ability/move typos are counted and printed
  (22 in 5,928 entries last run). `id_aliases.yaml` is reserved for *systematic*
  source differences — not for one player's misspelling.

---

## 4. Gotchas that cost time in this session

- **Streamlit caches imported modules.** After editing anything in `src/vgc/`,
  restart the server — a reload is not enough. An `AttributeError` that
  contradicts the code on disk is always this.
- **Sprites for Champions-only Megas probably don't exist anywhere** (see §6.2).
- **`fact_usage` is a precomputed rollup with no filter dimensions.** This is the
  single most important fact for the next phase — see §6.1.
- **Champions stat formula**: HP = base+SP+75, others = floor((base+SP+20) ×
  nature). SP caps at 32/stat, 66 total. Verified against a 31-row speed-tier
  reference table (186 values, exact) which is pinned in
  `tests/test_speed_tiers.py`. Both the Python and SQL copies are checked
  against each other, so they can't drift.
- **Abilities that retype moves** (Aerilate, Pixilate, Refrigerate, Galvanize)
  are hardcoded in `vgc/typechart.py` because Showdown implements them as code,
  not data. Missing this had Salamence-Mega ranked 5th instead of 3rd.
- **Regulation M-C ends 2026-12-02.** April's Toronto Regional will be a later
  regulation; add its dates and name patterns to `config/regulations.yaml` when
  announced. Nothing else needs to change.

---

## 5. How trustworthy is the meta right now

From `check_meta_stability.py`, which bootstraps both by team and by whole
tournament (the latter is the honest one — teams at one event aren't independent):

- **Locked:** Rillaboom 1st, Sneasler 2nd, Salamence 3rd — never move.
- **Stable band:** Incineroar / Kingambit / Basculegion shuffle within 4–6.
- **Separating:** Indeedee-F now clearly 7th (was lost in a 5-way tie).
- **Still noisy:** Gholdengo (14.9–22.5%) and Arcanine-Hisui (13.2–20.2%) swing a
  lot *between events* — they need more **events**, not more teams.

Rule of thumb: **~25–30 events / ~3,000 teams** should settle the top 15.
Currently at 19 / 1,553.

Sanity check against the in-game ladder ranking: the top 7 match exactly once
Indeedee-F and Indeedee-M are combined (the game aggregates formes, we split
them). Divergence below that is a real ladder-vs-tournament difference.

---

## 6. Roadmap

Ratings: **Usefulness** = does it change teambuilding decisions.
**QoL** = does it make the tool nicer to use. **Complexity** = build effort.

### Tier 1 — do these first

| # | Item | Useful | QoL | Complexity |
|---|---|---|---|---|
| 6.1 | Meta-side filtering (top cut, event size, recency) | **High** | **High** | Medium |
| 6.2 | Sprites | Medium | **High** | Low–Medium |
| 6.3 | Visual and chart polish | Low–Med | **High** | Low–Medium |
| 6.4 | Speed control toggle (Tailwind / Trick Room) | **High** | Medium | Low–Medium |

#### 6.1 Meta-side filtering — the highest-value item

Right now the only meta filter is a top-N slider. Worth adding:

- **Top-cut only** — "what did teams that actually won bring". Arguably a better
  signal for regional prep than all-teams usage.
- **Event size** — a 27-player local and a 266-player major shouldn't count equally.
- **Recency** — last 2 weeks vs the whole regulation, to catch a shifting meta.
- **Specific events** — isolate one major.

**Critical technical note:** `fact_usage` is a *precomputed rollup* — one row per
species per regulation, with no placement, date or event-size dimension. You
cannot filter it. But `fact_tournament_set` has everything you need
(`placement`, `wins/losses/ties`, joined to `fact_tournament.event_date` and
`.players`), and it's only 9,318 rows — DuckDB aggregates that in single-digit
milliseconds.

So the move is: **replace the marts' dependence on `fact_usage` with a
parameterised aggregation over `fact_tournament_set`**, computed per filter
selection. `fact_usage` can stay as the unfiltered default. This is a refactor of
`mart_meta_top` (and everything downstream reads from that, so the other three
tabs inherit the filters for free).

Two things already loaded and completely unused that this unlocks:
- **`wins/losses/ties` per player** — usage weighted by actual performance.
- **`placement`** — top-cut filtering.

#### 6.2 Sprites

Showdown serves sprites at predictable URLs
(`play.pokemonshowdown.com/sprites/gen5/<id>.png`), so this is mostly plumbing.

**Flag before starting:** Champions invented new formes — `Garchomp-Mega-Z`,
`Golisopod-Mega`, `Floette-Mega`, `Raichu-Mega-X/Y`. Sprites for these **probably
do not exist on Showdown or anywhere else**, because the game is new. Budget for
a fallback (base-species sprite with a Mega badge, or a type-coloured chip) and
decide the rule before building. Check coverage first — it's one script over
`dim_pokemon` — rather than discovering it halfway through.

Also decide hotlink vs local cache. Local cache is friendlier (works offline,
no dependency on Showdown's CDN) and the file count is small.

#### 6.3 Visual and chart polish

Current state is functional but inconsistent: Visuals 1 and 2 are Plotly
heatmaps, Visuals 3 and 4 are styled dataframes. Worth doing:

- One shared colour system. There's already a convention worth keeping: **green
  is always good for you** — the defensive grid and coverage grid deliberately
  invert their scales to preserve it.
- Threat names on the coverage grid are angled and cramped at 20+ columns;
  sprites (6.2) would fix this better than any font tweak.
- The Speed table has 10 columns and scrolls horizontally on narrow windows.
- Consider whether the Threat list's progress-bar column earns its width.

#### 6.4 Speed control toggle

Already parked with design notes. Tailwind doubles a side's Speed; Trick Room
inverts the comparison. Two open questions: whether it applies to your side,
theirs or both, and that the verdict wording must invert ("You outspeed" →
"You move first"). Speed control is on most VGC teams, so the current plain
Speed order is really only the neutral case.

### Tier 2 — strong value, more work

| # | Item | Useful | QoL | Complexity |
|---|---|---|---|---|
| 6.5 | Use the CBD spreads/natures already loaded | **High** | Medium | Medium |
| 6.6 | Usage trends over time | Med–High | Medium | Medium |
| 6.7 | "What should I add" — fill coverage holes | **High** | Medium | Med–High |
| 6.8 | Smogon ladder source | Medium | Low | Medium |

- **6.5** — 5,192 rows of CBD natures and spreads are loaded and **used by
  nothing**. They'd power "what spread does this threat actually run" and the
  parked "likely column" marker on the Speed tab. The catch is documented: CBD
  reports natures and spreads as *separate* distributions and never pairs them,
  so a pairing rule has to be chosen and stated. Suggested approach: aggregate
  natures by Speed *direction* (+/neutral/−) rather than picking one name, since
  Jolly and Timid are identical for Speed purposes.
- **6.6** — every tournament has an `event_date`, so rising/falling usage is
  computable. Catching a threat on the way up matters more for April than
  knowing today's order. Shares its plumbing with 6.1.
- **6.7** — the tool currently tells you Golisopod-Mega is a hole; the natural
  next question is "so what fixes that?". Needs a candidate pool and a scoring
  rule, and risks feeling prescriptive — worth designing carefully.
- **6.8** — blocked until October. Adds ladder usage as a *second* opinion, which
  is genuinely useful given ladder is where the practice games happen.

### Tier 3 — big, or better later

| # | Item | Useful | QoL | Complexity |
|---|---|---|---|---|
| 6.9 | Damage calculator | **Very high** | Medium | **High** |
| 6.10 | Team A/B comparison | Medium | Medium | Medium |
| 6.11 | Teammate cores / common pairs | Medium | Low | Medium |
| 6.12 | Hosting (Streamlit Cloud) | Low | Medium | Medium |

**6.9 is the single biggest upgrade available.** Everything in Visuals 2 and 4 is
currently *type matchup* — it says Rillaboom's Grassy Glide is 1× STAB into your
Garchomp, but not whether it actually KOs. Real damage turns "type pressure" into
"do I lose". It needs spreads (6.5), items, abilities and field effects first, so
it sits naturally after Tier 2 rather than before it.

**6.11** was deliberately skipped in v1: CBD teammate rows are fetched but not
loaded, because they carry no percentage.

### Explicitly not doing

From `PARKING_LOT.md`: ML of any kind, replay parsing, bring-4 recommendations
(belongs to the VFC xV project).

---

## 7. Suggested order

1. **6.1 meta filtering** — highest value, and it unlocks 6.6 for nearly free.
2. **6.2 sprites + 6.3 polish** — do them together; sprites solve several
   layout problems that aren't worth fixing twice.
3. **6.4 speed control** — small, self-contained, high value per hour.
4. **6.5 spreads** — then reconsider 6.9.

A reasonable next-session scope is 6.1 alone, or 6.2 + 6.3 together. 6.1 is a
refactor with a clear shape; the visual work is broader but lower-risk.

---

## 8. Conventions to keep

- **All writes go through `scripts/`.** The app is strictly read-only.
- **Log every judgment call in `DECISIONS.md`** with a reason. That file is the
  project's memory across sessions and it has repeatedly paid for itself.
- **Prove loaders are idempotent** by running twice and comparing counts.
- **Verify a data format before writing code against it** — but only formats not
  already verified.
- **Run `uv run pytest -q` after code changes and propose a commit**, don't
  commit unprompted.
- For UI work, actually open the app and look. Three real bugs this session
  (a column scrolled off-screen, unreadable text on light fills, and the
  meaningless "3×") were invisible to the test suite.
