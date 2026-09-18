-- Damaging moves each threat runs often enough to plan around.
CREATE OR REPLACE VIEW mart_meta_common_moves AS
SELECT t.regulation, t.snapshot_date, t.species_id, t.forme_id, t.display_name,
       m.move_id, m.display_name AS move_name, m.type AS move_type, m.category,
       m.base_power, m.is_spread,
       d.pct AS move_share,
       t.forme_usage_pct, t.species_rank
FROM mart_meta_top t
JOIN mart_build_detail d
  ON d.regulation = t.regulation AND d.pokemon_id = t.species_id AND d.detail_type = 'move'
JOIN dim_move m ON m.move_id = d.detail_value
WHERE d.pct >= {{common_move_threshold}} AND m.category <> 'Status'
ORDER BY t.forme_usage_pct DESC, d.pct DESC;
