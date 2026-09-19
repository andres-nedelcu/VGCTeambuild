-- Modal stat investment per species, for every stat, not just Speed.
--
-- Generalises what 03_meta_speed.sql does for the Speed slot. The same finding holds
-- across the board and is what makes a damage estimate possible at all: whole spreads
-- are fragmented (the modal full spread averages 29% of a species' builds) but any
-- SINGLE slot is concentrated, because the fragmentation is spread across the other
-- five. Measured over the landed CBD data:
--
--     Atk  modal share 0.887   254/262 species above 50%
--     SpA  modal share 0.893   249/262
--     Spe  modal share 0.790   230/262
--     HP / Def / SpD  0.63-0.67
--
-- Attackers, in other words, run max offence nearly always; defensive slots are the
-- uncertain ones. A damage figure built on this is solid on the attacking side and
-- should say so about the defending side.
--
-- Slots are the spread string's order: 1 HP, 2 Atk, 3 Def, 4 SpA, 5 SpD, 6 Spe.
CREATE OR REPLACE MACRO meta_investment(reg, cut, since, min_players, weight_mode) AS TABLE
WITH parsed AS (
    SELECT d.regulation, d.pokemon_id, d.pct, s.slot,
           try_cast(str_split(d.detail_value, '/')[s.slot] AS INT) AS sp
    FROM mart_build_detail d
    CROSS JOIN (SELECT unnest([1, 2, 3, 4, 5, 6]) AS slot) s
    WHERE d.detail_type = 'spread'
),
tallied AS (
    SELECT regulation, pokemon_id, slot, sp, sum(pct) AS w
    FROM parsed WHERE sp IS NOT NULL
    GROUP BY 1, 2, 3, 4
),
ranked AS (
    SELECT regulation, pokemon_id, slot, sp,
           w / sum(w) OVER (PARTITION BY regulation, pokemon_id, slot) AS share,
           row_number() OVER (PARTITION BY regulation, pokemon_id, slot
                              ORDER BY w DESC, sp) AS rn
    FROM tallied
)
SELECT regulation, pokemon_id, slot,
       CASE slot WHEN 1 THEN 'hp' WHEN 2 THEN 'atk' WHEN 3 THEN 'def'
                 WHEN 4 THEN 'spa' WHEN 5 THEN 'spd' ELSE 'spe' END AS stat,
       sp, share
FROM ranked WHERE rn = 1
ORDER BY regulation, pokemon_id, slot;

CREATE OR REPLACE VIEW mart_meta_investment AS
SELECT * FROM meta_investment(NULL, NULL, NULL, NULL, 'teams');
