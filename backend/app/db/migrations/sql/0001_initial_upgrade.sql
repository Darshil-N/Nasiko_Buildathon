-- SiteScout initial schema: PostgreSQL 16 + PostGIS. Source: architecture-1.md section 8.2.
--
-- Deviations from section 8.2 (each needs the owner's approval, decision D-24):
--   D1  cities.key                a stable slug ('bengaluru') so ingestion can upsert idempotently.
--   D2  scrape_jobs -> ingest_jobs no Anakin: drops anakin_job_id and credits_used, adds city_id and
--                                 stats (row counts). listings.scrape_job_id -> ingest_job_id,
--                                 listings.scraped_at -> imported_at, listings.source_note added.
--   D3  cell_attributes           NEW table: per-cell facts derived from OSM geometry (land-use shares,
--                                 distance to the nearest main road, optional population).
--   D4  cell_features.category    NEW key column: features F1, F4, F5, F6 depend on the business category,
--                                 so they must be stored per (cell, category), which section 8.2 cannot do.
--   D5  CHECK constraints         on enumerated text columns, NOT NULL and ON DELETE rules for integrity.
--
-- Nothing in this file runs until the owner approves it (rule 2, gate G-DB).

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------------------------------
CREATE TABLE cities (
    id                SERIAL PRIMARY KEY,
    key               TEXT NOT NULL UNIQUE,                                  -- D1
    name              TEXT NOT NULL,
    state             TEXT,
    country           TEXT NOT NULL DEFAULT 'IN',
    bbox              GEOMETRY(Polygon, 4326),
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft', 'ingesting', 'ready', 'stale')),
    last_full_refresh TIMESTAMPTZ
);

CREATE TABLE cells (
    h3_index      TEXT PRIMARY KEY,                                          -- H3 resolution 9
    city_id       INT NOT NULL REFERENCES cities (id) ON DELETE CASCADE,
    centroid      GEOMETRY(Point, 4326) NOT NULL,
    boundary      GEOMETRY(Polygon, 4326),
    locality_name TEXT,
    land_use      TEXT CHECK (land_use IN ('residential', 'commercial', 'mixed', 'other'))
);
CREATE INDEX cells_centroid_gix ON cells USING GIST (centroid);
CREATE INDEX cells_city_idx ON cells (city_id);

CREATE TABLE cell_attributes (                                               -- D3
    h3_index                  TEXT PRIMARY KEY REFERENCES cells (h3_index) ON DELETE CASCADE,
    landuse_residential_share NUMERIC(5, 4) NOT NULL DEFAULT 0
                              CHECK (landuse_residential_share BETWEEN 0 AND 1),
    landuse_commercial_share  NUMERIC(5, 4) NOT NULL DEFAULT 0
                              CHECK (landuse_commercial_share BETWEEN 0 AND 1),
    landuse_retail_share      NUMERIC(5, 4) NOT NULL DEFAULT 0
                              CHECK (landuse_retail_share BETWEEN 0 AND 1),
    main_road_dist_m          NUMERIC(10, 1) CHECK (main_road_dist_m >= 0),
    main_road_class           TEXT CHECK (main_road_class IN ('trunk', 'primary', 'secondary')),
    population_est            NUMERIC CHECK (population_est >= 0),           -- NULL until D-06 is decided
    source_version            TEXT,
    computed_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ingest_jobs (                                                   -- D2 (was scrape_jobs)
    id          BIGSERIAL PRIMARY KEY,
    city_id     INT REFERENCES cities (id) ON DELETE SET NULL,
    source      TEXT NOT NULL,                                               -- osm | csv | market_intel
    purpose     TEXT,                                                        -- pois | landuse | roads | places | rent_csv | growth
    target      TEXT,
    status      TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'done', 'failed')),
    raw_path    TEXT,
    stats       JSONB,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE pois (
    id         BIGSERIAL PRIMARY KEY,
    osm_type   TEXT,
    osm_id     BIGINT,
    city_id    INT NOT NULL REFERENCES cities (id) ON DELETE CASCADE,
    category   TEXT NOT NULL,                                                -- normalised, see config/osm_tags.yaml
    name       TEXT,
    brand      TEXT,
    tier_guess TEXT NOT NULL DEFAULT 'unknown'
               CHECK (tier_guess IN ('budget', 'mid', 'premium', 'unknown')),
    location   GEOMETRY(Point, 4326) NOT NULL,
    h3_index   TEXT REFERENCES cells (h3_index) ON DELETE SET NULL,          -- NULL for POIs just outside the city
    tags       JSONB,
    source     TEXT NOT NULL DEFAULT 'osm',
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (osm_type, osm_id)
);
CREATE INDEX pois_location_gix ON pois USING GIST (location);
CREATE INDEX pois_category_idx ON pois (category);
CREATE INDEX pois_city_category_idx ON pois (city_id, category);
CREATE INDEX pois_h3_idx ON pois (h3_index);

CREATE TABLE listings (
    id             BIGSERIAL PRIMARY KEY,
    ingest_job_id  BIGINT REFERENCES ingest_jobs (id) ON DELETE SET NULL,   -- D2
    city_id        INT NOT NULL REFERENCES cities (id) ON DELETE CASCADE,
    source         TEXT,
    url            TEXT,
    listing_type   TEXT CHECK (listing_type IN ('rent', 'sale')),
    property_type  TEXT CHECK (property_type IN ('shop', 'office', 'showroom', 'apartment', 'plot')),
    price_inr      NUMERIC CHECK (price_inr > 0),
    price_period   TEXT CHECK (price_period IN ('month', 'total')),
    area_sqft      NUMERIC CHECK (area_sqft > 0),
    price_per_sqft NUMERIC CHECK (price_per_sqft > 0),
    locality       TEXT,
    address_text   TEXT,
    location       GEOMETRY(Point, 4326),
    geo_precision  TEXT CHECK (geo_precision IN ('exact', 'locality')),
    h3_index       TEXT REFERENCES cells (h3_index) ON DELETE SET NULL,
    posted_date    DATE,
    source_note    TEXT,                                                     -- D2
    imported_at    TIMESTAMPTZ NOT NULL DEFAULT now()                        -- D2 (was scraped_at)
);
CREATE INDEX listings_h3_idx ON listings (h3_index);
CREATE INDEX listings_city_idx ON listings (city_id);

CREATE TABLE market_intel (
    id                BIGSERIAL PRIMARY KEY,
    city_id           INT NOT NULL REFERENCES cities (id) ON DELETE CASCADE,
    category          TEXT,                                                  -- clothing | cafe | pharmacy | general
    topic             TEXT,                                                  -- market_reputation | growth_news
    summary           TEXT,
    sources           JSONB,                                                 -- [{title, url}]
    locality_mentions TEXT[],
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX market_intel_city_idx ON market_intel (city_id);

CREATE TABLE cell_features (
    h3_index          TEXT NOT NULL REFERENCES cells (h3_index) ON DELETE CASCADE,
    category          TEXT NOT NULL,                                         -- D4 (cafe | clothing | pharmacy)
    feature_version   INT NOT NULL,
    features          JSONB NOT NULL,                                        -- raw and normalised F1..F9 and helper metrics
    affluence         NUMERIC CHECK (affluence BETWEEN 0 AND 1),
    rent_per_sqft_est NUMERIC CHECK (rent_per_sqft_est > 0),
    rent_is_estimated BOOLEAN,
    confidence        NUMERIC CHECK (confidence BETWEEN 0 AND 1),
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (h3_index, category, feature_version)                        -- D4
);

CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    external_id TEXT UNIQUE,
    email       TEXT,
    role        TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner', 'analyst', 'admin')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE analyses (
    id                TEXT PRIMARY KEY,                                      -- an_xxxxxxxx
    user_id           BIGINT REFERENCES users (id) ON DELETE SET NULL,
    city_id           INT NOT NULL REFERENCES cities (id),
    category          TEXT NOT NULL,
    tier              TEXT NOT NULL CHECK (tier IN ('budget', 'mid', 'premium')),
    answers           JSONB,
    constraints       JSONB,
    config_version    TEXT,
    status            TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'running', 'done', 'failed')),
    summary_narrative TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ
);
CREATE INDEX analyses_user_idx ON analyses (user_id, created_at DESC);

