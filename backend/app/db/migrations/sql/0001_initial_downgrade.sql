-- Reverses 0001_initial_upgrade.sql (drops every SiteScout table; the postgis extension is kept).
DROP TABLE IF EXISTS category_configs;
DROP TABLE IF EXISTS agent_runs;
DROP TABLE IF EXISTS recommendations;
DROP TABLE IF EXISTS analyses;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS cell_features;
DROP TABLE IF EXISTS market_intel;
DROP TABLE IF EXISTS listings;
DROP TABLE IF EXISTS pois;
DROP TABLE IF EXISTS ingest_jobs;
DROP TABLE IF EXISTS cell_attributes;
DROP TABLE IF EXISTS cells;
DROP TABLE IF EXISTS cities;
