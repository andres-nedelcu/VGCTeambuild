-- Which species actually show up on a team together, from the tournament teamlists.
--
-- PROJECT_OUTLINE and HANDOFF §6.11 deferred this because CBD's teammate rows carry
-- no percentage. They are not needed: fact_tournament_set is 1,553 real teams, and a
-- self-join over it gives true co-occurrence for free. Species grain, not forme --
-- you pick a species and the stone is a build choice made later.
--
-- Three numbers, because share alone is misleading:
--   share_of_a  of the teams running A, the share that also run B
--   share_of_b  the same the other way, since pairs are rarely symmetric
--   lift        how much more often they appear together than independent picks
--               would predict. Rillaboom is on over half of all teams, so almost
--               everything "pairs" with it at a high share; lift near 1 means the
--               pair is just two popular Pokemon meeting by chance, and lift well
--               above 1 means they are actually chosen for each other.
--
-- Parameters are meta_usage's; see sql/marts/00_meta_usage.sql. Filters flow through
-- meta_entries, so "cores among top-cut teams" is the same question asked of a
-- smaller, better population.
CREATE OR REPLACE MACRO meta_cores(reg, cut, since, min_players, weight_mode) AS TABLE
WITH entry AS (
    SELECT * FROM meta_entries(reg, cut, since, min_players, weight_mode)
),
team AS (
    SELECT DISTINCT regulation, tournament_id, player_id, wt FROM entry
),
total AS (
    SELECT regulation, sum(wt) AS denom FROM team GROUP BY 1
),
solo AS (
    SELECT regulation, pokemon_id, sum(wt) AS w FROM entry GROUP BY 1, 2
),
pair AS (
    SELECT a.regulation, a.pokemon_id AS a_id, b.pokemon_id AS b_id, sum(a.wt) AS w
    FROM entry a
    JOIN entry b
      ON b.regulation = a.regulation
     AND b.tournament_id = a.tournament_id
     AND b.player_id = a.player_id
     AND b.pokemon_id > a.pokemon_id
    GROUP BY 1, 2, 3
)
SELECT p.regulation,
       p.a_id, p.b_id,
       da.display_name AS a_name, db.display_name AS b_name,
       p.w AS together,
       sa.w AS teams_a, sb.w AS teams_b,
       p.w / nullif(sa.w, 0) AS share_of_a,
       p.w / nullif(sb.w, 0) AS share_of_b,
       (p.w * o.denom) / nullif(sa.w * sb.w, 0) AS lift
FROM pair p
JOIN solo sa ON sa.regulation = p.regulation AND sa.pokemon_id = p.a_id
JOIN solo sb ON sb.regulation = p.regulation AND sb.pokemon_id = p.b_id
JOIN total o ON o.regulation = p.regulation
JOIN dim_pokemon da ON da.pokemon_id = p.a_id
JOIN dim_pokemon db ON db.pokemon_id = p.b_id
WHERE p.w > 0
ORDER BY p.w DESC;

-- The unfiltered default, matching the other marts.
CREATE OR REPLACE VIEW mart_meta_cores AS
SELECT * FROM meta_cores(NULL, NULL, NULL, NULL, 'teams');
