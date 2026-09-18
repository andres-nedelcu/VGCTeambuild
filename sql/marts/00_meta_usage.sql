-- Parameterised meta usage over the tournament sets, replacing the fact_usage rollup
-- as the marts' source so the meta side can be filtered.
--
-- fact_usage is a precomputed rollup with one row per species per regulation and no
-- placement, date or event-size dimension, so it cannot be filtered at all. The same
-- numbers are recoverable from fact_tournament_set (9,318 rows), which carries
-- placement and wins/losses/ties and joins to fact_tournament for event_date and
-- players. Aggregating it per filter selection costs single-digit milliseconds.
--
-- The definition mirrors scripts/load_limitless.py exactly, so meta_usage with every
-- filter off reproduces fact_usage row for row (pinned by tests/test_meta_usage.py):
--   a team is (tournament_id, player_id); a species counts once per team;
--   usage_pct = teams holding the species / total teams, per regulation.
-- Only "rank" differs, and only among equal-usage species: the loader's rank comes
-- from a Python sort with an arbitrary tiebreak, this one breaks ties on pokemon_id
-- so repeated builds agree.
--
-- Parameters -- NULL means "no filter", so meta_usage(NULL,NULL,NULL,NULL,'teams')
-- is the whole regulation, every event, every finisher:
--   reg          regulation code, e.g. 'M-C'; NULL for all regulations
--   cut          keep only finishers at or above this placement (top-cut view)
--   since        keep only events on or after this date (recency)
--   min_players  keep only events at least this large
--   weight_mode  'teams' = every team counts 1
--                'wins'  = every team counts its match wins, so usage becomes the
--                          share of wins earned by teams holding the species
--
-- On 'wins': weighting by wins rather than win *rate* is deliberate. 408 of 1,553
-- entries have no placement and average 1.19W/2.13L over 3.3 games (the placed
-- average 2.73W/2.58L over 5.3) -- they dropped early. A win-rate weight would need
-- an arbitrary minimum-games floor to stop those entries from swinging it; weighting
-- by wins lets them self-discount to near zero with no threshold to tune.
--
-- On 'cut': placement runs dense 1..N in every event with the remainder NULL, so
-- placement <= cut is exactly "top N finishers", and the NULLs it excludes are those
-- same early droppers. Two limits worth stating in the app: a fixed cut means
-- different things across a 42-player and a 148-player event (a percentile cut is a
-- possible follow-up), and the sample shrinks fast -- top 16 is 304 teams against
-- 1,553 unfiltered, so small rank moves inside a cut view are noise.
--
-- snapshot_date is the latest event_date included, not a load date: for a view
-- computed per filter selection, "the meta as of this event" is the honest label.
CREATE OR REPLACE MACRO meta_usage(reg, cut, since, min_players, weight_mode) AS TABLE
WITH entry AS (
    SELECT DISTINCT
           t.regulation, s.tournament_id, s.player_id, s.pokemon_id, t.event_date,
           CASE WHEN weight_mode = 'wins' THEN coalesce(s.wins, 0) ELSE 1 END AS wt
    FROM fact_tournament_set s
    JOIN fact_tournament t USING (tournament_id)
    WHERE (reg IS NULL OR t.regulation = reg)
      AND (cut IS NULL OR (s.placement IS NOT NULL AND s.placement <= cut))
      AND (since IS NULL OR t.event_date >= since)
      AND (min_players IS NULL OR t.players >= min_players)
),
team AS (
    SELECT DISTINCT regulation, tournament_id, player_id, event_date, wt FROM entry
),
total AS (
    SELECT regulation, sum(wt) AS denom, count(*) AS n_teams, max(event_date) AS as_of
    FROM team GROUP BY 1
),
species AS (
    SELECT regulation, pokemon_id, sum(wt) AS wt, count(*) AS n_teams
    FROM entry GROUP BY 1, 2
)
SELECT s.regulation,
       o.as_of AS snapshot_date,
       s.pokemon_id,
       s.wt / nullif(o.denom, 0) AS usage_pct,
       row_number() OVER (PARTITION BY s.regulation ORDER BY s.wt DESC, s.pokemon_id) AS "rank",
       o.n_teams AS sample_size,
       s.n_teams AS species_teams
FROM species s
JOIN total o ON o.regulation = s.regulation
WHERE s.wt > 0
ORDER BY s.regulation, s.wt DESC, s.pokemon_id;
