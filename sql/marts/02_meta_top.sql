-- Share of a species' teams holding each Mega stone, keyed to the forme that stone makes.
-- Species-level and unfiltered: stone share comes from build data (CBD preferred), which
-- has no placement or date dimension, so a filtered meta is still split by the same
-- shares. Splitting a top-cut meta by ladder stone shares is a known approximation --
-- fact_tournament_set.item_id could give a filtered share later; see docs/DECISIONS.md.
--
-- The base_species_id match rejects a stone sitting on a species it cannot belong to.
-- Teamlists are third-party data and carry occasional junk that still passes item
-- validation because the item itself is real: a Meganium listed with a Blastoisinite,
-- a Floette-Eternal with a Delphoxite. Both are single entries, so today the
-- mega_variant_min_share filter already discards them -- but on a low-sample species
-- one typo can clear 10%, and a phantom forme would then enter the meta outright.
CREATE OR REPLACE VIEW mart_meta_stone_share AS
SELECT d.regulation, d.pokemon_id, i.mega_forme_id AS forme_id, sum(d.pct) AS share
FROM mart_build_detail d
JOIN dim_item i ON i.item_id = d.detail_value
JOIN dim_pokemon holder ON holder.pokemon_id = d.pokemon_id
JOIN dim_pokemon forme ON forme.pokemon_id = i.mega_forme_id
WHERE d.detail_type = 'item' AND i.is_mega_stone AND i.mega_forme_id IS NOT NULL
  AND holder.base_species_id = forme.base_species_id
GROUP BY 1, 2, 3;

-- Meta threats as formes, not species: usage split by stone share, with the base forme
-- taking whatever is left. Variants under mega_variant_min_share are dropped.
-- Parameters are meta_usage's; see sql/marts/00_meta_usage.sql for what each one means.
CREATE OR REPLACE MACRO meta_top(reg, cut, since, min_players, weight_mode) AS TABLE
WITH u AS (
    SELECT regulation, snapshot_date, pokemon_id, usage_pct, "rank", sample_size
    FROM meta_usage(reg, cut, since, min_players, weight_mode)
),
stone_total AS (
    SELECT regulation, pokemon_id, sum(share) AS total
    FROM mart_meta_stone_share
    GROUP BY 1, 2
),
variant AS (
    SELECT u.regulation, u.snapshot_date, u.pokemon_id AS species_id,
           s.forme_id, s.share AS forme_share, u.usage_pct, u."rank", u.sample_size
    FROM u
    JOIN mart_meta_stone_share s
      ON s.regulation = u.regulation AND s.pokemon_id = u.pokemon_id
    UNION ALL
    SELECT u.regulation, u.snapshot_date, u.pokemon_id, u.pokemon_id,
           1 - coalesce(t.total, 0), u.usage_pct, u."rank", u.sample_size
    FROM u
    LEFT JOIN stone_total t
      ON t.regulation = u.regulation AND t.pokemon_id = u.pokemon_id
)
-- One row per forme, not per contributing species. Two formes of one species can
-- share a Mega -- Floette and Floette-Eternal both carry base_species_id 'floette'
-- and both become Floette-Mega -- and leaving them apart splits one threat's usage
-- across two rows, understating it (11.9% + 1.9% shown as 11.9%). Species-level
-- columns keep the largest contributor's values, since that is also the species whose
-- build data the downstream marts join on for moves, items, spreads and Scarf share.
SELECT v.regulation, v.snapshot_date,
       arg_max(v.species_id, v.usage_pct * v.forme_share) AS species_id,
       v.forme_id, p.display_name,
       p.is_mega, p.type1, p.type2, p.hp, p.atk, p."def", p.spa, p.spd, p.spe,
       arg_max(v.forme_share, v.usage_pct * v.forme_share) AS forme_share,
       arg_max(v.usage_pct, v.usage_pct * v.forme_share) AS species_usage_pct,
       sum(v.usage_pct * v.forme_share) AS forme_usage_pct,
       arg_max(v."rank", v.usage_pct * v.forme_share) AS species_rank,
       max(v.sample_size) AS sample_size,
       count(*) AS contributing_species
FROM variant v
JOIN dim_pokemon p ON p.pokemon_id = v.forme_id
WHERE v.forme_share >= {{mega_variant_min_share}}
GROUP BY v.regulation, v.snapshot_date, v.forme_id, p.display_name, p.is_mega,
         p.type1, p.type2, p.hp, p.atk, p."def", p.spa, p.spd, p.spe
ORDER BY forme_usage_pct DESC;

-- The unfiltered default, so every existing reader keeps working unchanged.
CREATE OR REPLACE VIEW mart_meta_top AS
SELECT * FROM meta_top(NULL, NULL, NULL, NULL, 'teams');
