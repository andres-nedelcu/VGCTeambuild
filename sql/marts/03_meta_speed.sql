-- Champions stat math, mirrored from vgc.stats.calc_stat. Both are pinned to the same
-- reference speed-tier table by tests/test_speed_tiers.py, so they cannot drift apart.
CREATE OR REPLACE MACRO champ_stat(base, sp, nature_pct) AS ((base + sp + 20) * nature_pct) // 100;
CREATE OR REPLACE MACRO champ_scarf(spe) AS (spe * 3) // 2;

-- Speed benchmarks per forme. Every column is derived from base Speed alone, so the
-- numbers never depend on build data; scarf_share only flags where to look.
-- Parameters are meta_usage's; see sql/marts/00_meta_usage.sql for what each one means.
-- scarf_share stays species-level and unfiltered for the same reason as stone share:
-- it comes from build data, which carries no placement or date dimension.
-- Nature -> Speed direction. Mirrors vgc.stats.NATURES; tests/test_likely_speed.py
-- checks this mapping against vgc.stats.nature_mod for all 25 natures so the two
-- copies cannot drift, the same guarantee champ_stat already has.
CREATE OR REPLACE MACRO spe_nature_dir(nature) AS (
    CASE WHEN nature IN ('jolly', 'timid', 'hasty', 'naive') THEN 'plus'
         WHEN nature IN ('brave', 'quiet', 'relaxed', 'sassy') THEN 'minus'
         ELSE 'neutral' END);
CREATE OR REPLACE MACRO spe_nature_pct(dir) AS (
    CASE dir WHEN 'plus' THEN 110 WHEN 'minus' THEN 90 ELSE 100 END);

CREATE OR REPLACE MACRO meta_speed(reg, cut, since, min_players, weight_mode) AS TABLE
WITH scarf AS (
    SELECT regulation, pokemon_id, max(pct) AS scarf_share
    FROM mart_build_detail
    WHERE detail_type = 'item' AND detail_value = 'choicescarf'
    GROUP BY 1, 2
),
-- What Speed investment a threat actually runs. The exact Speed slot is used rather
-- than a 0/partial/32 bucket: bucketing scores 79.6% average concentration against
-- the exact value's 79.0%, so it buys almost nothing and costs an arbitrary boundary.
-- Whole spreads are useless here by comparison -- the modal full spread averages only
-- 29% -- because the other five slots fragment while the Speed slot does not.
spe_sp AS (
    SELECT regulation, pokemon_id, spe_sp, share FROM (
        SELECT regulation, pokemon_id, spe_sp, w / sum(w) OVER (PARTITION BY regulation, pokemon_id) AS share,
               row_number() OVER (PARTITION BY regulation, pokemon_id ORDER BY w DESC, spe_sp) AS rn
        FROM (
            SELECT regulation, pokemon_id, spe_sp, sum(pct) AS w
            FROM (
                SELECT regulation, pokemon_id, pct,
                       try_cast(str_split(detail_value, '/')[6] AS INT) AS spe_sp
                FROM mart_build_detail WHERE detail_type = 'spread'
            )
            WHERE spe_sp IS NOT NULL
            GROUP BY 1, 2, 3
        )
    ) WHERE rn = 1
),
nature_dir AS (
    SELECT regulation, pokemon_id, dir, share FROM (
        SELECT regulation, pokemon_id, dir, w / sum(w) OVER (PARTITION BY regulation, pokemon_id) AS share,
               row_number() OVER (PARTITION BY regulation, pokemon_id ORDER BY w DESC, dir) AS rn
        FROM (
            SELECT regulation, pokemon_id, dir, sum(pct) AS w
            FROM (
                SELECT regulation, pokemon_id, pct, spe_nature_dir(detail_value) AS dir
                FROM mart_build_detail WHERE detail_type = 'nature'
            )
            GROUP BY 1, 2, 3
        )
    ) WHERE rn = 1
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
       -- Annotation only: likely_spe never feeds a verdict. The benchmark columns
       -- above are exact, this is an observation about what people bring, and the
       -- two shares are INDEPENDENT marginals -- CBD publishes nature and spread
       -- distributions separately and never pairs them, so their product is not a
       -- joint probability and is deliberately not computed here.
       sp.spe_sp AS likely_spe_sp,
       sp.share AS likely_spe_sp_share,
       nd.dir AS likely_nature_dir,
       nd.share AS likely_nature_share,
       CASE WHEN sp.spe_sp IS NULL OR nd.dir IS NULL THEN NULL
            ELSE champ_stat(t.spe, sp.spe_sp, spe_nature_pct(nd.dir)) END AS likely_spe,
       least(coalesce(sp.share, 0), coalesce(nd.share, 0)) AS likely_confidence,
       t.forme_usage_pct, t.species_rank
FROM meta_top(reg, cut, since, min_players, weight_mode) t
LEFT JOIN scarf s
  ON s.regulation = t.regulation AND s.pokemon_id = t.species_id
LEFT JOIN spe_sp sp
  ON sp.regulation = t.regulation AND sp.pokemon_id = t.species_id
LEFT JOIN nature_dir nd
  ON nd.regulation = t.regulation AND nd.pokemon_id = t.species_id
ORDER BY t.spe DESC, t.forme_usage_pct DESC;

-- The unfiltered default, so every existing reader keeps working unchanged.
CREATE OR REPLACE VIEW mart_meta_speed AS
SELECT * FROM meta_speed(NULL, NULL, NULL, NULL, 'teams');