CREATE TABLE recommendations (
    id                 BIGSERIAL PRIMARY KEY,
    analysis_id        TEXT NOT NULL REFERENCES analyses (id) ON DELETE CASCADE,
    rank               INT,
    h3_index           TEXT REFERENCES cells (h3_index),
    zone_name          TEXT,
    score              NUMERIC CHECK (score BETWEEN 0 AND 100),
    confidence         NUMERIC CHECK (confidence BETWEEN 0 AND 1),
    contributions      JSONB,
    top_drivers        JSONB,
    top_risks          JSONB,
    nearby_listing_ids BIGINT[],
    narrative          TEXT
);
CREATE INDEX recommendations_analysis_idx ON recommendations (analysis_id, rank);

CREATE TABLE agent_runs (
    id          BIGSERIAL PRIMARY KEY,
    analysis_id TEXT,
    agent_name  TEXT,
    status      TEXT,
    latency_ms  INT,
    tokens_in   INT,
    tokens_out  INT,
    cost_usd    NUMERIC NOT NULL DEFAULT 0,                                  -- always 0 in the free MVP
    trace_id    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX agent_runs_analysis_idx ON agent_runs (analysis_id);

CREATE TABLE category_configs (
    category  TEXT NOT NULL,
    version   TEXT NOT NULL,
    config    JSONB NOT NULL,                                                -- mirrors config/categories/*.yaml
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (category, version)
);
