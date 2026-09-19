-- Cores conditioned on the item the holder is carrying.
--
-- Why this exists: species-level co-occurrence can average two mutually exclusive
-- archetypes into nothing. Sneasler is the case that exposed it. It runs Unburden on
-- 89% of builds and a terrain seed on 58%, split almost evenly between Grassy Seed
-- and Psychic Seed, because the seed is consumed by the terrain and Unburden then
-- doubles its Speed. Those two builds demand *different* partners:
--
--     Sneasler @ Grassy Seed   -> 99% run Rillaboom   (base rate 54%)
--     Sneasler @ Psychic Seed  -> 100% run Indeedee   (base rate 27%)
--     Sneasler @ White Herb    -> 52% Rillaboom, i.e. the base rate, no association
--
-- Aggregated over items those two cancel, and Sneasler + Rillaboom lands at a lift of
-- 1.03 — indistinguishable from chance, and badly wrong. Conditioning on the item
-- recovers a near-deterministic relationship.
--
-- Grain: one row per (holder species, holder's item, partner species).
--   share       P(partner | holder holds this item)
--   base_share  P(partner | holder), over all items
--   delta       share - base_share, which is what makes a build worth showing
--
-- Items come from fact_tournament_set, so they are what players actually brought to
-- these events, not a ladder build distribution.
CREATE OR REPLACE MACRO meta_item_cores(reg, cut, since, min_players, weight_mode) AS TABLE
WITH entry AS (
    SELECT * FROM meta_entries(reg, cut, since, min_players, weight_mode)
),
held AS (
    SELECT e.regulation, e.tournament_id, e.player_id, e.pokemon_id, e.wt, s.item_id
    FROM entry e
    JOIN fact_tournament_set s
      ON s.tournament_id = e.tournament_id
     AND s.player_id = e.player_id
     AND s.pokemon_id = e.pokemon_id
    WHERE s.item_id IS NOT NULL
),
holder_item AS (
    SELECT regulation, pokemon_id, item_id, sum(wt) AS w
    FROM held GROUP BY 1, 2, 3
),
holder_all AS (
    SELECT regulation, pokemon_id, sum(wt) AS w FROM entry GROUP BY 1, 2
),
pair_item AS (
    SELECT h.regulation, h.pokemon_id AS holder_id, h.item_id,
           p.pokemon_id AS partner_id, sum(h.wt) AS w
    FROM held h
    JOIN entry p
      ON p.regulation = h.regulation AND p.tournament_id = h.tournament_id
     AND p.player_id = h.player_id AND p.pokemon_id <> h.pokemon_id
    GROUP BY 1, 2, 3, 4
),
partner_all AS (
    SELECT regulation, pokemon_id, sum(wt) AS w FROM entry GROUP BY 1, 2
),
total AS (
    SELECT regulation, sum(wt) AS denom
    FROM (SELECT DISTINCT regulation, tournament_id, player_id, wt FROM entry)
    GROUP BY 1
),
pair_all AS (
    SELECT e.regulation, e.pokemon_id AS holder_id, p.pokemon_id AS partner_id,
           sum(e.wt) AS w
    FROM entry e
    JOIN entry p
      ON p.regulation = e.regulation AND p.tournament_id = e.tournament_id
     AND p.player_id = e.player_id AND p.pokemon_id <> e.pokemon_id
    GROUP BY 1, 2, 3
)
SELECT pi.regulation,
       pi.holder_id, dh.display_name AS holder_name,
       pi.item_id, di.display_name AS item_name,
       pi.partner_id, dp.display_name AS partner_name,
       pi.w AS together,
       hi.w AS holder_teams_with_item,
       ha.w AS holder_teams,
       pi.w / nullif(hi.w, 0) AS share,
       pa.w / nullif(ha.w, 0) AS base_share,
       (pi.w / nullif(hi.w, 0)) - (pa.w / nullif(ha.w, 0)) AS delta,
       -- Lift for this build specifically: how much more often the partner turns up
       -- beside this item than its own popularity would predict. Comparable with
       -- mart_meta_cores.lift, and subject to the same ceiling of 1 / partner usage.
       (pi.w / nullif(hi.w, 0)) / nullif(pt.w / o.denom, 0) AS lift
FROM pair_item pi
JOIN holder_item hi
  ON hi.regulation = pi.regulation AND hi.pokemon_id = pi.holder_id AND hi.item_id = pi.item_id
JOIN holder_all ha
  ON ha.regulation = pi.regulation AND ha.pokemon_id = pi.holder_id
LEFT JOIN pair_all pa
  ON pa.regulation = pi.regulation AND pa.holder_id = pi.holder_id
 AND pa.partner_id = pi.partner_id
JOIN partner_all pt
  ON pt.regulation = pi.regulation AND pt.pokemon_id = pi.partner_id
JOIN total o ON o.regulation = pi.regulation
JOIN dim_pokemon dh ON dh.pokemon_id = pi.holder_id
JOIN dim_pokemon dp ON dp.pokemon_id = pi.partner_id
LEFT JOIN dim_item di ON di.item_id = pi.item_id
ORDER BY delta DESC;

CREATE OR REPLACE VIEW mart_meta_item_cores AS
SELECT * FROM meta_item_cores(NULL, NULL, NULL, NULL, 'teams');
