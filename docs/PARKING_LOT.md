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
- Sprites in the coverage heatmap and defensive grid chart x-axis (6.2 landed sprites in the two dataframe views only; the Plotly charts are 6.3's job per 6.2's non-goals)
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

### Other Speed-modifying items (added 2026-09-18)

`team_speeds` applies Choice Scarf only. `dim_item` also carries **Iron Ball** and
**Macho Brace** (halve Speed), **Quick Powder** (Ditto only) and the move-last items
Lagging Tail and Full Incense. The halving pair matters more now that the Speed tab
has a Trick Room mode, since that is exactly where they get used. Same one-line
change in `team_speeds`; the open question is whether to model move-last items at all,
as they are an ordering rule rather than a Speed multiplier.
