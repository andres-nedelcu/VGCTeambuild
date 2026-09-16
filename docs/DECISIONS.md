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
| 2026-09-16 | Limitless teamlists carry no stat points; spreads come from CBD only | Teamlist fields: id, name, item, ability, attacks, nature, tera (always null) |
| TBD (Phase 2) | Usage weight for CBD in threat/coverage scores (rank-based vs Limitless %) | CBD has no usage % |
| TBD (Phase 0) | Mega and forme ID rule | Sources disagree on representation |
| TBD (Phase 0) | Champions stat formula | Must be verified against in-game values |
| TBD (Phase 3) | Smogon rating cutoff | Pick one and never mix |
| 2026-09-16 | Static data exported from Showdown `champions` mod via Dex, pinned to c23d2e9 | Mod overrides move data; npm release (Jul 28) predates Mega Garchomp Z |
| 2026-09-16 | Node used only for the static export step | Lets Showdown resolve mod inheritance instead of parsing TypeScript |
| 2026-09-16 | Showdown format IDs: gen9championsvgc2026regmc / regmb | Confirmed from Dex.formats on the pinned commit |
