-- Champions stat math, mirrored from vgc.stats.calc_stat. Both are pinned to the same
-- reference speed-tier table by tests/test_speed_tiers.py, so they cannot drift apart.
CREATE OR REPLACE MACRO champ_stat(base, sp, nature_pct) AS ((base + sp + 20) * nature_pct) // 100;
CREATE OR REPLACE MACRO champ_scarf(spe) AS (spe * 3) // 2;

-- Speed benchmarks per forme. Every column is derived from base Speed alone, so the
-- numbers never depend on build data; scarf_share only flags where to look.
-- Parameters are meta_usage's; see sql/marts/00_meta_usage.sql for what each one means.
-- scarf_share stays species-level and unfiltered for the same reason as stone share:
-- it comes from build data, which carries no placement or date dimension.
CREATE OR REPLACE MACRO meta_speed(reg, cut, since, min_players, weight_mode) AS TABLE
WITH scarf AS (
    SELECT regulation, pokemon_id, max(pct) AS scarf_share
    FROM mart_build_detail
    WHERE detail_type = 'item' AND detail_value = 'choicescarf'
    GROUP BY 1, 2
)
SELECT t.regulation, t.snapshot_date, t.species_id, t.forme_id, t.display_name,
       t.spe AS base_spe,
       champ_stat(t.spe, 32, 110) AS spe_max_plus,
       champ_stat(t.spe, 32, 100) AS spe_max_neutral,
       champ_stat(t.spe, 0, 100)  AS spe_uninvested,
       champ_stat(t.spe, 0, 90)   AS spe_uninvested_neg,
       champ_scarf(champ_stat(t.spe, 32, 110)) AS spe_max_plus_scarf,
       champ_scarf(champ_stat(t.spe, 32, 100)) AS spe_max_neutral_scarf,
       coalesce(s.scarf_share, 0) AS scarf_share,
       coalesce(s.scarf_share, 0) >= {{scarf_threshold}} AS scarf_flag,
       t.forme_usage_pct, t.species_rank
FROM meta_top(reg, cut, since, min_players, weight_mode) t
LEFT JOIN scarf s
  ON s.regulation = t.regulation AND s.pokemon_id = t.species_id
ORDER BY t.spe DESC, t.forme_usage_pct DESC;

-- The unfiltered default, so every existing reader keeps working unchanged.
CREATE OR REPLACE VIEW mart_meta_speed AS
SELECT * FROM meta_speed(NULL, NULL, NULL, NULL, 'teams');
