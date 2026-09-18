-- Build data (moves, items, abilities) for one species comes from a single source.
-- CBD is preferred because it is the larger build sample; Limitless teamlists are the
-- fallback for species CBD does not cover. Usage weight never comes from here.
CREATE OR REPLACE VIEW mart_build_detail AS
WITH pick AS (
    SELECT regulation, pokemon_id,
           CASE WHEN bool_or(source = 'cbd') THEN 'cbd' ELSE 'limitless' END AS build_source
    FROM fact_usage_detail
    GROUP BY 1, 2
)
SELECT d.*
FROM fact_usage_detail d
JOIN pick p
  ON p.regulation = d.regulation
 AND p.pokemon_id = d.pokemon_id
 AND p.build_source = d.source;
