# Decisions Log

| Date | Decision | Why |
|---|---|---|
| 2026-09-15 | Python + DuckDB + Streamlit | SQL-first transforms, native on macOS, free hosting option later |
| 2026-09-15 | Power BI ruled out | Power BI Desktop is Windows-only |
| 2026-09-15 | Shared `vgc` data package with VFC xV | Avoids maintaining two pipelines for the same sources |
| 2026-09-15 | Showdown ID as universal join key | CBD already provides `showdownId`, and Showdown data is the static source |
| 2026-09-15 | Ingest dated CBD snapshots only, never "Current" | The "Current" window is undefined |
| 2026-09-15 | Pikalytics and similar sites are reference only | No official API; scraping is fragile |
| 2026-09-15 | Smogon deferred to v1.1 | M-C chaos files not expected until early October 2026 |
| 2026-09-16 | App uses short-lived read-only connections, not a cached one | An open reader in another process blocks `refresh.py` from writing |
| 2026-09-16 | `fact_tournament_set.placing` renamed to `placement` | `PLACING` is a reserved keyword in DuckDB |
| 2026-09-16 | CBD rows tagged by ranked season (M-C = M6–M8), not date | CBD's last M5 snapshot (10_09) is dated after M-C started |
| 2026-09-16 | CBD fetched via JSON API, one dated folder, Doubles only | No date param: request days=N and verify the date; archived seasons are JSON-only |
| 2026-09-16 | CBD usage = rank only (usage_pct, sample_size NULL) | CBD publishes usage rank, not percentages |
| 2026-09-16 | CBD raw data stays local, attribution if anything is shown publicly | CBD API rules: caching OK, no mirror |
| 2026-09-16 | Limitless M-C = in M-C window AND (format M-C, or CUSTOM with 'M-C'/'Reg M-C' in the name) | Limitless has no M-C format yet; organizers use CUSTOM. Ambiguous names are skipped |
| 2026-09-16 | Limitless species key = teamlist `id` slug via to_id + config/id_aliases.yaml | `name` is a display name (e.g. 'Indeedee ♀') |
| 2026-09-16 | Limitless client honours the RateLimit header (50 requests / 5 min) | No API key for personal use |
| 2026-09-16 | Limitless teamlists carry no stat points; spreads come from CBD only | Teamlist fields: id, name, item, ability, attacks, nature, tera (ignored: no Tera in Champions, though 17/888 entries in the first event carry a value) |
| 2026-09-16 | Phase 0 exit criteria met | CBD top 50: 50/50; Limitless 148 teams: 0 unresolved; paste b58a4fb249fb3cbf: PASS |
| 2026-09-16 | Megas: pokemon_id = species as listed; Mega forme derived from held stone via dim_item.mega_forme_id (multi-forme stones resolved from holder forme); mega share = stone share. Reverses outline 7.1 proposal | CBD, Limitless and PokePaste all list base species + stone (e.g. Raichu 79.7% Y / 17.4% X in CBD) |
| 2026-09-16 | Static data exported from Showdown `champions` mod via Dex, pinned to c23d2e9 | Mod overrides move data; npm release (Jul 28) predates Mega Garchomp Z |
| 2026-09-16 | Node used only for the static export step | Lets Showdown resolve mod inheritance instead of parsing TypeScript |
| 2026-09-16 | Showdown format IDs: gen9championsvgc2026regmc / regmb | Confirmed from Dex.formats on the pinned commit |
| 2026-09-16 | Defensive grid Mega toggle: single choice of "No Mega" or one stone holder; everyone else stays base. A toggled Mega uses the Mega forme's types and ability; base forms use the paste's ability. Stretch: per-option comparison table (weak / resist-immune counts, flagged types) | Only one Mega per battle; Mega typing/ability can flip matchups (Golisopod-Mega Bug/Steel, Garchomp-Mega-Z Levitate) |
| 2026-09-16 | App lists pastes already in `my_team`; new pastes go through `load_paste.py` (app shows the command). In-memory URL preview parked | App stays read-only; every displayed team has passed the same ID/alias resolution checks |
| 2026-09-16 | Phase 1 exit criteria met | Real paste grid renders in ~0.1s; Golisopod-Mega / Gardevoir-Mega toggles correct; Garchomp-Mega-Z shows Ground 0 (off: 1x); 46 tests passing |
| 2026-09-16 | Meta marts split Mega species into forme variants by stone share; base forme gets 1 − Σ stone shares; variants under mega_variant_min_share (0.10) dropped; moves/items/spreads stay species-level | Megas change typing, ability and Speed; dominant-forme-only hides large minorities |
| 2026-09-16 | Usage weight comes from Limitless % only. CBD supplies builds (moves, items, abilities, natures, spreads) and has no species rank in its files; CBD rows in fact_usage are not loaded | CBD per-Pokémon files carry build data, not a usage ranking |
| 2026-09-16 | CBD loads only the newest date in the newest landing (by manifest landed_at), replacing prior CBD rows for that regulation. Teammates skipped in v1 | Each file returns a rolling 3-day window, so landings overlap; history isn't needed for v1 |
| 2026-09-16 | Champions stat formula confirmed with 4 in-game Speed values: HP = base+SP+75, other = floor((base+SP+20) × nature); SP max 32/stat, 66 total. Single function vgc.stats.calc_stat | Matches Showdown server mod, client, and in-game values |
| 2026-09-16 | Investment unit 'ev' is read as SP when within SP limits; real EVs raise an error (no EV→SP conversion) | EV/8 is lossy and 510 EVs don't map onto 66 SP; a silent conversion would be quietly wrong |
| TBD (Phase 3) | Smogon rating cutoff | Pick one and never mix |
