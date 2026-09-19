# Brief — the single-Pokémon (dex) view

**Suggested model: Opus or Sonnet 5.** Design-heavy rather than algorithmically hard;
all the data and every calculation it needs already exist.

**Branch:** `feat/dex-view`, from `main`.
**Read first:** `docs/briefs/OPERATING_RULES.md`, then `docs/SUMMARY_2026-09-18.md`
for where the project is, then `DECISIONS.md` — it is long now, but the 2026-09-18/19
entries are the ones that matter and they will stop you re-deciding settled questions.

---

## What it is

Andres's long-term vision: *"for this to just work as a damage calculator with search
bars where you can use all the settings."* Pick any Pokémon in the dex and see
everything known about it, then calculate against it.

One page, one Pokémon. Four parts:

1. **Pick it.** A search over `dim_pokemon` (1,518 rows, so it needs to be a
   searchable selectbox, not a dropdown).
2. **What the meta runs.** Its usage and rank, most common items, abilities, moves,
   natures and spreads — all in `mart_build_detail`, `mart_meta_top` and
   `mart_meta_investment`. Everything here is already computed; this part is almost
   entirely presentation.
3. **Set it up.** Nature, SP, ability, item, and a stat stage. The Spreads tab
   (`app/components/spread_editor.py`) already does exactly this for team members —
   read it before writing a second one, and factor the shared piece out rather than
   copying it.
4. **Calculate.** Damage both directions: your team into it, and it into your team.

---

## What already exists — do not rebuild any of this

- **`vgc.damage`** — the formula, pinned roll-for-roll against Showdown's own
  simulator. **Do not modify it without regenerating the fixture.** The workflow is:
  add a case to `tests/fixtures/damage_cases.json`, run
  `node scripts/showdown_damage.js tests/fixtures/damage_cases.json > tests/fixtures/damage_reference.json`,
  and `tests/test_damage.py` tells you immediately whether you are right. That loop
  takes about two minutes and is the most valuable thing in the repo — use it.
- **`vgc.incoming`** — meta attacking your team, with KO brackets.
- **`vgc.outgoing`** — your team attacking the meta, with the likely/bulkiest split.
- **`vgc.edit`** — spread overrides held in session, never written to the warehouse.
- **`vgc.cores`** — pairs, item-conditioned pairs, and trios.
- `app/components/palette.py` and `sprite_axis.py` — every colour and both sprite
  axes. No hex literal belongs outside `palette.py`.

The gap this brief fills is that all of the above is anchored to *your team*. Nothing
lets you ask about an arbitrary Pokémon.

---

## Design decisions already made — do not relitigate

- **Green means good for Andres**, everywhere, in both themes.
- **No composite scores.** Show the components and sort by them. The reasoning is in
  `DECISIONS.md` under the 6.7 entry and it applies here too.
- **Abilities are not modelled individually.** Damage-affecting abilities go through
  the generic stat stage (-6..+6): Intimidate is -1, Stamina +N, Swords Dance +2.
  Abilities that change *type effectiveness* are already handled in `vgc.typechart`.
  Do not start an ability graph — `DECISIONS.md` explains why at length.
- **Two figures, not one, wherever investment is uncertain.** Attacking investment is
  reliable (modal share ~0.89); defensive investment is not (~0.63-0.67). Follow what
  `vgc.outgoing` does: report the modal build and the bulkiest legal one.
- **The app is read-only.** Session state only; never write to the warehouse.

## Open questions that are yours to decide

- **Does the dex view live in a tab, or replace the Damage tab's direction radio?**
  There are already seven tabs and Andres has said the "What to add" tab is not
  intuitive. Adding an eighth without restructuring may make that worse. He has said
  he has his own notes on reorganising — **ask him before adding a tab.**
- How much of the build panel is worth showing at once. All of it is available; most
  of it may be noise.
- Whether the calculator should accept an arbitrary *attacker* too, or only ever
  compare against the loaded team. The former is the full calculator vision; the
  latter is a smaller, more focused thing.

---

## Acceptance

- Works with the network off. `tests/test_offline.py` blocks sockets and drives the
  app's read path — extend it to cover the new page.
- Any new damage path is pinned against the simulator, not against your own reading
  of the source.
- `uv run pytest -q` green (307 at the time of writing), new tests included.
- You have opened the app and looked at it. Several bugs in this project were
  invisible to a green suite — a collapsed Plotly axis, sprites overlapping tick
  labels, a nature selector silently applying Adamant.
- Judgement calls logged in `DECISIONS.md`; commit proposed, not made.
