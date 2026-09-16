-- 00_schema.sql
-- Warehouse DDL. Idempotent: safe to rerun.

-- ───────────── Static layer ─────────────

CREATE TABLE IF NOT EXISTS dim_pokemon (
    pokemon_id       VARCHAR PRIMARY KEY,   -- Showdown ID of the battle forme
    display_name     VARCHAR,
    base_species_id  VARCHAR,
    is_mega          BOOLEAN,
    type1            VARCHAR,
    type2            VARCHAR,               -- NULL if single type
    hp INT, atk INT, def INT, spa INT, spd INT, spe INT,
    abilities        VARCHAR[],
    data_source      VARCHAR,               -- 'showdown' | 'showdown_champions_mod' | 'manual'
    loaded_at        TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_type_chart (
    atk_type    VARCHAR,
    def_type    VARCHAR,
    multiplier  DOUBLE,                     -- 0, 0.5, 1, 2
    PRIMARY KEY (atk_type, def_type)
);

CREATE TABLE IF NOT EXISTS dim_move (
    move_id      VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    type         VARCHAR,
    category     VARCHAR,                   -- Physical | Special | Status
    base_power   INT,
    accuracy     INT,
    priority     INT,
    target       VARCHAR,
    is_spread    BOOLEAN
);

CREATE TABLE IF NOT EXISTS dim_item (
    item_id       VARCHAR PRIMARY KEY,
    display_name  VARCHAR,
    is_mega_stone BOOLEAN,
    mega_forme_id VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_ability_type_modifier (
    ability_id  VARCHAR,
    atk_type    VARCHAR,
    multiplier  DOUBLE,                     -- levitate/ground = 0, thickfat/fire = 0.5
    PRIMARY KEY (ability_id, atk_type)
);

-- ───────────── Live layer (append-only) ─────────────

CREATE TABLE IF NOT EXISTS fact_usage (
    source         VARCHAR,                 -- 'cbd' | 'limitless' | 'smogon'
    regulation     VARCHAR,
    snapshot_date  DATE,
    pokemon_id     VARCHAR,
    usage_pct      DOUBLE,
    rank           INT,
    sample_size    INT,                     -- teams or battles; see DECISIONS.md
    loaded_at      TIMESTAMP,
    PRIMARY KEY (source, regulation, snapshot_date, pokemon_id)
);

CREATE TABLE IF NOT EXISTS fact_usage_detail (
    source         VARCHAR,
    regulation     VARCHAR,
    snapshot_date  DATE,
    pokemon_id     VARCHAR,
    detail_type    VARCHAR,                 -- 'move' | 'item' | 'ability' | 'spread' | 'teammate'
    detail_value   VARCHAR,
    pct            DOUBLE,
    loaded_at      TIMESTAMP,
    PRIMARY KEY (source, regulation, snapshot_date, pokemon_id, detail_type, detail_value)
);

CREATE TABLE IF NOT EXISTS fact_tournament (
    tournament_id  VARCHAR PRIMARY KEY,
    name           VARCHAR,
    regulation     VARCHAR,
    event_date     DATE,
    players        INT,
    has_teamlists  BOOLEAN,
    is_online      BOOLEAN,
    loaded_at      TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_tournament_set (
    tournament_id  VARCHAR,
    player_id      VARCHAR,
    placement      INT,                     -- "placing" is reserved in DuckDB
    wins INT, losses INT, ties INT,
    slot           INT,                     -- 1–6
    pokemon_id     VARCHAR,
    item_id        VARCHAR,
    ability_id     VARCHAR,
    moves          VARCHAR[],
    PRIMARY KEY (tournament_id, player_id, slot)
);

-- ───────────── Your team ─────────────

CREATE TABLE IF NOT EXISTS my_team (
    paste_id    VARCHAR,
    team_name   VARCHAR,
    slot        INT,
    pokemon_id  VARCHAR,
    nickname    VARCHAR,
    item_id     VARCHAR,
    ability_id  VARCHAR,
    nature      VARCHAR,
    investment  JSON,                       -- raw investment as parsed (see outline 7.5)
    moves       VARCHAR[],
    loaded_at   TIMESTAMP,
    PRIMARY KEY (paste_id, slot)
);
