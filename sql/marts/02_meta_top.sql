-- Share of a species' teams holding each Mega stone, keyed to the forme that stone makes.
CREATE OR REPLACE VIEW mart_meta_stone_share AS
SELECT d.regulation, d.pokemon_id, i.mega_forme_id AS forme_id, sum(d.pct) AS share
FROM mart_build_detail d
JOIN dim_item i ON i.item_id = d.detail_value
WHERE d.detail_type = 'item' AND i.is_mega_stone AND i.mega_forme_id IS NOT NULL
GROUP BY 1, 2, 3;

-- Meta threats as formes, not species: Limitless usage split by stone share, with the
-- base forme taking whatever is left. Variants under mega_variant_min_share are dropped.
CREATE OR REPLACE VIEW mart_meta_top AS
WITH u AS (
    SELECT regulation, snapshot_date, pokemon_id, usage_pct, "rank", sample_size
    FROM fact_usage
    WHERE source = 'limitless'
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
SELECT v.regulation, v.snapshot_date, v.species_id, v.forme_id, p.display_name,
       p.is_mega, p.type1, p.type2, p.hp, p.atk, p."def", p.spa, p.spd, p.spe,
       v.forme_share,
       v.usage_pct AS species_usage_pct,
       v.usage_pct * v.forme_share AS forme_usage_pct,
       v."rank" AS species_rank,
       v.sample_size
FROM variant v
JOIN dim_pokemon p ON p.pokemon_id = v.forme_id
WHERE v.forme_share >= {{mega_variant_min_share}}
ORDER BY forme_usage_pct DESC;
