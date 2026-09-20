# SiteScout: Build Progress (Free MVP edition)

> Detailed tracker for `plan.md` (version 0.5). Step IDs match the plan (`P.Part.Step`). Every step is broken into micro-tasks; **progress % = ticked micro-tasks ÷ total micro-tasks**.
> Last updated: 2026-09-20 · Overall status: **Phase 0 in progress** (Docker and the Nasiko stack are running; repo scaffolded with a local git repository; work split between two agents; no application code and no database yet).

**How to read this file**
- `- [ ]` not done · `- [x]` done · `- [~]` in progress · `- [!]` blocked (say why on the same line).
- `- [-]` cut from the MVP by the owner; cut tasks are not counted in the totals.
- 🔒 marks a micro-task that needs the owner's approval first (gates G-DB, G-EDIT, G-PUSH, G-COST, G-DECIDE, G-DEVIATE from `plan.md` §3).
- Update this file in the same change as the work it describes.

---

## 1. Summary

<!-- SUMMARY-START -->
| Phase | Name | Parts | Steps | Micro-tasks | Done | Progress | Status |
|---|---|---|---|---|---|---|---|
| 0 | Setup, verification and decisions | 6 | 34 | 108 | 64 | 59% | in progress |
| 1 | Data foundation | 7 | 33 | 96 | 77 | 80% | in progress |
| 2 | Optional rent data, growth signals and snapshot | 5 | 19 | 46 | 24 | 52% | in progress |
| 3 | Feature and scoring engine | 9 | 32 | 92 | 71 | 77% | in progress |
| 4 | Backend API | 9 | 30 | 65 | 35 | 54% | in progress |
| 5 | Agents on Nasiko | 8 | 25 | 64 | 13 | 20% | in progress |
| 6 | Streamlit app | 7 | 25 | 65 | 56 | 86% | in progress |
| 7 | Validation and tuning | 6 | 10 | 28 | 14 | 50% | in progress |
| 8 | Polish, hardening and demo | 8 | 21 | 44 | 13 | 30% | in progress |
| | **Total** | **65** | **229** | **608** | **367** | **60%** | |

Decisions (32 total): 5 partly answered · 8 proposed (awaiting your confirmation) · 15 answered · 1 deferred · 3 closed
<!-- SUMMARY-END -->

Refresh the table above with `python scripts/update_progress_summary.py` (from the repo root) after a batch of ticks.

### Work split and handoffs (two Claude agents; rules in `plan.md` §9)

| Agent | Steps | State |
|---|---|---|
| **A** (this session) | Phase 0 except 0.5.4; 1.1, 1.2.1, 1.2.5, 1.3–1.6; 2.1.5, 2.2.3, 2.4, 2.5; 3.8; Phase 4 except 4.3 and 4.6.4; Phase 5; 8.2, 8.3, 8.5, 8.7 | working |
| **B** (second session) | 0.5.4; 1.2.2–1.2.4; 1.7; 2.1.1–2.1.4, 2.2.1–2.2.2, 2.3; 3.1–3.7 (not 3.3.2, the 3.4.4 fallback, 3.7.3 or 3.6) and 3.9; 4.3 and 4.6.4; Phase 6; Phase 7; 8.1, 8.4, 8.6 | working: pointed at the remaining Phase 6 gaps (6.2.3 progress state, 6.4.2/6.4.3 map overlay, 6.6 UX states, 6.7.1 docs) |
| Joint | 8.8 sign-off | later |

**Handoffs** (requests between agents; the receiving agent updates the status):

| # | From | To | Request | Status |
|---|---|---|---|---|
| 1 | A | B | Scaffold, `.venv`, tool configs and local git are ready. Start with `shared/contracts.py` (cells, POIs, listings, market signals, `CellFeatures`) and tell A when it is ready, because A's database loaders and feature pipeline must produce exactly those shapes. | done |
| 2 | A | B | Config loader (`shared/config.py`) and category YAMLs are needed by A for `/categories` and ingestion. | done |
| 3 | A | B | LLM client (`shared/llm/`) is needed by A for the Nasiko agents (Phase 5). | done |
| 4 | A | B | The database is live and migrated (13 tables, all empty). Features are stored per (cell, category) because F1, F4, F5 and F6 depend on the category, so `CellFeatures` in `shared/contracts.py` needs a `category` field. New per-cell inputs come from `cell_attributes` (land-use shares, distance to the nearest main road and its class) plus POIs with their whitelisted `tags` (for example `building`, hotel `stars`). Please add a `CellAttributes` model to the contracts when you need it. | done |
| 5 | A | B | FYI: `ruff check` reports 7 findings in `tests/shared/test_config.py` (your file). | open |
| 7 | A | B | Backend skeleton is in place: `backend/app/core/errors.py` already emits the section 10.4 envelope (codes plus additive `UNAUTHORIZED` and `NOT_FOUND`), auth, settings and a read-only DB session. In `backend/app/schemas/` please provide the Pydantic `ErrorEnvelope` and the request and response models (4.3.1, 4.3.2) matching that shape. `GET /v1/categories` needs your `shared/config.py` loader once it is committed. | done |
| 8 | A | B | Agent runtime is ready: `agents/_shared/runner.py` (validate, run, envelope) and `a2a_glue.py`, plus `python -m scripts.deploy_agent <agent> --include agent_base=agents/_shared --include shared=shared` which packages `shared/` into an agent so your `shared/llm` client can be imported inside agents. Failure replies use an `error` object instead of `payload`; please mirror that in `AgentResponse` in `shared/contracts.py`. | open |
| 9 | A | B | Git rule (found the hard way): we share ONE index, so at 13:03 my bare `git commit` tried to include your staged files and the lint hook failed on them. From now on both of us commit with an explicit path list: `git commit -m "[B] ..." -- path1 path2`. Your files are still staged and untouched. Before you commit, run `ruff check` and `ruff format --check` on them (the hook found lint errors in some of your staged files, for example `tests/shared/test_config.py`). | open |
| 10 | A | B | For 3.8 (feature build) I propose this split: **you** provide one pure entry point, for example `scoring.build_cell_features(config, cells, catchments, attributes, ...) -> list[CellFeatures]`, doing the formulas and the city-wide percentile normalisation; **I** provide the inputs and the database I/O. Inputs I already have: `pipelines.catchments.iter_catchments(cells, pois, k=config.catchment_k, ...)` yields `(cell, list[POIRow with distance_m])` lazily, one cell at a time; `pipelines.city_dataset.build_dataset` gives cells, `CellAttributeRow` (land-use shares, main-road distance and class, locality, land use) and POIs. Because features are per (cell, category) and normalisation needs every cell, please make the entry point accept an iterator of cells but return the full list. Tell me if you prefer a different shape. | open |
| 11 | A | B | Owner decisions that unblock you (details in the Decision Log): **D-22 approved**: implement the no-rent variants (affluence = 2/3 premium-POI density + 1/3 apartment share; drop F8 and rescale weights when there is no rent data; confidence = 2/3 POI coverage + 1/3 recency plus a visible note; rent filter only where rent data exists), and keep the original formulas for when a rent CSV exists. **D-19 answered**: no boosters are scored; provide day-part profile, age-skew proxy and medical density as explanatory info in the zone detail data, without changing the score or the weight tables (skip parking, late-night, seasonality). **D-23**: Streamlit has no login. **D-04**: the orchestrator lives in the backend (I will call the agents in order). | open |
| 12 | A | B | More owner answers: **D-17**: please draft `config/brands_premium.yaml` per category (cafe, clothing, pharmacy) and tier (budget, mid, premium) for Bengaluru and put it in front of the owner for approval before it is used (also fix the placeholder that lists a pharmacy chain as premium). **Cuts**: PDF export is cut (skip 4.6.4 and the export screen 6.2.9) and Mumbai is cut. Growth signal (F9) and the compare-zones screen stay in. D-30 defaults are kept. | open |
| 13 | A | B | Feature build is done on my side and ranks with your engine: `pipelines/build_features.py` builds `CellFeatures` for all 3 tiers per cell and category (I used your `affluence_index`, `tier_fit`, `gap_opportunity`, `accessibility`, `growth_momentum`, `residential_demand`, `pct` unchanged) and `ScoreEngine.rank` consumes them. Observations for you: (1) top scores are tightly clustered (about 80 to 83 for all 10 zones), so ranking resolution is low; percentile ranks saturate near 1.0 for several features, so please look at spreading the score. (2) `rank` returns single cells; zone merging and names (3.7.5) are still needed. (3) `scoring.features.confidence_score` still has the four-term formula; I use `pipelines.build_features.confidence_without_rent` (D-22c), please fold it into your library. (4) I stored per-category decay sums (`anchor_components`) so F1 can be recomputed with `answer_modifiers` at request time; a helper for that would be useful. | open |
| 14 | A | B | The analysis API is committed (`93ebc1a`): `POST/GET /v1/analyses`, `/recommendations` (`?format=geojson`), `/zones/{rank}`, `/cells` (every scored cell with rank and score, for your heat map), `/compare`, `/what-if`, `GET /v1/categories` (tiers with labels and wizard questions) and `GET /v1/cities` now returns `{"cities": [...]}`. `GET /v1/analyses/{id}` returns status and, once done, the recommendations too. Create returns 202. Please build the wizard and Results tabs against these; shapes are in `backend/app/schemas/`. Notes for your library: (1) `ScoreEngine` keeps F8 at a neutral 0.5 when there is no rent data, but the approved D-22b says to drop F8 and rescale the other weights; please implement that. (2) The real cafe/mid ranking is Officers Colony 82.6, Corporation Quarters 82.0, SBI Colony 81.8: still tightly clustered (see row 13). (3) Analyses are not saved until the owner approves runtime writes, so end-to-end runs against the real database wait for that approval; the endpoints work today in tests. | open |
| 6 | A | B | Resolved: the owner says the two blank lines in `architecture-1.md` were their own accidental edit and asked to keep it, so B does not need to confirm anything. Still do not edit that file. One process note: when either of us runs `git commit`, pre-commit briefly stashes and restores the *other* agent's modified tracked files (a few seconds). Do not write files during a commit; if an edit fails around a commit, retry it. Stage only your own paths. | done |
| 15 | A | B | Rows 13 and 14 are resolved on my side: zone merging/naming (3.7.5) and narratives now run for real (`zone_names`, `make_narrative` in `backend/app/services/analysis_service.py`), and the score-clustering observation still holds (Officers Colony 82.6, Corporation Quarters 82.0, SBI Colony 81.8 for cafe/mid) but is no longer blocking — treat it as a tuning item for Phase 7, not a defect. The `sitescout-scoring` Nasiko agent is now deployed and live (`agents/scoring/`, wraps the same `score_zones` the backend uses locally) and the backend calls it for real when `USE_NASIKO_AGENTS=true` (falls back to local scoring automatically if the agent is down); verified end to end against the real database. `scripts/agent_packaging.py` gained a `data=` parameter (verbatim, non-`.py` files, e.g. category YAMLs) alongside the existing `shared=` (code-only) parameter — use `--data name=path` on `deploy_agent` for any agent that needs config files, not `--include`. | done |

