# VGC Teambuilding Dashboard — 2.0 Outline

**Stack:** Python · DuckDB · Streamlit · Plotly (unchanged)
**Format:** Pokémon Champions VGC Doubles (current: Regulation M-C)
**Status:** scoping. Nothing in here is built yet.
**Last updated:** 1 November 2026

> **Read this first if you are a new session picking up 2.0 work.**
> `PROJECT_OUTLINE.md` describes v1 and is still accurate about the data layer.
> This document describes what 2.0 changes and, just as importantly, **what is
> still undecided**. Items are marked **SETTLED**, **OPEN**, or **PROTOTYPE
> FIRST**. Do not implement an OPEN item without talking to Andres — and do not
> re-litigate a SETTLED one without a reason.

---

## 1. Why there is a 2.0

v1 answers its question well and the data layer underneath it is sound. The
reasons to restructure are specific:

1. **The build loop is too slow to use during a game.** Streamlit rebuilds all
   seven tabs on every rerun and there is essentially no caching, so nudging one
   SP slider recomputes every analysis in the app. Measured: **7.72 seconds per
   render**. The tool's most valuable interaction is its slowest one.
2. **The tab structure has drifted from the questions being asked.** Seven peer
   tabs, one of which ("What to add") runs seven distinct analyses, and one of
   which (Threat list) is superseded by its own neighbour.
3. **The damage calculator is not yet better than a general-purpose calculator.**
   The formula core is excellent and verified; the *inputs* are narrow.
4. **Teams cannot be managed from the app**, because they live in a warehouse
   that is deliberately read-only.

### The through-line

> v1 asked "how does my team line up against the meta?" and answered it with
> tables. 2.0 keeps the question, makes the answer fast enough to use while
> playing, and makes the calculator the reason you reach for this tool instead of
> a generic one.

---

## 2. Principles for 2.0

These govern the work. If a change conflicts with one of these, raise it rather
than working around it.

1. **A wrong calculator is worse than an incomplete one.** Andres's words and the
   governing rule of all damage work. Every new damage mechanic is verified
   against the pinned Showdown simulator before it ships. A mechanic that is not
   modelled must be **visibly absent**, never silently wrong.
2. **Don't rewrite the damage formula core.** `vgc/damage.py` is cited to source,
   verified against a generated reference fixture, and is the most valuable file
   in the repo. 2.0 adds *inputs* to it; it does not restructure the chain.
3. **Keep the two-figure honesty.** Every uncertain number reports both the
   as-set figure and the worst case, with the caller naming which side is
   unknown. This is a design achievement of v1 and it survives intact.
4. **The tab boundary is the cache boundary.** The three surfaces are split on
   team-dependent vs team-independent computation precisely so the expensive
   meta work can be cached across team edits. Do not move a team-dependent
   analysis into the meta surface, or vice versa, without understanding that this
   is what you are breaking.
5. **One writer for derived data.** Facts and marts are written by `refresh.py`
   and nothing else. **Teams are not derived data** — see §4.
6. **Log every judgement call in `DECISIONS.md`.** This has repeatedly paid for
   itself and is how a new session reconstructs intent.
7. **Expect rework.** This outline will be wrong in places. Some decisions below
   are explicitly deferred until something is prototyped, and prototyping will
   invalidate earlier choices. That is the plan, not a failure of it.

---

## 3. The three surfaces — **SETTLED** (shape), **OPEN** (contents)

v1's seven tabs collapse to three, split on **what the computation depends on**:

| Surface | Depends on | Recomputes when |
|---|---|---|
| **1. Team** | the loaded team's spread, moves, items, Mega | you edit the team |
| **2. Meta** | regulation + `MetaFilter` only | you change a meta filter |
| **3. Calc** | two explicit builds | you change either build |

### Surface 1 — Team

The build loop: change a thing, see the effect, without leaving the surface.

- Team management: add, remove, switch (see §4)
- Spread editing (natures + SP) — carries over from the v1 Spreads tab, which
  Andres likes as-is
- **New:** move and item editing, so the tool stops being rigid about what a
  paste said
- Mega selection
- Paste export (carries over)
- **How the team fares:** defence and coverage merged (§5.2), what threatens it,
  where it sits on the speed landscape

