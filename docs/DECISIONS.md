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
| TBD (Phase 0) | Mega and forme ID rule | Sources disagree on representation |
| TBD (Phase 0) | Champions stat formula | Must be verified against in-game values |
| TBD (Phase 3) | Smogon rating cutoff | Pick one and never mix |
