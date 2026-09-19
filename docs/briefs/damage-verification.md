# Brief — independent damage-formula verification corpus

**You are the verification half of a two-part job.** Someone else is implementing a
damage calculator for this project in parallel. Your job is to derive the ground
truth **independently of that implementation**, so the two can be compared. If we
agree, the confidence is real. If we disagree, one of us is wrong and we find out
immediately instead of shipping a confidently wrong number.

That independence is the entire value of this task. Protect it.

---

## Hard rules

1. **Do not read, run, or look at any damage-calculator implementation in this repo.**
   If `src/vgc/damage.py` (or anything like it) exists by the time you read this,
   ignore it completely. Do not open it. Deriving from the source and then checking
   your answer against someone else's code is not verification.
2. **I have deliberately not written the formula in this brief.** Derive it yourself
   from the vendored source. If you find yourself wanting me to confirm a step, that
   is exactly the confirmation this task exists to avoid.
3. **Write exactly one file**: `tests/fixtures/damage_reference.json`, plus your
   written findings in your reply. Change nothing else. Do not touch `src/`, `app/`,
   `sql/`, or any other test.
4. **Never write to the warehouse.** `connect(read_only=True)` only. Another session
   is working in this repo at the same time.
5. **Do not run the Streamlit app**, and do not start a server.
6. **Cite `file:line` for every mechanical claim.** A number with no citation cannot
   be checked and is worth nothing here.

## Your source of truth

`vendor/pokemon-showdown/` — a pinned checkout at commit `c23d2e9`, which is the exact
version this project's static data was exported from. Use it, not the internet, not
your memory of how Pokémon damage works. Where your recollection and the source
disagree, the source wins and the disagreement is worth reporting.

Two places matter most:

- The generic simulator, for the base damage calculation and the modifier chain.
- `vendor/pokemon-showdown/data/mods/champions/` — Champions overrides some things and
  not others. Establishing **which** is a substantial part of this job. Note in
  particular that `scripts.ts` overrides `statModify`, and whether the damage path
  consumes those modified stats is a question you should answer explicitly.

`vendor/` is large. Do not read it exhaustively — navigate with grep.

## Format of the answer

The format is not a spreadsheet of numbers. It is a derivation plus examples.

### Phase 1 — the chain

Produce, in your reply:

- The base damage expression, with every truncation/floor shown in the order it
  applies. Integer rounding order is the single most common source of off-by-one
  errors in damage calculators, so be exact about where each `trunc` sits.
- The **ordered** list of everything applied after it — spread, weather, critical
  hits, the random factor, STAB, type effectiveness, burn, items, abilities — with
  the multiplier for each and a `file:line` citation.
- An explicit statement of which of these Champions overrides and which it inherits.
- Anything that surprised you, or that a careful implementer would get wrong.

Then **STOP and report.** Do not start Phase 2.

### Phase 2 — worked examples

Only after you are told to continue.

Build `tests/fixtures/damage_reference.json`: a list of cases, each with the full
input (attacker species, stat investment, nature, item, ability; move; defender
species, investment, nature, item, ability; field state; single-target or spread) and
the expected damage as a **min/max roll range in raw HP**, plus the defender's HP so a
percentage can be derived.

Every case must also carry a `steps` field: the arithmetic, in order, with the
intermediate value after each step. The steps are more valuable than the answer —
they are what makes a mismatch diagnosable rather than just a failure.

Real Champions data, please. `connect(read_only=True)` gives you `dim_pokemon`,
`dim_move` and `dim_item`; `vgc.stats.calc_stat` is this project's already-verified
Champions stat formula (HP = base + SP + 75, others = floor((base + SP + 20) x
nature), SP capped 32/stat and 66 total).

Cover at minimum:

- A plain neutral single-target physical hit — the baseline everything else builds on.
- A special attack, to exercise the other stat path.
- **A spread move in doubles**, which is the default case in VGC and has its own modifier.
- **A Fire move into Golisopod-Mega (Bug/Steel, 4x weak) with and without rain.** This
  is the case that motivated the whole feature: the question is whether rain moves it
  across a KO threshold, so both numbers matter.
- A Choice-item boosted hit and a Life Orb hit.
- At least one case where an ability changes the result.
- At least one case you expect an implementer to get wrong. Say why.

Then **STOP and report** with a summary of the cases and anything you could not
resolve from the source.

## How to work

Andres is watching both sessions and tracking credit usage. **Stop at the end of each
phase and wait to be told to continue** — do not run the phases together. Keep your
reports readable: what you found, what it cost, what you are unsure about.

If something in the source is genuinely ambiguous, say so rather than picking. An
"I could not determine this from the source" is a useful result. A confident guess
dressed as a finding is the one outcome that makes this whole exercise pointless.