Everything on this surface depends on the team, so everything here is expected to
recompute on edit. That is why it is one surface: the feedback loop must not be
split across a tab boundary.

### Surface 2 — Meta

What the format is doing, independent of what you are running.

- Usage, trends over time, risers and fallers
- The speed landscape (§5.3)
- Cores, partners, combos, item-cores — **relocated here** from the dead "What to
  add" tab, where they were buried
- Meta snapshot generation (§6)

Cacheable in its entirety against `(regulation, MetaFilter)`. None of it should
recompute when a spread changes.

### Surface 3 — Calc

The damage calculator, and the main engineering effort of 2.0. See §7.

### The drill-through — **SETTLED**

The v1 Dex view **stops being a tab**. The Pokémon profile — base stats, usage,
common items/abilities/moves/natures/spreads — becomes a **detail panel reachable
from anywhere**: a bar in the speed view, a row in a threat list, a cell in a
damage grid. One implementation, every surface gets deeper, one less destination
to navigate to.

Note this is an **extraction, not a deletion**: the calculator half of
`dex_view.py` (the custom-attacker path, `versus(unknown=None)`) is the most
flexible calculator surface in v1 and moves to Surface 3 rather than being lost.

---

## 4. Teams move out of the warehouse — **SETTLED** (principle), **OPEN** (mechanism)

**The finding:** `my_team` is the only hand-authored table in a warehouse of
derived data. Everything else is rebuilt from `data/raw/` by `refresh.py`. Teams
are the one thing that would be *lost* if the warehouse were deleted. They are
in there because it was convenient on day one.

**Why it matters:** that single misplacement causes the rigidity. The app is
read-only to protect the marts; because it is read-only, spread edits live in
`st.session_state` and die on browser refresh; because they die, `to_paste()`
exists so a spread can be copied into a note before it is lost.

**Consequence:** moving teams out unwinds the whole chain. In-app add/remove and
persistent move/item edits are **the same fix**, not two features.

**Also settled:** VFC xV is shelved. Andres is focusing on this project. The
single-writer rule was partly justified by a second process reading the same
warehouse file; that justification is now weaker, though the rule still stands
for derived data on its own merits.

**OPEN:** where teams actually live (a JSON or SQLite store beside the warehouse,
format, migration of the eight existing pastes). Needs a decision before Surface
1 work starts, because everything on that surface depends on it.

---

## 5. Per-area decisions

### 5.1 Spreads editing — **SETTLED**

Keep the v1 editor, which works. Add move and item editing.

**Dependency:** item editing is coupled to item coverage in the engine (§7.2).
The moment the UI offers an item dropdown it implies the engine understands the
choice. Either ship them together, or mark unmodelled items visibly in the picker
— per Principle 1, silence is not acceptable.

### 5.2 Defence + coverage merge — **SETTLED**

One surface, one direction toggle. The Damage tab already solves this exact
problem with its "What hits me / What I hit" radio; reuse the pattern rather than
inventing a second one.

### 5.3 Speed landscape — **PROTOTYPE FIRST**

The v1 table is the weakest surface in the app. The diagnosis: **speed is a
one-dimensional continuum rendered as a table**, which throws away the one thing
that matters — distance along the line.

The direction Andres wants to see before committing: anchor the view to actual
speed values on a line rather than to Pokémon in rows.

**What the data supports, and why a plain histogram undersells it:**
`mart_meta_speed` does not hold one value per threat. It holds a *range* —
`spe_uninvested_neg`, `spe_uninvested`, `spe_max_neutral`, `spe_max_plus`, Scarf
variants — plus `likely_spe` and a `likely_confidence`. So each threat is a band
with a marker in it.

Drawn as bands on a number line with your team's speeds as lines across it, the
questions answer themselves:

- band entirely left of your line → you outspeed it
- your line passes through the band → depends on their build; the marker says
  which way to bet
- band entirely right → you lose

Tailwind and Trick Room come nearly free: `speed.Field` already models them, and
on a number line Tailwind is a 2× scale transform.

**Status:** build it, look at it, then decide. Andres has explicitly reserved
further comment until he can see it working.

### 5.4 Cut from v1 — **SETTLED**

- **Threat list** — redundant. It ranks by type pressure only and the app's own
  caption admits the Damage tab answers what it leaves open.
