-- The Pokémon combinations people actually bring together, three at a time.
--
-- mart_meta_cores answers "which pairs go together". This answers the question a
-- player asks when planning: "what am I likely to be facing as a unit". A trio is
-- the useful grain -- a pair under-describes an archetype and a full six is almost
-- never repeated exactly, while trios recur often enough to plan against.
--
-- Support is a plain count, not lift: unlike pairs, a popular trio IS the thing you
-- want to see. Lift matters for asking whether two Pokémon are *chosen* for each
-- other; frequency matters for asking what you will run into.
CREATE OR REPLACE MACRO meta_combos(reg, cut, since, min_players, weight_mode) AS TABLE
WITH entry AS (
    SELECT * FROM meta_entries(reg, cut, since, min_players, weight_mode)
),
team AS (
    SELECT DISTINCT regulation, tournament_id, player_id, wt FROM entry
),
total AS (
    SELECT regulation, count(*) AS teams FROM team GROUP BY 1
),
trio AS (
    SELECT a.regulation, a.pokemon_id AS a_id, b.pokemon_id AS b_id, c.pokemon_id AS c_id,
           count(*) AS together
    FROM entry a
    JOIN entry b ON b.regulation = a.regulation AND b.tournament_id = a.tournament_id
                AND b.player_id = a.player_id AND b.pokemon_id > a.pokemon_id
    JOIN entry c ON c.regulation = a.regulation AND c.tournament_id = a.tournament_id
                AND c.player_id = a.player_id AND c.pokemon_id > b.pokemon_id
    GROUP BY 1, 2, 3, 4
)
SELECT t.regulation, t.a_id, t.b_id, t.c_id,
       da.display_name AS a_name, db.display_name AS b_name, dc.display_name AS c_name,
       t.together,
       t.together / nullif(o.teams, 0) AS share
FROM trio t
JOIN total o ON o.regulation = t.regulation
JOIN dim_pokemon da ON da.pokemon_id = t.a_id
JOIN dim_pokemon db ON db.pokemon_id = t.b_id
JOIN dim_pokemon dc ON dc.pokemon_id = t.c_id
ORDER BY t.together DESC;

CREATE OR REPLACE VIEW mart_meta_combos AS
SELECT * FROM meta_combos(NULL, NULL, NULL, NULL, 'teams');
