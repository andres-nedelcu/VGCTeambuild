-- Damaging moves each threat runs often enough to plan around.
-- Parameters are meta_usage's; see sql/marts/00_meta_usage.sql for what each one means.
-- Move shares stay species-level and unfiltered: they come from build data, which
-- carries no placement or date dimension. A filter changes which threats appear and
-- how they are weighted, not what those threats are believed to run.
CREATE OR REPLACE MACRO meta_common_moves(reg, cut, since, min_players, weight_mode) AS TABLE
SELECT t.regulation, t.snapshot_date, t.species_id, t.forme_id, t.display_name,
       m.move_id, m.display_name AS move_name, m.type AS move_type, m.category,
       m.base_power, m.is_spread,
       d.pct AS move_share,
       t.forme_usage_pct, t.species_rank
FROM meta_top(reg, cut, since, min_players, weight_mode) t
JOIN mart_build_detail d
  ON d.regulation = t.regulation AND d.pokemon_id = t.species_id AND d.detail_type = 'move'
JOIN dim_move m ON m.move_id = d.detail_value
WHERE d.pct >= {{common_move_threshold}} AND m.category <> 'Status'
ORDER BY t.forme_usage_pct DESC, d.pct DESC;

-- The unfiltered default, so every existing reader keeps working unchanged.
CREATE OR REPLACE VIEW mart_meta_common_moves AS
SELECT * FROM meta_common_moves(NULL, NULL, NULL, NULL, 'teams');