- **"What to add" as a tab** — `suggest.py` deliberately refuses to score, which
  is intellectually honest and is also why the tab feels useless: it declines to
  conclude. Its cores/partners/combos/item-cores content moves to Surface 2.
  Whether a recommender returns in any form is **OPEN**.

### 5.5 Visual language — **DEFERRED**

Andres is not happy with the current look and wants to move away from everything
being tabular. This is explicitly scoped as a **later update**, with only minor
restructuring of how data is presented in 2.0.

One supporting note for when it is picked up: this is not only taste. `DECISIONS`
records that Streamlit's dataframe Styler silently honours only `color`,
`background-color` and `font-weight` and drops everything else — that cost an
hour and killed two separate design ideas. The tabular approach fights the
framework; Plotly does not.

### 5.6 Sidebar — **MOSTLY CARRIED OVER**

Team management changes (§4). The meta filters stay as they are for now, with
Andres explicitly flagging the rest of the sidebar for **reopened discussion** as
the build proceeds.

---

## 6. Meta snapshot — **OPEN**, develop with Andres

The two existing snapshots are structurally identical — same sections, same
lenses — which is the signature of something ready to be generated. The October
one took eight throwaway scratchpad scripts and hand-rebuilt SQL, every number of
it derived from marts that already existed.

The direction: the snapshot is **Surface 2 serialised, with commentary**, and it
and Surface 2 should read through the same query layer rather than being rebuilt
by hand each time.

A second idea worth weighing when this is picked up: the September snapshot made
predictions (both-weather teams "worth watching" at 1.7%, Indeedee-F
under-performing) and the October one could check them only because the old file
happened to be read. **A snapshot that scores its own previous predictions** would
be genuinely novel, and the dated history to do it already exists.

---

## 7. The damage calculator

The main engineering effort, and the area Andres is most nervous about. Principle
1 governs everything here.

### 7.1 What is already right

The formula chain, the 4096-step fixed-point `modify()`, the roll landing before
STAB and type effectiveness, weather, terrain including per-move clauses, Weather
Ball's retyping, stat stages, and the two-figure reporting. All verified against
the simulator. **None of this is being rewritten.**

### 7.2 Items — scope is much smaller than it first appears — **SETTLED**

An earlier audit framed this as "26 of 583 items modelled", which was misleading.
Andres's correction is right and the data confirms it: **173 distinct items are
actually brought to events**, and most of what is missing does not belong in a
damage calculation at all.

**The governing distinction: does the item change the damage roll, or what
happens after it?** A damage calculator answers "how much damage will this do",
not "what is the HP after end-of-turn effects".