---

## 2. Decision log (G-DECIDE)

Nothing is assumed. Status: `answered` (the owner decided), `proposed` (my suggestion, waiting for the owner's confirmation), `open` (needs the owner's answer), `deferred`, `closed` (no longer applicable).

| ID | Question | Needed by | Status | Answer / date |
|---|---|---|---|---|
| D-01 | Hackathon rules: is pre-building allowed, is the theme fixed, what counts as "using" Nasiko? | 0.1.1 | partly answered | Owner, 2026-09-20: Nasiko is compulsory; Anakin and DronaHQ are not. Pre-building and theme still open. |
| D-02 | Which city is the demo city (Pune is only an example in the architecture)? | 0.1.2 | answered | Owner, 2026-09-20: Bengaluru first; Mumbai is cut from the MVP (see the cuts below). Bengaluru's OSM coverage is confirmed by the full download and the data is loaded. |
| D-03 | Which LLM route and models? | 0.1.4, 0.3.6 | partly answered | Owner, 2026-09-20: Ollama as primary if possible, OpenRouter free as backup. Owner then said any Antraa or fairsynth model was fine. Finding: every `Antraa-*` and `fairsynth-*` model carries an unrelated baked-in system prompt and dataset (8,177 prompt tokens per request, which fills the 8,192 context), so I chose the clean `qwen2.5:7b-instruct` instead (7.6B, tool support, 59 prompt tokens, valid JSON, 10.1 s including load), plus `nomic-embed-text` for embeddings. **Owner to confirm this substitution.** Set in Nasiko's `.env`: `OPENAI_MODEL`, `ROUTER_MODEL`, `EMBEDDING_MODEL`. Still open: whether Nasiko can really use Ollama (its LLM Router natively supports openai, anthropic, gemini and openrouter only; **verified 2026-09-20:** the route works when `OPENAI_API_BASE` (the router's setting) and `OPENAI_BASE_URL` (the routing engine's setting) both point at Ollama's OpenAI-compatible endpoint; a deployed agent answered through the proxy in 9.8 s and the routing engine dispatched in 6.8 s) and the OpenRouter backup model. Machine: 23.7 GB RAM, RTX 3050 6 GB. |
| D-04 | Does the `orchestrator` live as a Nasiko agent or inside the backend? | 5.3.4 | answered | Owner, 2026-09-20: the orchestrator lives inside the backend, which calls each Nasiko agent in turn. |
| D-05 | Database | 1.1.1 | answered | Owner, 2026-09-20: PostgreSQL + PostGIS in Docker. The separate test database is approved later at 4.9.1. |
| D-06 | Population source: WorldPop or Census ward data (both free)? | 1.5.3 | answered | Owner, 2026-09-20: use OSM residential-building density plus land-use shares for F3 now; `cell_attributes.population_est` stays NULL until a population source is added later (no schema change needed). |
| D-07 | Competitor price level and popularity data | 3.4.1, 7.3.1 | proposed | Proposed: Google Places is dropped (paid). The Spearman correlation only runs if the owner supplies popularity data. |
| D-08 | Which geocoder: Nominatim or Photon (only for CSV rows lacking coordinates)? | 2.2.1 | proposed | Proposed: Nominatim. |
| D-09 | Routing engine for isochrones | 3.6.3 | deferred | Isochrones are proposed out of the MVP (see D-18). |
| D-10 | PDF export approach | 4.6.4 | closed | Owner cut PDF export from the MVP on 2026-09-20; nothing to decide. |
| D-11 | Interface replacing DronaHQ | 6.1 | answered | Owner, 2026-09-20: Streamlit. |
| D-12 | Public access | 6.5.3 | proposed | Proposed: local only; a free Cloudflare Tunnel to Streamlit only if remote access is needed. |
| D-13 | Which property portals are scraped? | none | closed | No scraping in the MVP (rent data comes from an optional CSV). |
| D-14 | Build order for the categories. | 0.1.3 | partly answered | Owner, 2026-09-20: all three (cafe, clothing store, pharmacy) are in the MVP. Still open: which one is built end to end first (the architecture suggests one first, then the other two by configuration). |
| D-15 | Repo root for the code, and whether to run `git init` in `D:\Projects\Nasiko_Buildathon`. | 0.6.1, 0.6.5 | answered | Owner, 2026-09-20: this folder is the repo root, with a local `git init` (no remote, nothing pushed). |
| D-16 | The rules list skips numbers 5 and 6. Were two rules dropped? If so, what are they? | Phase 0 start | closed | Owner, 2026-09-20: nothing was dropped; the rules list is complete as written (numbered 1, 2, 3, 4, 7, 8). |
| D-17 | Content of `brands_premium.yaml`: provided by the owner, or drafted for approval? | 1.2.3 | partly answered | Owner, 2026-09-20: Agent B drafts brand lists per category and tier for Bengaluru, and the owner approves the file before it is used. Until then `config/brands_premium.yaml` is a 4-brand placeholder. |
| D-18 | Optional accuracy boosters in scope: parking (#9), late-night (#15), seasonality (#14), growth (#11)? Isochrones (#4) are proposed out. The architecture recommends 1, 2, 3, 5, 7, 8, 12, 13, 16, 17. | 3.6.3 | answered | Owner, 2026-09-20: no optional boosters in the MVP (parking, late-night activity, seasonality and isochrones are out); the three in D-19 are shown as information only. |
| D-19 | Boosters #7 (day-part), #16 (age skew), #17 (medical density) are not among F1–F9. Do they modify an existing feature, become extra weighted features, or appear only as explanatory info? Any option changes the weight tables (G-DEVIATE). | 3.6.1 | answered | Owner, 2026-09-20: "show three as info only": day-part profile, age-skew proxy and medical ecosystem density appear as explanatory facts in the zone detail and do not change the score, so the weight tables stay unchanged. |
| D-20 | Rent and property-price data source | 2.1 | answered | Owner, 2026-09-20: OSM-only core plus an optional CSV the owner provides for the demo city. |
| D-21 | Growth signal (F9) and `market-intel` without Anakin | 2.4, 5.2.3 | proposed | Proposed: OSM `construction` and `proposed` tags plus a curated notes file, summarised locally; no live web search. |
| D-22 | Model adjustments when rent and price data are absent (G-DEVIATE): (a) affluence weights, since two of four terms depend on prices; (b) F8 rent efficiency fallback; (c) confidence weights for listing and price coverage; (d) how the rent hard filter behaves. | 1.2.2, 3.3.2, 3.4.4, 3.7.3 | answered | Owner, 2026-09-20: asked whether Anakin could supply rent data, said it is optional, credits are limited, and to decide myself: "if it is not a hassle, easy and fast, finish and integrate, or move on with your proposal as I have a very tight deadline". **Decision: Anakin is NOT integrated now** (needs a key, a terms-of-service review of the property portals, and a full extract, geocode and clean pipeline; about 300 free credits could cover only a few dozen pages against 1,000+ Bengaluru localities). **My proposal is adopted:** (a) affluence = 2/3 premium-POI density + 1/3 apartment share when there is no price data; (b) F8 is dropped when there is no rent data and the other weights are rescaled to sum to 1.0; (c) confidence = 2/3 POI coverage + 1/3 recency with a visible "rent data not available" note; (d) the rent filter runs only where rent data exists. With a rent CSV (from any source, including Anakin later) the original architecture formulas apply. |
| D-23 | Users and roles in the Streamlit MVP: none (single local user), or a simple password for admin pages? | 6.1.3 | answered | Owner, 2026-09-20: one local user, no login; admin pages are not password protected (local demo only). |
| D-24 | Schema and repo-layout simplifications (G-DEVIATE): rename or drop the Anakin-specific parts of `scrape_jobs`; use `frontend/streamlit_app/` instead of `dronahq/` and `frontend/map_embed/`. | 0.6.1, 1.1.3 | answered | Owner, 2026-09-20: approved the folder layout with a new top-level `shared/` package (streamlit follows from D-11), and the schema deviations D1–D5 together with migration 0001 (`ingest_jobs` instead of `scrape_jobs`, new `cell_attributes`, `cell_features.category`, `cities.key`, CHECK constraints). |
| D-25 | Adapt §9.3, §13 and parts of §14 and §19 to the installed Nasiko (A2A v1.0 agents, port 8080, LLM Router, routing engine). `architecture-1.md` itself is not edited. | Phase 5 | proposed | Forced by the read-only review in `plan.md` §2.4. |
| D-26 | Nasiko keys and CLI: which keys go in (free providers only), who edits (G-EDIT); create `D:\Projects\Nasiko\.env` from `.env.example` (the installed version does not read the old `.nasiko-local.env`); whether to install Rust 1.85+ to build the `nasiko` CLI, or use the dashboard. | 0.3.2, 0.3.4 | partly answered | Owner, 2026-09-20: "create it yourself" (done: `.env` created), "dashboard is fine for now" (CLI stays optional). Still open: a real free OpenRouter key (the old file only held a placeholder), and Rust only if the CLI is wanted later. |
| D-27 | Python version for our code | 0.2.2 | answered | Owner, 2026-09-20: whichever is quick to use, so the installed 3.11.9 is used (no install). `uv` is optional. |
| D-28 | Tier labels: the owner asked for "niche, medium class and lower class". Proposed mapping to the architecture's ids: lower class → `budget`, medium class → `mid`, niche → `premium`. Does "niche" mean the premium/specialty end? | 1.2.2, 6.2.2 | answered | Owner, 2026-09-20: yes, niche means premium. Mapping: lower class → `budget`, medium class → `mid`, niche → `premium`. |
| D-29 | Bengaluru is large (roughly 700 km², about 7,000 cells). Start with tiled Overpass requests and fall back to a free Karnataka extract from Geofabrik if the public server is too slow? | 1.4.1 | proposed | Evidence from the 2026-09-20 check: counting features over a Bengaluru bounding box took 22 to 32 s per heavy tag, and three quick follow-up queries were rejected with HTTP 429. Tiling with slow pacing, or the extract, will be needed. Update: tiled, paced downloading with automatic tile splitting is built and running; the extract has not been needed so far. |
| D-30 | Implementation choices I made for cell attributes; please review (all are easy to change): (a) a cell's `land_use` comes from land-use polygon shares (at least 0.25) or POI counts (at least 3 commercial POIs, or at least 3 residential buildings); both give `mixed`, neither gives `other`; (b) locality names come from the nearest OSM place point (suburb, neighbourhood, quarter) within 3 km, because most Bengaluru localities are mapped as points rather than polygons; (c) POIs just outside the boundary but inside the 1.5 km fetch buffer are kept with `h3_index` NULL, so edge cells still see nearby landmarks. | 1.3.3, 1.5.1 | answered | Owner, 2026-09-20: keep the defaults (land share of at least 25% or 3+ commercial POIs or residential buildings; localities from the nearest place point within 3 km). |
| D-31 | How the backend logs in to Nasiko: the client uses a username and password. Proposed: a dedicated service user with the least rights Nasiko allows, instead of the admin account whose password is in Nasiko's `.env`. For local development the admin login is used. | 5.6.1 | proposed | |
| D-32 | Heuristics I chose inside the feature build (all constants in `pipelines/build_features.py`, easy to change; review when convenient): (a) F3 residential demand = 0.6 x percentile of residential buildings in the catchment + 0.4 x percentile of the residential land-use share around the cell; (b) POI coverage: a cell zoned commercial or retail (25%+ of its area) is expected to have at least the 25th-percentile POI count within 500 m, otherwise its coverage drops; every other cell counts as fully covered; (c) road class scores: trunk and primary 1.0, secondary 0.7, none 0.3; transit, parking and coverage use a 500 m walking radius; (d) premium POIs = brands on the premium list, car showrooms and 4-5 star hotels; (e) a competitor's tier = the brand list, else the affluence of the cell it sits in, using the midpoints of the tier targets as cut-offs; (f) growth (F9) is neutral 0.5 and flagged as estimated until growth data exists; (g) confidence without rent data = 2/3 POI coverage + 1/3 recency (D-22c). | 3.8 | proposed | |

---

## 3. Approval log

Record every approval the owner gives for gated actions.

| Date | Gate | What was approved | Reference step |
|---|---|---|---|
| 2026-09-20 | G-DECIDE | Anakin and DronaHQ optional, Nasiko compulsory, MVP must be free | D-01 |
| 2026-09-20 | G-DECIDE | Streamlit as interface | D-11 |
| 2026-09-20 | G-DECIDE | OSM-only core plus optional CSV for rent data | D-20 |
| 2026-09-20 | G-DECIDE | Ollama primary if possible, OpenRouter free as backup | D-03 |
| 2026-09-20 | G-DECIDE | PostgreSQL + PostGIS in Docker | D-05 |
| 2026-09-20 | G-DECIDE | Nasiko already installed at `D:\Projects\Nasiko`; the `nasiko` CLI may be used | D-26 |
| 2026-09-20 | G-EDIT | Rewrite `plan.md` and `progress.md` for the free MVP ("start editing the idea") | Change log |
| 2026-09-20 | G-EDIT | Create `D:\Projects\Nasiko\.env` myself ("create it yourself") | 0.3.2 |
| 2026-09-20 | G-DECIDE | Use the Nasiko dashboard for now; CLI optional | 0.3.4 |
| 2026-09-20 | G-DECIDE | Use the installed Python 3.11.9 ("whichever is quick to use") | D-27 |
| 2026-09-20 | G-DECIDE | Cities: Bengaluru first, Mumbai if time remains | D-02 |
| 2026-09-20 | G-DECIDE | All three categories in the MVP with three tiers (lower class, medium class, niche) | D-14, D-28 |
| 2026-09-20 | acknowledged, **not** approval | "ok" to the note that no-rent-data formulas need changes; concrete proposal still awaits approval | D-22 |
| 2026-09-20 | G-DECIDE | D-22 deferred: "start with other building we will come back to this" | D-22 |
| 2026-09-20 | G-DECIDE | "Niche" means premium | D-28 |
| 2026-09-20 | G-DECIDE | Start Docker Desktop and the Nasiko stack ("yes") | 0.3.3 |
| 2026-09-20 | G-DECIDE | Any Antraa or fairsynth Ollama model is fine; I used `qwen2.5:7b-instruct` instead and told the owner why (to confirm) | D-03 |
| 2026-09-20 | G-DECIDE | This folder is the repo root; local `git init` (no remote) | D-15, 0.6.5 |
| 2026-09-20 | G-DECIDE | Second Claude runs on the same computer and folder; work split in `plan.md` §9 | §9 |
| 2026-09-20 | G-DEVIATE | Add a top-level `shared/` package to the layout | D-24 |
| 2026-09-20 | G-DB | Start the new empty PostGIS container and apply migration 0001 as written ("Approve container + migration as written") | 1.1.1, 1.1.4 |
| 2026-09-20 | G-DEVIATE | Schema deviations D1–D5 from the architecture DDL (cities.key, ingest_jobs instead of scrape_jobs, new cell_attributes, cell_features.category, CHECK constraints), approved together with the migration | D-24 |
| 2026-09-20 | G-DECIDE | Use OSM residential-building density plus land-use shares for F3 now; population stays NULL until later | D-06 |
| 2026-09-20 | G-DECIDE | Keep the two leading blank lines in `architecture-1.md`: the owner made that edit by mistake and asked to keep it; committed as the owner's own change | rule 1 |
| 2026-09-20 | G-DB | Load the Bengaluru dataset (1 city, 6,631 cells, 6,631 cell attributes, 41,469 POIs, 1 ingest job) in one transaction (owner: "Approve the load") | 1.3.1, 1.3.4, 1.4.5 |
| 2026-09-20 | G-DB | Store the computed features (19,893 `cell_features` rows) and mark Bengaluru `ready` (owner: "Approve storing features and marking Bengaluru ready") | 3.8.1 |
| 2026-09-20 | G-DB | Runtime app writes: the backend may insert and update rows in `users`, `analyses` and `recommendations` when an analysis is created and run (no schema change, no other tables; every read endpoint uses a READ ONLY session). Owner: "Approve (Recommended)". | 4.5.1 |
| 2026-09-20 | G-DEVIATE | Adopt the no-rent-data formulas (D-22) as proposed; Anakin not integrated (decision delegated to Agent A: "take the decision") | D-22 |
| 2026-09-20 | G-DECIDE | Boosters: none scored; day-part, age skew and medical density shown as information only | D-18, D-19 |
| 2026-09-20 | G-DECIDE | Orchestrator inside the backend | D-04 |
| 2026-09-20 | G-DECIDE | Streamlit: one local user, no login | D-23 |
| 2026-09-20 | G-DECIDE | Cut from the MVP: PDF export and Mumbai. Kept: growth signal (F9) and the compare-zones screen | plan §6 |
| 2026-09-20 | G-DECIDE | Keep the land-use and locality defaults | D-30 |
| 2026-09-20 | G-DECIDE | Rules 5 and 6: nothing was dropped | D-16 |
| 2026-09-20 | G-DECIDE | Brand list: Agent B drafts, owner approves before use | D-17 |

## 4. Database change log (G-DB)

Every database action, with the approval reference. **No entries means the database has not been touched** (this includes Nasiko's own databases).

| Date | Action | SQL / migration id | Approved on | Applied |
|---|---|---|---|---|
| 2026-09-20 | Started a NEW, empty PostGIS container `sitescout-db` (`postgis/postgis:16-3.4`, bound to `127.0.0.1:5433`, volume `sitescout_pgdata`) with `docker compose up -d db`. Nasiko's own databases were not touched. | `docker-compose.yml` | 2026-09-20 (owner: "Approve container + migration as written") | yes; healthy in about 9 s |
| 2026-09-20 | Applied migration `0001_initial`: 13 SiteScout tables plus `alembic_version`, including the deviations D1–D5 listed at the top of the SQL file. | `backend/app/db/migrations/sql/0001_initial_upgrade.sql` | 2026-09-20 (same approval) | yes; verified read-only: 13 tables, PostGIS 3.4, SRID 4326 geometry columns, 26 CHECK constraints, 14 foreign keys, 30 indexes, all tables empty |
| 2026-09-20 | Loaded the Bengaluru OSM dataset with `python -m pipelines.ingest_city load --write` (one transaction, upserts on natural keys): 1 city (status `ingesting`), 6,631 cells, 6,631 `cell_attributes`, 41,469 POIs, 1 `ingest_jobs` row. Nasiko's databases untouched. | `pipelines/db_load.py`, data in `data/raw/osm/bengaluru/latest/` | 2026-09-20 (owner: "Approve the load") | yes; verified read-only: counts match exactly, 0 invalid geometries, SRID 4326, 0 orphaned foreign keys, 3,155 buffer-zone POIs with NULL cell. A second run of the same load inside a transaction that was rolled back gave identical counts (idempotent) and persisted nothing |
| 2026-09-20 | Stored the computed features with `python -m pipelines.run_features --write` (one transaction, upserts): 19,893 rows in `cell_features` (cafe, clothing and pharmacy x 6,631 cells; each row holds all three tiers and the per-category anchor sums) and set the Bengaluru city status to `ready`. No other table was touched. | `pipelines/features_store.py` | 2026-09-20 (owner: "Approve storing features and marking Bengaluru ready") | yes; verified read-only: 6,631 rows per category, table 27 MB, city `ready`, `GET /v1/cities` lists Bengaluru, and loading plus ranking one category and tier from the database takes about 0.6 s |
| 2026-09-20 | Enabled runtime writes from the backend to `users`, `analyses`, `recommendations` (see the approval log); verified by one real end-to-end analysis, recorded below. | `backend/app/db/analysis_store.py` | 2026-09-20 | yes: one real run (cafe, mid, Bengaluru) created 1 user, 1 analysis (`an_de07ae37`) and 5 recommendations; compare, what-if, GeoJSON and history checked over HTTP |

## 5. Commit log (local only; nothing has been pushed)

| Date | Commit | Summary | Pushed |
|---|---|---|---|
| | | *(no repository yet)* | no |

## 6. Blockers

| Date | Blocker | Step | Waiting on |
|---|---|---|---|
| 2026-09-20 | No usable free LLM key yet: the OpenRouter key in the old env file is a placeholder, and the Ollama route through Nasiko is unverified | 0.3.6 | Owner: a real free OpenRouter key (optional) and the Ollama model id (D-03) |

---

## Phase 0: Setup, verification and decisions

**Status:** in progress (read-only checks only)

### Part 0.1: Decisions and hackathon rules

**0.1.1 Confirm remaining hackathon rules**
- [x] Owner confirmed Anakin and DronaHQ are optional and Nasiko is compulsory (D-01, partly)
- [ ] Ask whether pre-building is allowed
- [ ] Ask whether the theme is fixed and what counts as "using" Nasiko
- [ ] Record the answers in the Decision Log

**0.1.2 Choose the demo city**
- [x] Owner chose Bengaluru first, Mumbai only if time remains (D-02)
- [x] Spot-check Bengaluru's OSM coverage (markets, colleges, hospitals present) - confirmed by the full download: 64 marketplaces, 593 colleges, 1,125 hospitals, 3,060 offices
- [ ] Owner confirms Bengaluru after the spot-check

**0.1.3 Choose the first category**
- [ ] Owner picks cafe or clothing (D-14)
- [ ] Record the reason in the Decision Log

**0.1.4 Choose LLM models**
- [x] Owner chose the route: Ollama primary if possible, OpenRouter free backup (D-03)
- [x] Record machine capacity (23.7 GB RAM, RTX 3050 6 GB) and that Ollama already holds local models
- [ ] Owner picks the Ollama model id(s)
- [ ] Owner picks the OpenRouter free model id(s)

**0.1.5 Resolve remaining open decisions**
- [ ] Walk through every `open` and `proposed` item in the Decision Log with the owner
- [ ] Mark each as answered or deferred with a date

**0.1.6 Buyer conversations**
- [ ] Conversation with one aspiring store owner
- [ ] Conversation with one broker or franchise person
- [ ] Summarise what they said in a short note

### Part 0.2: Accounts, keys and tooling

**0.2.1 OpenRouter backup key**
- [ ] Owner gets a real free OpenRouter key (the one in the old env file is only a placeholder) 🔒
- [ ] Confirm the backup model is free

**0.2.2 Toolchain**
- [x] Docker and Compose installed (Docker 29.7.2, Compose v5.5.0)
- [x] Docker Desktop engine running
- [x] git installed (2.49.0)
- [x] Ollama installed (0.34.2)
- [x] Python: owner chose to use the installed 3.11.9 (D-27)
- [x] Project virtual environment with pip: `.venv` (Python 3.11.9), dev dependencies installed and locked in `requirements/lock-dev.txt` (`uv` is optional)
- [ ] Rust 1.85+ only if the `nasiko` CLI is built from source later (D-26) 🔒

**0.2.3 Secret handling**
- [ ] `.env` convention agreed (local only)
- [ ] `.gitignore` covers `.env`, `data/raw`, caches
- [ ] Rule agreed: secret values are never printed or logged

### Part 0.3: Nasiko feasibility (compulsory platform)

**0.3.1 Review the installed Nasiko (read-only)**
- [x] Locate the install at `D:\Projects\Nasiko` and record branch and commit (`main`, `58cfe60`)
- [x] Read the README, LLM Router, env template and A2A docs
- [x] Compare with §13 and record the differences in `plan.md` §2.4
- [x] Check the state of the existing env file without printing secret values

**0.3.2 Create the Nasiko `.env`** 🔒 G-EDIT
- [x] Owner approved: "create it yourself" (D-26)
- [x] Create `.env` from `.env.example` in `D:\Projects\Nasiko` (new file; nothing existing edited)
- [x] Generate and set the required secrets (encryption key, JWT secret, agent JWT secret, admin password)
- [x] Point the LLM settings at Ollama; the paid OpenAI key was not copied
- [x] Confirm `.env` is git-ignored and `docker compose config` reports no errors
- [x] Set `OPENAI_MODEL`, `ROUTER_MODEL` and `EMBEDDING_MODEL` to the chosen Ollama models (D-03)
- [x] Add `OPENAI_API_BASE`, `DEFAULT_PROVIDER` and `DEFAULT_MODEL`: the LLM Router (agents' calls) reads those, not `OPENAI_BASE_URL`, and would otherwise keep calling `api.openai.com`; server container recreated and healthy
- [ ] Owner supplies a real free OpenRouter key for the backup route (the old file only held a placeholder) 🔒

**0.3.3 Start Nasiko**
- [x] Start the Docker Desktop engine
- [x] `docker compose up -d --build` in `D:\Projects\Nasiko`
- [x] Containers healthy (7 running; postgres and redis report healthy)
- [x] `http://localhost:8080` responds (health returns 200; the dashboard redirects to its login page)
- [x] Admin login works (API login returns a token for the superuser and an authenticated `GET /api/agents` succeeds; the dashboard page itself was not opened in a browser)

**0.3.4 Deploy through the dashboard (CLI optional)**
- [x] Owner chose the dashboard for now; the CLI stays optional (D-26)
- [x] Dashboard upload flow for an agent reviewed (used the same `POST /api/agents/upload` call the dashboard makes; the server builds the image, about 30 s)
- [ ] Only if the CLI is wanted later: install Rust 1.85+ and `cargo install --path cli/` 🔒
- [ ] Only if the CLI is wanted later: `nasiko connect http://localhost:8080` and `nasiko auth login`

**0.3.5 Hello-world agent**
- [x] Start from a template in `D:\Projects\Nasiko\agents\` (or `nasiko new` if the CLI is installed) (wrote `agents/hello_world/` on the template's pattern)
- [x] Upload it through the dashboard (through the dashboard's upload API; agent is running)
- [x] Chat with it in the dashboard and get an answer (through the A2A proxy; completed in 9.8 s with a sensible answer)
- [x] Inspect the A2A Agent Card (the registry stores it and auto-generated the capability description)
- [x] Scripted `SendMessage` call through Nasiko's proxy (`POST /api/agents/{id}` with header `A2A-Version: 1.0`)

**0.3.6 LLM route**
- [x] Confirmed from the source that an LLM config only validates the provider name (openai, anthropic, gemini, openrouter) and accepts any model string, so `openai` with `qwen2.5:7b-instruct` is allowed
- [ ] `nasiko llm-config providers` reviewed (needs the CLI, or the equivalent API call)
- [ ] OpenRouter free-model config created and attached to the hello-world agent
- [x] Agent LLM call works through the LLM Router (the agent answered through the router to local Ollama)
- [x] Ollama tested through an OpenAI-compatible base URL (works via `OPENAI_API_BASE`; see the note added to D-03)
- [x] Result recorded in D-03

**0.3.7 Routing engine**
- [x] Note the chat model and embedding model the routing engine needs (`ROUTER_MODEL` and `EMBEDDING_MODEL`, set to `qwen2.5:7b-instruct` and `nomic-embed-text`)
- [x] Confirm a free option works for each (routing dispatch through `POST /api/orchestrator/a2a` worked in 6.8 s)
- [~] Try sample routing queries and note quality (only one agent is registered so far, so selection quality is untested)

**0.3.8 Backend to Nasiko**
- [~] How our backend authenticates to Nasiko (login returns a bearer token for the user; a service account for the backend is still to decide)
- [ ] Access-control and flow-guard defaults noted
- [x] How new agents appear in the routing engine (immediately after deploy, no restart needed)

**0.3.9 Record findings**
- [ ] Windows and Docker networking notes
- [ ] Decision Log updated

### Part 0.4: Free LLM feasibility

**0.4.1 Local models**
- [x] Confirm Ollama installed and list the existing local models
- [x] Pick `qwen2.5:7b-instruct` after finding that the Antraa and fairsynth models carry baked-in prompts (D-03)
- [x] Measure latency (10.1 s including model load, 59 prompt tokens)
- [ ] Measure RAM and VRAM use

**0.4.2 Structured output**
- [x] Test tier classification as strict JSON (one sample gave valid JSON and a sensible tier; a larger sample is still needed)
- [ ] Test narrative-from-JSON

**0.4.3 Container reach**
- [x] A container reaches Ollama on the host: a throwaway container gets HTTP 200 from `host.docker.internal:11434` even though Ollama listens only on 127.0.0.1
- [x] Repeat the check from a real agent container on the Nasiko network (needs the hello-world agent) (the agent reached Ollama through the router)

**0.4.4 OpenRouter backup**
- [ ] Test the free model
- [ ] Note rate limits and availability

**0.4.5 Decide models**
- [ ] Primary and backup ids recorded in the Decision Log

### Part 0.5: Free data and UI feasibility

**0.5.1 Overpass**
- [x] Overpass responds for Bengaluru
- [x] Spot-check coverage: counts over an approximate Greater Bengaluru bounding box are cafes 1,154, restaurants 3,276, marketplaces 63, colleges 576, universities 38, hospitals 1,113, clinics 1,017, schools 1,675, offices 3,183, bus stops 3,311 and apartment buildings 8,984 (plausible; not yet compared with places the owner knows)
- [x] Retry the pharmacy, clothes-shop and mall counts (they were rejected with HTTP 429; pace requests slower) - superseded by the full download: 998 pharmacies, 1,488 clothes shops, 77 malls

**0.5.2 Population source**
- [ ] Dataset downloadable for the city

**0.5.3 Geocoder terms**
- [ ] Nominatim or Photon terms allow our low-volume use

**0.5.4 Streamlit map spike**
- [x] Hello page draws H3 hexagons coloured by a dummy score
- [x] Click on a hexagon is captured
- [x] Library chosen (folium or pydeck)

**0.5.5 Free-stack inventory**
- [ ] List every dependency, image, model and service with licence and cost
- [ ] Confirm none is paid

### Part 0.6: Repository scaffolding and engineering standards

**0.6.1 Repo layout**
- [x] Owner confirms repo root (D-15) 🔒
- [x] Owner approves layout deviations (D-24: `shared/` package; Streamlit folder) 🔒
- [x] Create folders from §17 as adapted (empty packages)

**0.6.2 Tooling configuration**
- [x] ruff configured (Markdown excluded so no tool can rewrite `architecture-1.md`)
- [x] mypy configured (strict; verified on the empty scaffold)
- [x] pytest configured (network and database tests behind an `integration` marker)
- [x] pre-commit configured and installed as a git hook (`architecture-1.md` excluded from every hook)

**0.6.3 Environment files**
- [x] `.env.example` (no Anakin variables; Nasiko base URL `http://localhost:8080`; database on host port 5433)
- [x] `.gitignore`

**0.6.4 Conventions**
- [ ] Logging field names documented
- [ ] Error envelope documented
- [ ] Module boundaries documented

**0.6.5 Git**
- [x] Owner decides on `git init` 🔒 (approved: local only)
- [x] First local commit (no push)

**0.6.6 Phase-0 report**
- [ ] Go/no-go report written
- [ ] Decision Log updated
- [ ] Phase 0 exit criteria met

---

## Phase 1: Data foundation

**Status:** not started

### Part 1.1: Database schema and migrations

**1.1.1 Provision PostGIS** 🔒 G-DB
- [x] Check port conflicts with Nasiko's own Postgres (Nasiko publishes host port 5432 and Redis 6379, so SiteScout's database will use 5433)
- [x] Compose service for `postgis/postgis:16-3.4` (`docker-compose.yml`, localhost:5433 only)
- [x] Owner approves starting it
- [x] Container healthy

**1.1.2 Alembic setup**
- [x] Alembic initialised (URL from `DATABASE_URL` only; offline SQL rendering works)
- [x] SQLAlchemy base and naming conventions

**1.1.3 Initial migration written** 🔒 G-DB
- [x] Translate §8.2 DDL into a migration (extension, tables, indexes)
- [x] Show the proposed Anakin-related simplifications (D-24)
- [x] Show the SQL to the owner
- [x] Owner approves or requests changes (approved as written)

**1.1.4 Apply migration** 🔒 G-DB
- [x] Owner approves applying
- [x] Apply
- [x] Verify tables, indexes and PostGIS
- [x] Record in the Database change log

**1.1.5 Models and repositories**
- [x] SQLAlchemy models for every table (a test fails if models and SQL drift apart)
- [ ] Repository classes with typed methods

**1.1.6 Upsert helpers**
- [ ] Upsert on `osm_type+osm_id` for POIs
- [ ] Upsert on `h3_index` for cells
- [ ] Upsert for listings
- [ ] Unit tests for each

### Part 1.2: Configuration layer

**1.2.1 OSM tag config**
- [x] `config/osm_tags.yaml` matches Appendix A (plus road and place kinds for attributes)

**1.2.2 Category configs**
- [x] `cafe.yaml`
- [x] `clothing.yaml`
- [x] `pharmacy.yaml`
- [x] Values match §5.3, §5.6 and Appendix B until D-22 is decided
- [x] Tier labels lower class, medium class and niche mapped to `budget`, `mid`, `premium` (D-28) 🔒

**1.2.3 Premium brands** 🔒
- [ ] Owner answers D-17
- [ ] `config/brands_premium.yaml` written and approved

**1.2.4 Loader and validator**
- [x] Pydantic config models
- [x] Validate weights sum to 1.0
- [x] Validate tier targets and known feature keys
- [x] Unit tests including a failing config

**1.2.5 Config sync** 🔒 G-DB
- [ ] Sync command writes to `category_configs`
- [ ] Owner approves the write
- [ ] Record in the Database change log

### Part 1.3: City and H3 grid

**1.3.1 City record and boundary**
- [x] Obtain the city boundary polygon (OSM relation 7902476, 719 km²; saved in `config/cities/`)
- [x] Compute bbox
- [x] Owner approves the city insert 🔒 G-DB - approved and loaded

**1.3.2 Generate cells**
- [x] Polyfill H3 res 9 over the boundary (6,631 cells)
- [x] Verify cell count is plausible for the city area (0.108 km² per cell)

**1.3.3 Locality names**
- [x] Fetch OSM place data (mostly points rather than polygons, see D-30; download running) - done: 1,251 place elements
- [x] Assign `locality_name` to each cell (code and tests done; real run waits for the download) - real run: 6,630 of 6,631 cells named, 1,024 distinct localities
- [x] Report cells with no locality (part of the QA report) - one cell has none

**1.3.4 Persist cells** 🔒 G-DB
- [x] Store centroid and boundary - 6,631 cells loaded
- [x] Owner approves the write
- [x] Record in the Database change log

### Part 1.4: OSM POI ingestion

**1.4.1 Overpass client**
- [x] Fetch by bounding-box tiles (Bengaluru is large; a failing tile splits into four)
- [ ] Fall back to a free Karnataka extract if the public server is too slow (D-29) 🔒
- [x] Timeout and retry
- [x] Response caching
- [x] Rate-limit respect
- [x] Tests with fixtures

**1.4.2 Query builder**
- [x] Group tags per call from `osm_tags.yaml`
- [x] Nodes and ways with `out center tags`
- [x] Unit tests on generated queries

**1.4.3 Normalisation**
- [x] Map OSM tags to internal categories
- [x] Handle way centres
- [x] Hotel star handling (the `stars` tag is kept for the scoring library)
- [x] Unit tests

**1.4.4 POI to cell assignment**
- [x] Compute H3 index per POI
- [x] POIs outside the city cells keep `h3_index` NULL instead of being dropped (D-30c)

**1.4.5 Persist POIs** 🔒 G-DB
- [x] Upsert with natural keys (loader written and tested with a fake connection; `load` is a dry run unless `--write`)
- [x] Owner approves the write
- [x] Record in the Database change log

**1.4.6 Coverage check**
- [ ] Per-area POI density check
- [ ] Flag implausibly low density areas
- [ ] Output feeds `poi_coverage`

### Part 1.5: Land use, buildings, population and roads

**1.5.1 Land use**
- [x] Fetch OSM landuse polygons (download running) - done: 12,144 elements
- [x] Classify each cell (residential, commercial, mixed, other): code and tests done, rule in D-30 - real run: 1,512 residential, 686 commercial, 594 mixed, 3,839 other

**1.5.2 Residential density**
- [x] Count residential buildings per cell (stored as `residential_building` POIs; counts feed the land-use class) - 11,947 residential-building POIs downloaded
- [ ] Compute apartment share (from the POIs' `building` tag in the feature stage)

**1.5.3 Population** 🔒 G-DECIDE
- [x] Owner answers D-06: OSM building density and land-use shares are used for the MVP; no population download is needed and `population_est` stays NULL

**1.5.4 Road and transit attributes**
- [x] Road class and main-road distance (code and tests done; needs the roads download) - real run: all 6,631 cells have a main road
- [x] Transit stops within walking distance (bus stops and stations are downloaded as POIs) - 3,427 bus stops and 148 stations downloaded
- [x] Parking presence (parking is downloaded as POIs) - 1,466 parking POIs downloaded

### Part 1.6: Geo-data pipeline and QA

**1.6.1 Ingestion pipeline**
- [x] `pipelines/ingest_city.py` runs steps 1–3 of §4.4 (`fetch`, `grid`, `build`, `load` exist; the full real run waits for the download) - verified on the full real download
- [x] Clear logging and exit codes
- [x] Dry-run mode that writes nothing (`load` without `--write`)

**1.6.2 Idempotency**
- [x] Two runs give identical counts (checked in a rolled-back transaction: identical counts, nothing persisted)
- [ ] Test added (needs the test database from 4.9.1; the check ran as a one-off script)

**1.6.3 QA report**
- [x] Counts per category and per cell (QA report written to `data/raw/osm/<city>/qa_report.json`; real run pending) - real QA report produced
- [ ] Spot check with the owner's known areas
- [x] Gaps recorded - 2,027 cells (31%) have no POI, 3,155 POIs lie only in the 1.5 km buffer, and 1 cell has no locality

**1.6.4 Tests**
- [x] Fixture Overpass responses (mocked transports)
- [ ] Integration test on a test database 🔒 G-DB
- [ ] Phase 1 exit criteria met (with 1.7)

### Part 1.7: Shared LLM client

**1.7.1 Provider abstraction**
- [x] Selection by environment (Ollama primary, OpenRouter free backup)
- [x] OpenAI-compatible interface
- [x] Inside agents the base URL is Nasiko's LLM Router; elsewhere Ollama or OpenRouter directly

**1.7.2 Strict-JSON helper**
- [x] Pydantic validation of outputs
- [x] Bounded retries
- [x] Timeouts

**1.7.3 Fallback**
- [x] Automatic fall back from primary to backup
- [x] Failure logged

**1.7.4 Tests**
- [x] Mocked providers
- [x] No network in tests

---

## Phase 2: Optional rent data, growth signals and snapshot

**Status:** not started

### Part 2.1: Optional rent and price CSV import

**2.1.1 CSV template and schema**
- [ ] Define columns (rent or sale, property type, price, period, area, locality, optional coordinates, source note)
- [ ] No personal-data columns
- [ ] Publish a template CSV

**2.1.2 Owner input** 🔒
- [ ] Owner supplies a CSV for the demo city, or confirms the MVP runs without one

**2.1.3 Validation and cleaning**
- [x] Pydantic row model
- [x] Reject area under 50 or over 20,000 sq ft
- [x] Reject prices beyond 5 standard deviations of the locality median
- [x] Deduplicate
- [x] Tests

**2.1.4 Importer CLI**
- [x] `--dry-run` that writes nothing
- [x] Report of accepted and rejected rows

**2.1.5 Persist listings** 🔒 G-DB
- [ ] Upsert listings
- [ ] Owner approves the write
- [ ] Record in the Database change log

### Part 2.2: Geocoding and cell assignment

**2.2.1 Geocoder client**
- [x] Owner confirms D-08 🔒
- [x] Client with cache
- [x] About 1 request per second

**2.2.2 Precision flag**
- [x] `exact` when coordinates exist
- [x] `locality` otherwise

**2.2.3 Cell assignment**
- [x] Compute H3 index for each listing
- [x] Report unassignable rows

### Part 2.3: Rent and price estimation

**2.3.1 Cell rent**
- [x] Use own listings when there are 3 or more
- [x] Otherwise inverse-distance-weighted k-ring average
- [x] Set `rent_is_estimated`
- [x] Tests

**2.3.2 Locality price**
- [x] Aggregate residential price by locality
- [x] Assign to all cells in the locality

**2.3.3 Coverage metrics**
- [x] `listing_coverage`
- [x] `price_coverage`

**2.3.4 No-data state**
- [x] Value stays null and is labelled missing
- [x] Test with an empty CSV

### Part 2.4: Growth signals from OSM

**2.4.1 Fetch signals** 🔒 G-DECIDE
- [ ] Owner confirms D-21
- [ ] Fetch OSM `construction`, `proposed` and related tags

**2.4.2 Curated notes**
- [ ] `config/area_notes.yaml` format with source and date
- [ ] Owner writes or approves notes 🔒

**2.4.3 Map to cells**
- [ ] Signals mapped to cells and localities (input to F9)

**2.4.4 Persist intel** 🔒 G-DB
- [ ] Insert `market_intel` rows with sources
- [ ] Owner approves the write
- [ ] Record in the Database change log

### Part 2.5: Snapshot dataset

**2.5.1 Snapshot format**
- [ ] Define JSON structure
- [ ] Export command producing `data/snapshots/{city}_{yyyy-mm}.json`

**2.5.2 Seed script** 🔒 G-DB
- [ ] `scripts/seed_demo.py`
- [ ] Owner approves the load
- [ ] Record in the Database change log

**2.5.3 Offline verification**
- [ ] Disconnect network and run the demo path
- [ ] Phase 2 exit criteria met

---

## Phase 3: Feature and scoring engine

**Status:** not started

### Part 3.1: Foundations

**3.1.1 Package layout**
- [x] `scoring/features.py`
- [x] `scoring/tier_fit.py`
- [x] `scoring/score.py`
- [x] Pure functions with type hints and docstrings

**3.1.2 Normalisation**
- [x] Percentile rank within city
- [x] Inversion of negative features
- [x] Tests including ties and constant series

**3.1.3 Config binding**
- [x] Load weights, `poi_weights`, catchment k and lambda per category
- [x] Load `answer_modifiers`

### Part 3.2: Demand and cluster features (F1, F3, F4)

**3.2.1 F1 anchor footfall**
- [x] Distance-decayed sum per §5.2
- [x] Per-category lambda (cafe 350, pharmacy 300, clothing 600)
- [x] Catchment via k-ring (cafe and pharmacy k=2, clothing k=4)
- [x] Tests

**3.2.2 F3 residential demand**
- [x] Combine population and building density
- [x] Tests

**3.2.3 F4 retail cluster**
- [x] Same-category density
- [x] Complementary categories
- [x] Tests

**3.2.4 Answer modifiers**
- [x] Apply modifiers (e.g. students × 1.3 on college weight)
- [x] Tests

### Part 3.3: Affluence and tier fit (F2)

**3.3.1 Premium POI density**
- [x] Premium brands from the YAML list
- [x] Car showrooms, fine dining, 4–5 star hotels

**3.3.2 Affluence index** 🔒 G-DEVIATE
- [ ] Owner answers D-22(a)
- [ ] §5.3 formula when rent CSV data exists
- [ ] Approved variant when it does not
- [ ] Output in 0..1
- [ ] Tests

**3.3.3 Tier fit**
- [x] Shortfall and overshoot penalties from config
- [x] Clamp to 0..1
- [x] Tests for all three tiers

### Part 3.4: Competition, gap and rent efficiency (F5, F6, F8)

**3.4.1 Competitor tier guess**
- [x] Brand list lookup
- [x] Area affluence rule
- [x] Optional small-LLM classification through the shared client (cached, validated)
- [x] Unknown stays `unknown` and counts as adjacent

**3.4.2 F5 supply**
- [x] Decay-weighted supply
- [x] Tier weights 1.0 / 0.5 / 0.2
- [x] Inversion when scored

**3.4.3 F6 gap opportunity**
- [x] demand = F1_raw × affluence_fit
- [x] gap = pct(demand / (supply + 0.5))

**3.4.4 F8 rent efficiency** 🔒 G-DEVIATE
- [ ] pct(F1_norm / (rent_norm + 0.1)) when rent exists
- [ ] Owner answers D-22(b) for the no-rent fallback
- [ ] Fallback implemented
- [ ] Tests

### Part 3.5: Accessibility and growth (F7, F9)

**3.5.1 F7 accessibility**
- [x] Combine road class, main-road distance, transit and parking
- [x] Tests

**3.5.2 F9 growth momentum**
- [x] Derive from the OSM growth signal and curated notes
- [x] Neutral value when no signal exists, flagged in confidence

### Part 3.6: Accuracy boosters

**3.6.1 Day-part, age skew, medical density** 🔒 G-DECIDE, G-DEVIATE
- [ ] Owner answers D-19
- [ ] Day-part profile (#7)
- [ ] Age-skew proxy (#16)
- [ ] Medical ecosystem density (#17)

**3.6.2 Handled elsewhere**
- [ ] Confirm rent hard filter (#12) is in 3.7.1
- [ ] Confirm vacancy listings (#13) are in 4.5.4

**3.6.3 Optional boosters** 🔒 G-DECIDE
- [ ] Owner answers D-18
- [ ] Implement only the approved ones

### Part 3.7: Constraints, ranking and explanations

**3.7.1 Hard filters**
- [x] Rent filter (rent × size > 1.2 × budget excludes) where rent data exists
- [x] Residential-only exclusion with pharmacy exception and flag
- [x] Confidence under 0.25 greyed and unranked

**3.7.2 Score and contributions**
- [x] `score = 100 × Σ w·f`
- [x] Per-feature contributions
- [x] Contributions sum to score

**3.7.3 Confidence** 🔒 G-DEVIATE
- [ ] Owner answers D-22(c)
- [ ] 0.4 POI + 0.3 listing + 0.2 recency + 0.1 price (or the approved variant)
- [ ] Tests

**3.7.4 Drivers and risks**
- [x] Top 3 positive drivers
- [x] Top 2 risks
- [x] Human-readable driver text from templates (no LLM)

**3.7.5 Ranking and zones**
- [x] Rank and `top_n`
- [x] Merge adjacent cells into named zones
- [x] Zone name from locality plus side

**3.7.6 No-candidates behaviour**
- [x] `NO_CANDIDATES` result
- [x] Cheapest 3 zones with rent when rent data exists

### Part 3.8: Feature build pipeline

**3.8.1 Build pipeline** 🔒 G-DB
- [x] Catchment generator `pipelines/catchments.py`: each cell's POIs within its k-ring with `distance_m` (lazy; k=2 for the whole city in 3.8 s, k=4 in 10.5 s)
- [x] `pipelines/build_features.py` (also `pipelines/catchment_sums.py`, `features_store.py`, `run_features.py`; all 3 categories for 6,631 cells build in about 5 s; numpy sums verified against B's `anchor_footfall`, `retail_cluster` and `competition_pressure`; B's `ScoreEngine` ranks the output)
- [x] Dry-run mode (default; storing needs `--write` and approval)
- [x] Owner approves the write
- [x] Record in the Database change log

**3.8.2 Versioning and freshness**
- [x] `feature_version` handling (version 1; stored per tier inside one JSON row per cell and category)
- [~] Oldest source date per cell stored (recency comes from the oldest download; not stored per cell)

### Part 3.9: Tests and CLI

**3.9.1 Core tests**
- [x] Weights sum to 1.0 for every config
- [x] Contributions sum to score
- [x] Score in [0, 100]
- [x] Premium tier lowers scores in low-affluence cells
- [x] Worked example §5.8 within tolerance

**3.9.2 Property tests**
- [x] Hypothesis tests for bounds and monotonicity

**3.9.3 CLI**
- [x] Score from `cell_features` or snapshot
- [x] Table and JSON output

**3.9.4 Category awareness**
- [x] Same location scored for all three categories
- [x] Results differ as expected

**3.9.5 OSM-only mode**
- [x] End-to-end scoring with no rent data
- [x] Output labels what is missing
- [x] Phase 3 exit criteria met

---

## Phase 4: Backend API

**Status:** not started

### Part 4.1: Application skeleton

**4.1.1 App factory and logging**
- [x] FastAPI app factory (`backend/app/main.py`, run with `uvicorn backend.app.main:create_app --factory`)
- [x] Settings via environment (secret never printed; placeholder key rejected in production)
- [x] Structured JSON logs with request ID

**4.1.2 Auth**
- [x] `X-API-Key` dependency (constant-time comparison)
- [x] `X-User-Id` propagation
- [ ] User upsert by `external_id`

**4.1.3 CORS**
- [x] Origins from `ALLOWED_ORIGINS` (only configured origins are allowed)

### Part 4.2: Persistence layer

**4.2.1 Sessions**
- [x] Session and transaction management (reads use READ ONLY sessions, verified against the real database; write sessions will be separate and explicit)

**4.2.2 Repositories**
- [~] Cities and cells (listing ready cities is done)
- [ ] Features
- [ ] Analyses and recommendations
- [ ] Jobs and configs

### Part 4.3: Schemas and errors

**4.3.1 Models**
- [x] Create-analysis request
- [x] Recommendations response
- [x] Compare and what-if models

**4.3.2 Error envelope**
- [x] Envelope model (Agent B's Pydantic model; the runtime shape is in `backend/app/core/errors.py`)
- [x] Five error codes mapped to HTTP statuses (plus additive `UNAUTHORIZED` and `NOT_FOUND`)
- [x] Global exception handlers (no stack traces or secrets reach the client)

### Part 4.4: Meta endpoints

**4.4.1 Health**
- [x] `GET /health` (public liveness plus a database hint)

**4.4.2 Cities**
- [x] `GET /cities` returns ready only

**4.4.3 Categories**
- [x] `GET /categories` from config (tiers with labels plus the wizard questions, answer ids matching `answer_modifiers`)

### Part 4.5: Analysis lifecycle

**4.5.1 Create analysis** 🔒 G-DB
- [x] Validate input
- [x] Insert queued analysis
- [x] Return id immediately
- [x] Owner approves first run against a real database (approved and run 2026-09-20)

**4.5.2 Pipeline runner**
- [x] Load features
- [x] Score
- [x] Narratives (deterministic templates until the report agent exists)
- [x] Mark done or failed

**4.5.3 Status endpoint**
- [x] `GET /analyses/{id}`

**4.5.4 Recommendations endpoint**
- [x] Ranked zones with breakdown
- [x] GeoJSON option
- [ ] Nearby listings when a CSV exists
- [x] Data notes

**4.5.5 Zone detail endpoint**
- [x] `GET /analyses/{id}/zones/{rank}` (with landmarks within 500 m)

**4.5.6 Snapshot fallback**
- [ ] Use the last good snapshot on upstream failure
- [ ] Show its date in the response

### Part 4.6: Analysis extras

**4.6.1 Compare**
- [x] `POST /analyses/{id}/compare` for 2–3 zones

**4.6.2 What-if**
- [x] Re-score with changed tier, budget, size or category
- [x] Rank-change output

**4.6.3 Chat**
- [ ] `POST /chat` contract
- [ ] Stub until Phase 5 integration

**4.6.4 Report PDF** 🔒 G-DECIDE
- [-] Owner confirms D-10 (cut by the owner, 2026-09-20)
- [-] `GET /analyses/{id}/report.pdf` with WeasyPrint (cut by the owner, 2026-09-20)

### Part 4.7: Admin endpoints

**4.7.1 Ingest trigger**
- [ ] `POST /admin/cities/{id}/ingest`

**4.7.2 Jobs and freshness**
- [ ] `GET /admin/jobs`
- [ ] `GET /admin/data-freshness`

**4.7.3 Config versions** 🔒 G-DB
- [ ] `PUT /admin/configs/{category}`
- [ ] Weight-sum validation
- [ ] New version, never overwrite

**4.7.4 Role enforcement**
- [ ] Admin-only routes

### Part 4.8: Hardening

**4.8.1 Rate and size limits**
- [ ] Rate limiting
- [ ] Request size limits

**4.8.2 Outbound calls**
- [ ] Timeouts
- [ ] Retry policy

**4.8.3 Validation edge cases**
- [ ] Unknown city
- [ ] Tier not offered for the category
- [ ] Unrealistic budget or size

### Part 4.9: Tests and packaging

**4.9.1 Tests** 🔒 G-DB
- [ ] Owner approves test database provisioning
- [ ] Unit tests
- [ ] API tests for every endpoint

**4.9.2 Container**
- [x] Backend Dockerfile (`backend/Dockerfile`: slim Python 3.11, non-root user, health check)
- [x] Compose service (`backend` in `docker-compose.yml`, localhost:8000 only; checked end to end: health, 401, cities, 404, JSON logs)
- [x] Confirm migrations do not run automatically at startup (the container only starts uvicorn)

**4.9.3 Smoke test**
- [ ] `scripts/smoke_test.sh`
- [ ] Sample payloads
- [ ] Phase 4 exit criteria met

---

## Phase 5: Agents on Nasiko

**Status:** not started

### Part 5.1: Agent framework

**5.1.1 Shared base**
- [x] Scaffold from a Nasiko template with `nasiko new` (the hello-world agent follows the template pattern)
- [x] A2A v1.0 JSON-RPC server with Agent Card and `SendMessage` (proven by the hello-world agent; shared glue in `agents/_shared/a2a_glue.py`)
- [x] Pydantic-validated JSON payloads (`agents/_shared/runner.py`)
- [x] Response envelope (`agent`, `version`, `latency_ms`, `warnings[]`) (plus an `error` object instead of `payload` on failure)

**5.1.2 Secrets**
- [ ] Per-agent secrets via `nasiko secrets set` or environment
- [ ] Minimal variables per agent

**5.1.3 LLM access**
- [ ] Reuse the shared LLM client (1.7)
- [~] Go through Nasiko's LLM Router with the config from `nasiko llm-config` (works for the hello-world agent; per-agent `llm-config` not needed because the server defaults point at Ollama)

**5.1.4 Network path**
- [x] Agent containers reach our PostGIS (the `sitescout-scoring` agent reads `host.docker.internal:5433` READ ONLY; verified with a real scored analysis)
- [x] Agent containers reach the backend where needed (the backend calls the agent through Nasiko's proxy; the agent does not call the backend back)
- [x] Confirm Nasiko's own databases are not used or touched (the agent only opens `open_store_url` against `DATABASE_URL`, SiteScout's own database)

### Part 5.2: Data-side agents

**5.2.1 `geo-data`**
- [ ] Wrap Phase 1 pipeline
- [ ] Endpoint contract and tests

**5.2.2 `listings`**
- [ ] Wrap CSV import, geocoding and rent estimation
- [ ] Endpoint contract and tests

**5.2.3 `market-intel`**
- [ ] Answer from OSM construction data and curated notes, with sources
- [ ] Say "not available" when there is no data
- [ ] Endpoint contract and tests

**5.2.4 `affluence`**
- [ ] Wrap affluence, competitor tiers and smoothing
- [ ] Endpoint contract and tests

### Part 5.3: Analysis-side agents

**5.3.1 `scoring`**
- [x] Rank endpoint, with the explanation (contributions, drivers, risks, narrative) bundled in the same reply (`backend/app/services/scoring_agent.py`, wraps the same `score_zones` the backend uses locally)
- [x] Tests (`backend/tests/test_scoring_agent.py`, `backend/tests/test_agent_gateway.py`)
- [ ] What-if and compare stay backend-only for now (they operate on an already-stored analysis, not a fresh ranking call); revisit if the agent should own them too

**5.3.2 `report-chat`**
- [ ] Narrative generation
- [ ] Follow-up answers
- [ ] What-if requests
- [ ] PDF hook

**5.3.3 Narrative guardrails**
- [ ] Structured JSON input only
- [ ] 3–5 sentences with 2 drivers, 1 risk, 1 on-site check
- [ ] Number post-check against the input
- [ ] One regeneration on failure
- [ ] Tested with the small local model

**5.3.4 `orchestrator`** 🔒 G-DECIDE
- [ ] Owner answers D-04
- [ ] Pipeline order with retries
- [ ] Tests

### Part 5.4: Cards and containers

**5.4.1 Agent Cards**
- [~] A2A Agent Card for each agent (hello-world and `sitescout-scoring` done; `geo-data`, `listings`, `market-intel`, `affluence`, `report-chat`, `orchestrator` still empty folders)
- [ ] Skill descriptions checked against routing behaviour

**5.4.2 Containers**
- [~] Dockerfile per agent (hello-world and `sitescout-scoring` done)
- [ ] Compose file per agent (not needed: agents are built and run by Nasiko itself, not by our compose file)
- [ ] `sample_request.json` per agent

### Part 5.5: Deploy and routing

**5.5.1 Deploy**
- [~] Deploy each agent with the CLI or dashboard (hello-world and `sitescout-scoring` done; repeatable command `python -m scripts.deploy_agent scoring --include agent_base=agents/_shared --include backend=backend --include shared=shared --include scoring=scoring --include pipelines=pipelines --data config=config`)
- [x] Note whether the routing engine sees new agents immediately (yes, no restart needed)

**5.5.2 Direct calls**
- [ ] `nasiko chat --agent ...` works for each agent
- [ ] Scripted `SendMessage` through the proxy works

**5.5.3 Router selection**
- [ ] Explanation question routes to `report-chat`
- [ ] Area or growth question routes to `market-intel`
- [ ] Same checks with the backup model

**5.5.4 Access control and flow guards**
- [ ] Backend-to-agent calls allowed
- [ ] Orchestrator-to-agent calls allowed
- [ ] Depth, fan-out and token limits fit the pipeline

### Part 5.6: Backend integration

**5.6.1 Client**
- [x] `nasiko_client` authenticates to Nasiko (`backend/app/services/nasiko_client.py`, tested)
- [x] Sends A2A `SendMessage` calls (also the routing-engine call)
- [x] `AgentGateway` / `NasikoScorer` (`backend/app/services/agent_gateway.py`) call the `sitescout-scoring` agent for a real analysis and fall back to local scoring (`ScorerUnavailableError`) if the agent is unreachable or answers something unusable; wired into `create_app` via `USE_NASIKO_AGENTS`, `NASIKO_USERNAME`, `NASIKO_PASSWORD`. Verified live: `POST /v1/analyses` for cafe/mid produced the same top zone (Officers Colony, 82.6) through the real agent call, logged as `scored an_66b9a05f on Nasiko agent sitescout-scoring v0.1.0 in 1893 ms`.

**5.6.2 Run tracking** 🔒 G-DB
- [ ] Write `agent_runs` rows
- [ ] Owner approves first writes
- [ ] Record in the Database change log

**5.6.3 Chat wiring**
- [ ] `/chat` calls the routing engine
- [ ] Return answer with sources or an explicit "not available"

### Part 5.7: Scheduler

**5.7.1 Job**
- [ ] APScheduler OSM refresh (monthly)

**5.7.2 Staleness**
- [ ] Mark stale after the freshness window

### Part 5.8: Observability

**5.8.1 Traces**
- [ ] One trace per agent call in the Nasiko dashboard
- [ ] `nasiko observe` view checked

**5.8.2 Tracking**
- [ ] Tokens and latency per analysis
- [ ] Phase 5 exit criteria met

---

## Phase 6: Streamlit app

**Status:** not started

### Part 6.1: App skeleton and backend client

**6.1.1 Layout**
- [x] Multipage Streamlit app under `frontend/streamlit_app/`

**6.1.2 Backend client**
- [x] Typed client with `X-API-Key` and `X-User-Id` headers
- [x] Timeouts
- [x] Friendly error mapping
- [x] API key stays server-side

**6.1.3 Users and roles** 🔒 G-DECIDE
- [ ] Owner answers D-23
- [ ] Implement the chosen approach

**6.1.4 Configuration**
- [x] Environment variables documented

### Part 6.2: Owner screens

**6.2.1 Screen 1: My analyses**
- [x] Table of past analyses
- [x] "New analysis" button

**6.2.2 Screen 2: Wizard**
- [x] Step 1 city and category cards
- [x] Step 2 tier selection
- [x] Step 3 constraints and category questions
- [x] Step 4 review and submit

**6.2.3 Progress state**
- [x] Poll the backend until done
- [x] Failure state

**6.2.4 Screen 3: Results**
- [x] Map with hex overlay
- [x] Ranked table
- [x] KPI tiles
- [x] Layer toggles
- [x] Confidence filter, and rent filter where available

**6.2.5 Screen 4: Zone detail**
- [x] Overview tab
- [x] Score breakdown tab
- [x] Landmarks tab
- [x] Spending power tab
- [x] Competition tab
- [x] Rent and listings tab (when data exists)
- [x] Risks and checklist tab

**6.2.6 Screen 5: Compare**
- [x] Side-by-side columns for 2–3 zones

**6.2.7 Screen 6: What-if**
- [x] Tier, budget and size controls
- [x] Rank-change display

**6.2.8 Screen 7: Chat**
- [x] Message input and history
- [x] Source links where available

**6.2.9 Screen 8: Export**
- [-] Export action (cut by the owner, 2026-09-20)
- [-] PDF content check (cut by the owner, 2026-09-20)

### Part 6.3: Admin screens

**6.3.1 Data and jobs**
- [x] City table
- [x] Ingestion jobs table
- [x] Freshness view
- [x] Ingest and refresh buttons

**6.3.2 Weights editor**
- [x] Editable weights with live sum check
- [x] Save as new version and set active
- [x] Show last back-test result

**6.3.3 System health**
- [x] Agent status, latency and error rate
- [x] Link to the Nasiko dashboard

### Part 6.4: Map

**6.4.1 Library**
- [x] Choose folium or pydeck from the Phase-0 spike

**6.4.2 Overlay**
- [x] Hex overlay coloured by score with legend
- [ ] Top-10 pins
- [ ] Layer toggles (landmarks, competitors, listings)

**6.4.3 Interaction**
- [x] Click a hex or pin to select a zone
- [x] Zone summary shown

### Part 6.5: Packaging and access

**6.5.1 Container**
- [x] Streamlit Dockerfile
- [x] Compose service

**6.5.2 Network layout**
- [x] Only Streamlit exposed to the user
- [x] Backend and Nasiko gateway stay private

**6.5.3 Optional tunnel** 🔒 G-DECIDE
- [ ] Owner decides if remote access is needed (D-12)
- [ ] Free tunnel to Streamlit only

### Part 6.6: UX states

**6.6.1 Edge cases**
- [x] City not ready
- [x] `NO_CANDIDATES`
- [x] Low-confidence warning
- [x] Tier-area mismatch reason
- [x] Out-of-scope chat reply
- [x] Upstream failure with snapshot date

**6.6.2 Caveats**
- [x] Data-source caveats on every result
- [x] "Rent data not available" state when there is no CSV

### Part 6.7: Documentation

**6.7.1 App docs**
- [ ] Screenshots
- [ ] Short README in `frontend/streamlit_app/`
- [ ] Phase 6 exit criteria met

---

## Phase 7: Validation and tuning

**Status:** not started

### Part 7.1: Back-test dataset

**7.1.1 Owner input** 🔒
- [ ] Owner supplies about 10 known places per category
- [ ] Owner supplies the expected order

**7.1.2 Store cases**
- [x] Cases in `data/backtest/`
- [x] Format documented

### Part 7.2: Back-test run

**7.2.1 Script**
- [x] `scripts/backtest.py`
- [x] Top-3 hit rate
- [x] Pass or fail per case

**7.2.2 All categories**
- [x] Clothing: markets above residential
- [x] Cafe: colleges and offices high
- [x] Pharmacy: hospitals and dense housing high

### Part 7.3: Popularity correlation (optional)

**7.3.1 Spearman** 🔒
- [ ] Owner decides whether popularity data exists (D-07)
- [ ] If yes: exclude each shop from its own competition feature
- [ ] If yes: Spearman per category
- [ ] If no: limitation written down

### Part 7.4: Sensitivity and stability

**7.4.1 Weight perturbation**
- [x] ±20 percent perturbation
- [x] Top-10 change report

**7.4.2 Tier direction**
- [x] Premium moves toward high-affluence zones

### Part 7.5: Tuning

**7.5.1 Proposals** 🔒 G-DEVIATE, G-DB
- [ ] Present weight changes with evidence
- [ ] Owner approves
- [ ] Save as a new config version
- [ ] Record in the Database change log

**7.5.2 Re-test**
- [ ] Re-run the back-test
- [ ] Record the result per version

### Part 7.6: Metrics

**7.6.1 Pitch numbers**
- [x] Top-3 hit rate
- [x] Average confidence of top 10
- [x] End-to-end latency
- [ ] Spearman if 7.3 ran
- [ ] Phase 7 exit criteria met

---

## Phase 8: Polish, hardening and demo

**Status:** not started

### Part 8.1: Feature completion

**8.1.1 Feature check**
- [x] Compare works for all categories
- [x] What-if works for all categories
- [x] Chat works for all categories
- [-] PDF works for all categories (cut by the owner, 2026-09-20)

**8.1.2 Success criteria**
- [x] Result in under 30 seconds
- [x] Clothing example behaves correctly
- [x] Categories score differently
- [x] Tier change re-ranks
- [x] Back-test shows good above bad

**8.1.3 Nasiko showcase**
- [ ] Every agent appears in the Nasiko dashboard
- [ ] Traces visible
- [ ] Routing demonstrated on a chat question

### Part 8.2: Offline and resilience

**8.2.1 Offline demo**
- [ ] Full demo from snapshot with network off

**8.2.2 Failure drills**
- [ ] Ollama down, falls back to OpenRouter
- [ ] Overpass unavailable, snapshot used
- [ ] An agent unavailable

### Part 8.3: End-to-end and performance

**8.3.1 E2E test**
- [ ] Automated smoke path

**8.3.2 Latency**
- [ ] Measure against the 30-second target, including local-LLM narrative time

### Part 8.4: Documentation

**8.4.1 README**
- [ ] Setup steps from §19.3 as adapted
- [x] Run and test instructions

**8.4.2 Runbook**
- [ ] Refresh procedures
- [ ] CSV import
- [ ] Troubleshooting

**8.4.3 Architecture corrections** 🔒 G-EDIT
- [ ] List proposed corrections to `architecture-1.md`
- [ ] Owner approves each before any edit

### Part 8.5: Final quality pass and cost audit

**8.5.1 Static checks**
- [ ] ruff clean
- [ ] mypy clean
- [ ] Full pytest passes

**8.5.2 Secret scan**
- [ ] No keys in the repo history
- [ ] `.env` and raw data not committed

**8.5.3 Dependency and container review**
- [ ] Pinned dependencies
- [ ] Minimal container images

**8.5.4 Cost audit**
- [ ] Re-run the free-stack inventory from 0.5.5
- [ ] Confirm no paid service, plan or credit-limited API is in the path

### Part 8.6: Demo

**8.6.1 Rehearsal**
- [ ] Rehearse the 5-minute script without Anakin or DronaHQ segments

**8.6.2 Slides**
- [x] Problem and solution
- [x] Limitations statement
- [x] Back-test numbers
- [x] Roadmap

**8.6.3 Backup**
- [ ] Recorded run
- [ ] Snapshot ready

### Part 8.7: Stretch: Mumbai (only if time remains)

**8.7.1 Go decision** 🔒
- [-] Owner confirms time remains and Mumbai goes ahead (cut by the owner, 2026-09-20)

**8.7.2 Ingest Mumbai**
- [-] Run the same ingestion pipeline for Mumbai (configuration only, no code change) (cut by the owner, 2026-09-20)
- [-] Tiled Overpass fetch and QA report (cut by the owner, 2026-09-20)
- [-] Snapshot exported (cut by the owner, 2026-09-20)

**8.7.3 Enable and test**
- [-] Owner supplies Mumbai back-test cases 🔒 (cut by the owner, 2026-09-20)
- [-] City enabled in the wizard (cut by the owner, 2026-09-20)
- [-] Scores checked for all three categories (cut by the owner, 2026-09-20)

### Part 8.8: Sign-off

**8.8.1 Definition of done**
- [ ] Every §20.1 item checked as adapted (Bengaluru; Mumbai only if it was done)
- [ ] Every §1.7 criterion checked as adapted
- [ ] Remaining gaps listed for the owner
- [ ] Phase 8 exit criteria met

---

## 7. Change log

| Date | Change | Approved by |
|---|---|---|
| 2026-09-20 | `plan.md` and `progress.md` created from `architecture-1.md` (new files; no existing file modified). | Requested by owner |
| 2026-09-20 | Plan 0.2 / progress rewritten for a free MVP: Anakin and DronaHQ removed, Nasiko kept, Streamlit, OSM plus optional CSV, Ollama with OpenRouter backup, PostGIS in Docker; new Part 1.7 (shared LLM client); Phases 2 and 6 rewritten; decisions D-20 to D-24 added. | Owner ("start editing the idea") |
| 2026-09-20 | Nasiko `.env` extended with `OPENAI_API_BASE`, `DEFAULT_PROVIDER` and `DEFAULT_MODEL` (LLM Router now targets Ollama); server container recreated; admin login verified via API; container-to-Ollama reach verified. Only the `.env` file I created was changed in `D:\Projects\Nasiko`. | Owner (approved creating and starting Nasiko) |
| 2026-09-20 | Plan 0.5: work split for two Claude agents (`plan.md` §9, handoff file `handoff-agent-b.md`); Docker Desktop and the Nasiko stack started (7 containers, server healthy); Ollama model chosen (`qwen2.5:7b-instruct`, embeddings `nomic-embed-text`) and set in Nasiko's `.env`; repo scaffolded (folders, `pyproject.toml`, requirements and lock file, `.gitignore`, `.env.example`, pre-commit, `scripts/update_progress_summary.py`); local `git init`; Bengaluru OSM coverage counts recorded; D-15 and D-28 answered, D-22 deferred, D-24 partly answered. `architecture-1.md` verified unchanged (size and timestamp). | Owner (answers to repo root, second Claude, `shared/`, niche, defer D-22, start Nasiko) |
| 2026-09-20 | Plan 0.4: scope confirmed by the owner (Bengaluru first, Mumbai stretch as new Part 8.7 with sign-off moved to 8.8; all three categories; tiers lower class, medium class and niche; dashboard instead of CLI; Python 3.11.9). Created `D:\Projects\Nasiko\.env` (new file, generated secrets, Ollama route; the paid OpenAI key was not copied). Decisions D-28 and D-29 added; D-22 given a concrete proposal awaiting approval. | Owner ("create it yourself", answers 2–5) |
| 2026-09-20 | Plan 0.3: read-only review of the installed Nasiko at `D:\Projects\Nasiko`; Phase 0 Part 0.3 and Phase 5 adapted to A2A v1.0, port 8080, LLM Router and routing engine; CLI allowed; decisions D-25 to D-27 added; blockers recorded. Nothing in `D:\Projects\Nasiko` was changed. | Owner (Nasiko already set up, CLI may be used) |
