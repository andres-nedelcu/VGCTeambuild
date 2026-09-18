# Wave 2 operating rules — read this before your task brief

Written 2026-09-18 (Friday evening) during a single planning session. If you are a
fresh session picking up one of the briefs in this folder, read, in order:

1. `docs/HANDOFF.md` — what the project is and where it got to. Sections 4 and 8
   are the ones that will save you time.
2. `docs/DECISIONS.md` — every judgment call and its reason. Check it before
   re-deciding anything; several of the decisions you are about to face are
   already settled there.
3. Your own brief in this folder.

Do not read `vendor/` — it is a pinned Showdown checkout, it is large, and nothing
in it needs changing.

---

## The deadline that shapes everything

Andres flies out Saturday and returns Monday night, with a local tournament on
Tuesday. **Two 3-hour flights**, and he intends to study matchups on the laptop
during them.

**Offline operation is a hard requirement, not a nice-to-have.** Anything your task
adds must work with the wifi off:

- No runtime calls to the network in `app/` — ever. The app already only reads a
  local DuckDB file; keep it that way.
- Anything fetched from the internet is fetched by a script in `scripts/`, cached
  on disk, and read from disk by the app.
- If you add an asset the app needs, make sure it is on disk and **committed**,
  not merely downloadable.

If your change would make the app degrade without a network, stop and say so
rather than shipping it.

---

## The rules that stop us breaking a working tool

**Rollback exists.** `git checkout v1-good` returns to the end of v1: four working
visuals, 155 passing tests. Use it rather than fighting a broken tree.

**One warehouse writer at a time.** DuckDB permits a single writer.
`scripts/refresh.py`, `build_marts.py`, `load_*.py` and `init_warehouse.py` write;
everything else opens read-only. The three wave-2 tasks are designed to need **no
writes at all** — if yours turns out to need one, say so before running it, because
another session or Andres may be using the warehouse.

**Ports.** Port 8502 is Andres's own dashboard — do not stop it, do not take it.
`.claude/launch.json` has a `dashboard-alt` config on 8503 for agent use. If 8503
is also busy, add another config rather than reusing one.

**Streamlit caches imported modules.** After editing anything under `src/vgc/`,
restart the server. A reload is not enough. An `AttributeError` that flatly
contradicts the code on disk is always this.

**Branch per task**, named in your brief, branched from `main`. Never work on
`main` directly — Andres needs to be able to travel on a green `main` at any moment.

---

## Definition of done

All four, every time:

1. `uv run pytest -q` passes. It takes about 3 seconds; run it often.
2. You added tests for what you built.
3. **You opened the app and looked at it.** Three real bugs in an earlier session —
   a column scrolled off-screen, unreadable text on light fills, and a meaningless
   "3×" — were all invisible to the test suite. Take a screenshot.
4. You logged every judgment call in `docs/DECISIONS.md`, with the reason, in the
   existing table format.

Then **propose a commit; do not commit unprompted.** That is a standing project
convention (`HANDOFF.md` §8), and Andres is reviewing as we go.

New ideas you have along the way go in `docs/PARKING_LOT.md`, not into code.

---

## Scope discipline

Each brief has a **Non-goals** section. Respect it. Scope creep is the named main
risk to this project (`PROJECT_OUTLINE.md` §2), and tonight there is a hard deadline
on top of that. A small finished thing beats a large half-thing — if you run short,
ship less rather than ship broken.