**Explicitly out of scope** (post-damage — Andres's call, and correct):
Sitrus Berry (9.81%), Leftovers (5.89%), Rocky Helmet (2.37%), Eject Button
(0.61%). These resolve after the damage is dealt and do not change it.

**Already modelled:** Life Orb, Choice Band/Specs, Assault Vest, Eviolite, Muscle
Band, Wise Glasses, Expert Belt, and the 18 type-boosting items (Miracle Seed at
5.76% is the most-used of them).

**No damage effect:** all 17 Mega stones in common use (they change the forme,
which is handled elsewhere), Choice Scarf (speed only, handled in `speed.py`).

**The actual gap — two mechanics and one verdict-layer item:**

| Gap | Items in use | Usage | What it does |
|---|---|---|---|
| **Resist berries** | Chople, Colbur, Occa, Passho | 4.81% combined | Halves a super-effective hit **as it is calculated** — a true roll modifier |
| **Terrain seeds** | Grassy, Psychic, Electric | 5.84% combined | +1 Def or +1 SpD in matching terrain — a stat boost, so it changes damage taken |
| **Focus Sash** | Focus Sash | **10.19% — the most-held item in the format** | Does not change the roll; changes whether the roll **KOs**. Belongs in the verdict layer, not the damage layer |

That is a small, countable, tractable scope — two mechanics plus a verdict-layer
special case, not a 557-item backlog. Implement the berry and seed *families*
rather than only the four and three in current use; the mechanic is the same and
the meta will move.

### 7.3 Other missing inputs — **OPEN** (which, and in what order)

- **Screens** — Reflect, Light Screen, **Aurora Veil**. Entirely unmodelled.
  Light Clay at 1.47% usage proves they are being run. The `def_stage` slider is
  offered as an approximation and is not the same thing.
- **Weather: snow and sand.** Only rain and sun exist today. Snow matters
  immediately — Mega Froslass has Snow Warning, so the tool cannot currently
  model the weather one of Andres's own Megas sets, nor snow's Ice-type Defense
  boost, nor the Aurora Veil that depends on it.
- **Abilities that scale damage** — Adaptability, Huge Power, Thick Fat,
  Multiscale, Filter, Tinted Lens, Guts, Technician. Note Adaptability needs
  `stab` to become a multiplier rather than a bool.
- **Multi-hit moves** (Rock Blast, Icicle Spear, Dragon Darts), **fixed-damage
  moves** (Seismic Toss, Night Shade), **critical hits**, **burn**, **Helping
  Hand**.

The generic ±6 stat-stage slider remains a legitimate stand-in for Intimidate,
Swords Dance and Stamina, and should not be removed when abilities arrive.

### 7.4 The inverse solve — **OPEN**, and the highest-value single feature

Today the engine only runs forwards: spread in, damage out. It never solves
backwards.

The question a competitive player actually asks is *"what is the minimum HP and
Def investment that survives Rillaboom's Grassy Glide?"* — which is exactly what
Andres described wanting from spread optimisation. Every component needed already
exists; nothing calls them in that direction.

This is the clearest answer to "why use this instead of a normal calculator".

---

## 8. Carried over untouched

Do not spend 2.0 effort re-engineering these:

- `vgc/damage.py` formula core and its reference fixture
- The ingest pipeline, `refresh.py`, and its idempotency
- The marts and the `MetaFilter` macro design
- The sprite cache and offline operation
- `DECISIONS.md` discipline

---

## 9. Known rot to clear while passing through

Small, independent, safe to fix opportunistically:

- `src/vgc/scoring.py` — dead, one line, `TODO(Phase 2)`, imported nowhere
- `scripts/spike_phase0.py`, `scripts/spike_limitless.py` — Phase 0 exploration,
  referenced only by the old outline
- `metafilter.py` module docstring quotes stale October 7 figures (159 events,
  "Salamence 41.3% → 12.8%"). This is the exact failure `DECISIONS` logged on
  2026-10-07: the app caption was fixed by deriving it, and the docstring quietly
  reintroduced the same stale claim
- `THIN_SAMPLE = 400`, but the comment above it cites ~3,000 teams as the bar the
  stability work established. The warning fires at 400
- Variable shadowing: the Damage tab reassigns `slots`, the "What to add" tab
  reassigns `mode` — both outer sidebar variables, harmless only because nothing
  reads them afterwards
- Six test files hardcode the same paste ID (`b58a4fb249fb3cbf`). ~40
  `pytest.skip` sites mean a fresh clone runs a largely skipped — and therefore
  green — suite
- No linter, formatter, type checker or CI

---

## 10. Sequencing and what gates what

Rough dependency order. Not a schedule.

1. **Team storage decision (§4)** gates all of Surface 1. Nothing on that surface
   can be built until teams have somewhere to live.
2. **Cache boundaries (§3)** gate how the whole app feels. Worth establishing
   with the three-surface split rather than retrofitting.
3. **Item editing (§5.1)** gates on, or ships alongside, item coverage (§7.2).
4. **Speed landscape (§5.3)** is independent — prototype it any time.
5. **The damage engine (§7)** is independent of all layout work and is the
   largest chunk. It can proceed in parallel with the restructuring.
6. **Meta snapshot (§6)** wants Surface 2's query layer to exist first.

## 11. Open questions, collected

Every **OPEN** item above, in one place, so a new session can see what still
needs Andres rather than hunting for it:

- Where and how teams are stored (§4) — blocking Surface 1
- Whether a recommender returns in any form (§5.4)
- The speed landscape's final design, after prototyping (§5.3)
- The meta snapshot's shape: surface, export, or scheduled artifact (§6)
- Which damage mechanics land, and in what order (§7.3)
- Whether the inverse solve is a 2.0 feature or the thing after it (§7.4)
- Sidebar beyond team management — flagged by Andres for reopened discussion
  (§5.6)
- Visual language, deliberately deferred (§5.5)
