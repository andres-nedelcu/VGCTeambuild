# Parking Lot

Ideas go here, not into code. Review only after v1 is done.

- Damage calculator integration (real damage-based threat score)
- Tailwind and Trick Room toggles on the speed ladder *(first v1.1 candidate)*
- Intimidate, weather, and terrain adjustments
- Win-rate views from Limitless records
- Teammate cores and common pairs
- Meta trend lines across snapshots
- Head-to-head comparison of two of your own teams
- Replay parsing
- Bring-4 recommendations (**belongs to VFC xV**)
- ML of any kind
- Hosting on Streamlit Community Cloud
- Sprites and visual polish
- In-app PokePaste URL preview (parse in memory, no warehouse write)
- Ability damage modifiers in the defensive grid: Dry Skin (Fire x1.25), Fluffy (Fire x2 / contact x0.5), Filter / Solid Rock, Bulletproof, Soundproof, Tera Shell (full-HP resist), Mimicry (terrain typing)
- Aura Guard (Champions, Mega Lucario Z): contact damage x0.5

## Prioritised roadmap

See `docs/HANDOFF.md` §6 for these ranked by usefulness, quality of life and
complexity, with technical notes. Added 2026-09-18:

- Meta-side filtering: top cut only, event size, recency, specific events
  (needs `mart_meta_top` to aggregate `fact_tournament_set` instead of reading
  the precomputed `fact_usage` rollup)
- Usage weighted by record — `wins/losses/ties` are loaded but unused
- Use the CBD natures and spreads already loaded (5,192 rows, currently unused)
- "What should I add" — suggest Pokémon that fill a coverage hole

## Follow-ups from meta filtering (added 2026-09-18)

- Percentile cut ("top 25% of finishers") as an alternative to the fixed top-N,
  so a 42-player and a 148-player event are cut comparably. Same WHERE clause
  with a computed threshold; the open question is which one to make the default.
- Filtered Mega stone share from `fact_tournament_set.item_id`, so a top-cut meta
  is split by the stones *cut teams* ran rather than by ladder shares.
- Wire `check_meta_stability.py` to accept a `MetaFilter`, so a cut view can report
  its own confidence instead of relying on the flat 400-team warning.

### Known bug: two species, one Mega forme (found 2026-09-18)

`mart_meta_top` can hold two rows for the same `forme_id`, because two species map to
one Mega forme via their stone: `floette` (share 1.000) and `floetteeternal` (0.986)
both become `floettemega`. It is the only such pair in M-C today.

Effect: Floette-Mega's usage is split across two rows, 11.9% and 1.9%, so the tool
shows 11.9% where the true figure is about 13.8% — roughly one rank low. The second
row sits near rank 41, so it stays outside the Offensive-coverage and Threat-list
sliders (max 40) and no duplicate is visible there; the Speed tab's slider reaches
60, so it can show Floette-Mega twice.

Predates the meta-filter work — the old `fact_usage`-based view had the same shape.

The fix is to sum usage per `(regulation, forme_id)`, but `species_id`,
`forme_share`, `species_usage_pct` and `species_rank` are species-level columns that
then need a rule (carry the largest contributor? null them?). Worth settling
deliberately rather than inside another change.
