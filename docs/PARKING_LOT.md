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
