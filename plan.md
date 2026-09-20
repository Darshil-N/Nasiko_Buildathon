# SiteScout: Build Plan (Free MVP edition)

> Source of truth for *what* the product is: `architecture-1.md` (section numbers appear as §n). That file is not edited.
> This file is the full plan of changes for the **free MVP**, split into **phases → parts → steps**. Step IDs (`P.Part.Step`, e.g. `3.2.1`) are reused in `progress.md`, which tracks how much of this plan is done.
> Plan version: 0.5 · Created: 2026-09-20 · Revised: 2026-09-20 (free-MVP rescope, adapted to the installed Nasiko, scope confirmed by the owner, work split for two agents, repo scaffolded) · Status: planning; only read-only checks done so far, plus one new file, `D:\Projects\Nasiko\.env` (no code, no database).
>
> **Revision 0.2:** Anakin and DronaHQ are no longer required. Nasiko stays compulsory. Everything must be free to build and run. Items marked *(proposed)* are my suggested replacements that still need the owner's confirmation in the Decision Log.
>
> **Revision 0.3:** Nasiko is already installed at `D:\Projects\Nasiko` and the `nasiko` CLI may be used. A read-only review showed it is a newer version than `architecture-1.md` §13 assumes (A2A v1.0 agents, port 8080, built-in LLM Router). Phase 0 and Phase 5 are adapted accordingly (see §2.4).
>
> **Revision 0.4:** The owner confirmed the scope: Bengaluru first (Mumbai only if time remains), all three categories, three tiers (lower class, medium class, niche), the Nasiko dashboard instead of the CLI for now, and the installed Python 3.11.9. The Nasiko `.env` was created (see §2.4). Still waiting on the owner's approval of the no-rent-data formulas (D-22) and the meaning of "niche" (D-28).
>
> **Revision 0.5:** The owner said "niche" means premium (D-28) and that the no-rent-data formulas (D-22) wait until we come back to them, so they are deferred. Docker and the Nasiko stack are running. The repo root is this folder with a local git repository (nothing pushed), and a `shared/` package was added to the layout. A second Claude joins on the same machine, so the work is split in §9. An Ollama model was chosen: `qwen2.5:7b-instruct` (D-03), because the Antraa and fairsynth models carry unrelated baked-in prompts.

---

## 1. Working rules (set by the project owner)

1. Without asking, not even a single letter of existing content is changed. Existing files (including `architecture-1.md`) are never edited without explicit approval.
2. No database change is made directly without asking first (DDL, migrations, seeds, inserts, updates, deletes).
3. `plan.md` (this file: the whole plan) and `progress.md` (how much is finished, what remains, all micro changes) are kept current.
4. Code quality stays production grade (standards in §4).
5. Nothing is pushed without asking. Local commits are fine.
6. Nothing is assumed. Wherever something is unspecified or blocked, ask.

*(The owner's list was numbered 1, 2, 3, 4, 7, 8. Rules 5 and 6 were not provided. They are asked about in decision D-16 in `progress.md`.)*

---

## 2. MVP scope: free, with Nasiko compulsory

### 2.1 Constraints from the owner
- **Nasiko is compulsory.** The agents are registered and run on Nasiko, reached through its gateway and router, with its observability.
- **Anakin and DronaHQ are not compulsory.** They are removed from the MVP and replaced with free alternatives.
- **The MVP must be free to build and run.** No paid API, no paid plan, no credit-limited service in the core path.

### 2.2 Replacement map

| Need | Original (architecture) | Free MVP choice | Status |
|---|---|---|---|
| Agent platform | Nasiko (older Kong/Mongo layout assumed in §13) | **Nasiko, already installed at `D:\Projects\Nasiko` (newer Rust / A2A v1.0 version). The `nasiko` CLI may be used.** | Fixed; details in §2.4 |
| Interface | DronaHQ | **Streamlit** (Python, open source), talks only to the backend | Answered by owner |
| Rent and property-price data | Anakin scraping of property portals | **OSM-only core + optional CSV** that the owner provides for the demo city. No scraping. | Answered by owner |
| Growth signals and "market intel" | Anakin search and agentic search | *(proposed)* OSM `construction` / `proposed` tags plus a curated notes file, summarised locally. No live web search. | Proposed (D-21) |
| LLM | OpenRouter or OpenAI (paid) | **Ollama local model as primary**, OpenRouter free models as backup | Answered by owner. Nasiko's LLM Router supports OpenRouter natively; Ollama is not a built-in provider and would need an OpenAI-compatible base-URL route, which must be verified (§2.4) |
| Database | PostgreSQL + PostGIS | **PostgreSQL + PostGIS in Docker** (free, open source) | Answered by owner |
| POIs, land use, buildings, roads | OSM via Overpass | OSM via Overpass (unchanged, free) | Fixed |
| Population density | WorldPop or Census | WorldPop or Census (both free) | Open (D-06) |
| Geocoding | Nominatim or Photon | Nominatim or Photon, only for CSV rows lacking coordinates | Proposed (D-08) |
| Competitor price level and popularity | Google Places (paid) | *(proposed)* Not used. Tier from brand list, area affluence and optional local LLM. | Proposed (D-07) |
| Walking isochrones | OpenRouteService, Valhalla | *(proposed)* Out of the MVP; k-ring catchments only | Proposed (D-18) |
| PDF export | DronaHQ add-on or WeasyPrint | *(proposed)* WeasyPrint in the backend | Proposed (D-10) |
| Public access | ngrok or Cloudflare Tunnel | *(proposed)* Local only; free Cloudflare Tunnel only if remote access is needed | Proposed (D-12) |
| Observability | Nasiko OpenTelemetry and Phoenix | Nasiko's own (OpenTelemetry, Tempo, Loki, dashboard, `nasiko observe`); free | Fixed |
| Scheduler | APScheduler | APScheduler (unchanged, free) | Fixed |

### 2.3 Consequences of removing paid data (each needs the owner's decision, see D-22)
The architecture's formulas assume rent and price data. Without it:
- The affluence index loses its two property-price terms (§5.3).
- Rent efficiency F8 and the rent hard filter have nothing to work on unless a CSV is supplied.
- The confidence formula has `listing_coverage` and `price_coverage` terms that would always be zero.
- Any change to weights or formulas is a deviation from the architecture (gate G-DEVIATE), so nothing is changed until the owner approves.

### 2.4 Nasiko as installed (read-only review, 2026-09-20)

Nasiko is already set up at `D:\Projects\Nasiko` (branch `main`, commit `58cfe60`, 14 Sep 2026). Nothing in that folder has been changed. It differs from the version `architecture-1.md` §13 describes:

| Topic | Architecture doc (§9.3, §13) | Installed version |
|---|---|---|
| Runtime | Kong gateway, Mongo, Phoenix; `make start-nasiko` | One Rust control-plane server plus Postgres, Redis, RustFS (S3), OTel Collector, Tempo and Loki; started with `docker compose up -d` |
| Dashboard | `http://localhost:9100/app/` | `http://localhost:8080` |
| Config file | `.nasiko-local.env` | `.env` copied from `.env.example`. That file does not exist yet. The existing `.nasiko-local.env` and `.venv` date from 9 May and belong to the older layout. |
| Agents | Containers with an `AgentCard.json`, custom routes at `/agents/{name}/...` | Any container that speaks **A2A protocol v1.0** (JSON-RPC 2.0 over HTTP, `SendMessage`), reached only through Nasiko's proxy |
| Routing | `GET /router/route?query=...` | 3-stage routing engine: embedding shortlist, rerank, LLM final pick (`ROUTER_MODEL`, `EMBEDDING_MODEL`) |
| LLM access | Keys held in Nasiko's env | **LLM Router:** agents receive `OPENAI_BASE_URL` plus a short-lived identity token, never a real key. Providers: openai, anthropic, gemini, openrouter. Chosen per agent with `nasiko llm-config`. |
| CLI | `nasiko agent upload-directory` | `nasiko` CLI: `connect`, `auth login`, `new`, `deploy`, `upload`, `ps`, `logs`, `chat`, `secrets`, `observe`, `llm-config`, and more |
| Observability | Phoenix | Dashboard, `nasiko observe`, Tempo and Loki |

State of this machine:
- Docker 29.7.2 and Compose v5.5.0 are installed, but the Docker Desktop engine is not running, so Nasiko is not up.
- The `nasiko` CLI is **not installed**. Installing it from source needs Rust 1.85+, which is not installed either. The owner said the CLI may be used but the dashboard is fine for now, so the CLI stays optional and installing Rust stays asked-first (D-26).
- Ollama 0.34.2 is installed and holds several local models. The machine has 23.7 GB RAM and an NVIDIA RTX 3050 with 6 GB.
- Python is 3.11.9. The owner chose to use what is installed (D-27). `uv` is not installed and is optional (a virtual environment with pip works).
- The old `.nasiko-local.env` contains real-looking keys (OpenAI, OpenRouter, MiniMax, GitHub OAuth). Their values were deliberately not displayed. The OpenAI key is a paid provider and is not part of the free MVP.

Owner said only the keys need changing and asked me to create the file. In the installed version the keys live in `.env`, so on 2026-09-20 I created `D:\Projects\Nasiko\.env` from `.env.example`. It is a new file; nothing existing was edited. It holds freshly generated secrets (`SECRETS_ENCRYPTION_KEY`, `JWT_SECRET`, `AGENT_JWT_SECRET`, `ADMIN_PASSWORD`; the template's public default encryption key was replaced) and a free LLM route pointing at Ollama (`OPENAI_BASE_URL=http://host.docker.internal:11434/v1` with a dummy key). The paid OpenAI key from the old file was not copied. The OpenRouter key in the old file is only a placeholder, so the OpenRouter backup needs a real free key from the owner (D-26). `OPENAI_MODEL` still needs the chosen Ollama model id (D-03).

Consequence: §9.3, §13 and parts of §14 and §19 of the architecture no longer match the real platform. The plan adapts to the installed version and records the adaptation as D-25 (G-DEVIATE). `architecture-1.md` itself is not edited.

### 2.5 Scope confirmed by the owner (2026-09-20)

| Item | Decision |
|---|---|
| Cities | **Bengaluru first.** Mumbai only if time remains (stretch, Part 8.7). Bengaluru is large (roughly 700 km², on the order of 7,000 H3 cells, to be measured in 1.3.2), so ingestion is tiled (D-29). |
| Categories | **Cafe, clothing store and pharmacy**, all three in the MVP. |
| Tiers | Three per category: **lower class, medium class and niche**. Proposed mapping to the architecture's internal ids `budget`, `mid`, `premium`; the owner still has to confirm that "niche" means the premium/specialty end (D-28). |
| Nasiko | Use the dashboard for deploying and testing; the CLI stays optional. |
| Python | Use the installed 3.11.9. |
| Model changes for missing rent data | Owner said "ok" to the note that these need changes. Because no concrete formulas were shown at that point, the specific proposal in D-22 still needs explicit approval before Phase 3. |

---

## 3. Approval gates

Work stops and asks before any of these:

| Gate | Trigger |
|---|---|
| **G-DB** | Any database action: create/alter/drop, migration apply, seed, bulk insert, update, delete, config sync. The exact SQL or migration is shown first. |
| **G-EDIT** | Modifying any file that already exists and was not created by us in this plan (starting with `architecture-1.md`). |
| **G-PUSH** | Any `git push`, remote creation, or publishing. Local commits do not need approval. |
| **G-COST** | Anything that could cost money or use a limited quota: any paid service, paid plan, or credit-limited API. The MVP is meant to need none, so this gate should never open; if something would, ask first. |
| **G-DECIDE** | Any choice the architecture leaves open or marks **[VERIFY]**. Recorded in the Decision Log in `progress.md`. |
| **G-DEVIATE** | Any deviation from the architecture (schema, weights, formulas, endpoints, stack, repo layout). |

---

## 4. Production-grade standards (apply to every phase)

Every part is only "done" when it meets these, not just when it runs.

1. **Typing and validation:** full type hints; Pydantic v2 models at every boundary (API, agents, config, CSV rows, LLM outputs); mypy clean on `scoring/` and `backend/`.
2. **Lint and format:** ruff clean; pre-commit hooks installed.
3. **Tests:** pytest unit tests for every pure function in `scoring/`; API tests for every endpoint; external services (Overpass, LLM, geocoder, Nasiko) are mocked with recorded fixtures, so tests never hit the network.
4. **Errors:** the standard error envelope (§10.4) everywhere; no bare `except`; upstream failures mapped to `UPSTREAM_TIMEOUT` and retryable flags; timeouts on every outbound call.
5. **Idempotency:** re-running ingestion for the same city and date never duplicates rows (upsert on natural keys, §9.4).
6. **Config over code:** categories, weights, OSM tags and premium brands live in YAML; adding a category needs no code change (§3.4).
7. **Secrets:** only via environment; never committed; agents receive only the variables they need (§18).
8. **Logging and tracing:** structured JSON logs with request and analysis IDs; every agent call recorded in `agent_runs` with trace ID.
9. **Honesty:** estimated values are labelled `estimated`; missing data is shown as missing, never invented; every result carries data notes and confidence.
10. **Free-only:** every dependency, image, model and service has an open or free licence and needs no paid account. Any addition is checked against this before it is adopted.
11. **Documentation:** each package has a short README section; public functions have docstrings that state units and ranges.
12. **Small, reviewable commits** (local only unless G-PUSH is approved).

---

## 5. Phase overview

| # | Phase | Goal | Architecture refs | Depends on | Output |
|---|---|---|---|---|---|
| 0 | Setup, verification and decisions | Prove Nasiko, the free LLM route and the free data sources work; settle open decisions; scaffold repo | §2, §13, §24 | none | Go/no-go report, repo scaffold |
| 1 | Data foundation | Database, config layer, H3 grid, OSM POIs, land use, population, shared LLM client | §4, §8 | 0 | Cells and POIs for the demo city |
| 2 | Optional rent data, growth signals and snapshot | CSV import for rent and price, geocoding, estimates, OSM growth signals, offline snapshot | §4, §12 (adapted) | 1 | Rent per cell where data exists, growth signal, snapshot |
| 3 | Feature and scoring engine | F1–F9, affluence and tier fit, constraints, ranking, explanations, tests | §5, §6, §7 | 1 (2 for full data) | `scoring/` library and CLI |
| 4 | Backend API | FastAPI service, persistence, async analysis, admin | §10, §11 | 1, 3 | Working `/v1` API |
| 5 | Agents on Nasiko | Wrap components as agents, cards, deploy, router, observability, scheduler | §9, §13 | 2, 3, 4 | 6–7 agents registered and callable |
| 6 | Streamlit app | Owner screens, admin screens, map, packaging | §14, §15 (adapted) | 4 (5 for chat) | Usable UI |
| 7 | Validation and tuning | Back-test, sensitivity, tuned weights | §21 (adapted) | 3, 4 | Numbers for the pitch |
| 8 | Polish, hardening and demo | Feature completion, offline mode, e2e, cost audit, docs, rehearsal | §20, §23 | all | Demo-ready system |

Phases 2 and 3 can overlap once Phase 1 finishes: scoring can be built against OSM-only features while the optional rent CSV work continues.

---

## Phase 0: Setup, verification and decisions

**Goal:** know what actually works before building on it. Resolve every **[VERIFY]** item that blocks later phases, with special attention to Nasiko plus a free LLM.
**Exit criteria:** Nasiko running with a hello-world A2A agent reachable through its proxy; the LLM route (Ollama primary, OpenRouter backup) proven with Nasiko; free data sources confirmed for the demo city; every decision that gates Phase 1 answered; repo scaffolded with quality tooling; a written free-stack inventory showing no paid dependency.

### Part 0.1: Decisions and hackathon rules
- **0.1.1** Confirm the remaining hackathon rules: whether pre-building is allowed, whether the theme is fixed, what counts as "using" Nasiko (§24). The owner has already answered that Anakin and DronaHQ are optional.
- **0.1.2** Demo city: Bengaluru first, Mumbai only if time remains (owner's choice). Spot-check Bengaluru's OSM coverage before committing (§1.6, §24).
- **0.1.3** Choose the first category to build end to end (cafe or clothing) (§20).
- **0.1.4** Choose the Ollama model id(s). This machine has 23.7 GB RAM and an RTX 3050 with 6 GB, and Ollama already holds several local models. Keep OpenRouter free as backup (D-03).
- **0.1.5** Work through the remaining open decisions in the Decision Log until each is answered or explicitly deferred.
- **0.1.6** Hold two real conversations (one aspiring owner, one broker or franchise person) to validate the buyer hypotheses (§1.4).

### Part 0.2: Accounts, keys and tooling
- **0.2.1** Create the OpenRouter free-tier key for the backup route (no Anakin or DronaHQ accounts are needed).
- **0.2.2** Install and verify the toolchain. Already present: Docker 29.7.2 with Compose v5.5.0 (engine not running), git 2.49, Node 22, Ollama 0.34.2, Python 3.11.9 (the owner chose to use it, D-27). Still needed: the Docker Desktop engine running, a project virtual environment with pip (`uv` is optional), and Rust 1.85+ only if the `nasiko` CLI is installed from source later (D-26). `make` is not needed because Nasiko uses `docker compose`.
- **0.2.3** Establish secret handling: `.env` local only, `.env.example` committed, `.gitignore` covers secrets and `data/raw`.

### Part 0.3: Nasiko feasibility (compulsory platform)
- **0.3.1** Review the installed Nasiko at `D:\Projects\Nasiko` read-only: locate it, record version and layout, compare with §13 (result in §2.4).
- **0.3.2** Create `D:\Projects\Nasiko\.env` (owner approved; done 2026-09-20 with generated secrets and the Ollama route, no paid key). Remaining: a real free OpenRouter key for the backup route if the owner wants one, since the old file only held a placeholder (D-26).
- **0.3.3** Start the Docker Desktop engine, run `docker compose up -d` in the Nasiko folder, open `http://localhost:8080` and log in as admin.
- **0.3.4** Use the Nasiko dashboard to deploy and test agents for now (owner's choice). The `nasiko` CLI stays optional; it is not installed and building it needs Rust 1.85+ (D-26).
- **0.3.5** Hello-world agent: start from a template in `D:\Projects\Nasiko\agents\` (or `nasiko new` if the CLI is installed), upload it through the dashboard and chat with it there; inspect its A2A Agent Card and make a scripted `SendMessage` call through Nasiko's proxy.
- **0.3.6** LLM route: run `nasiko llm-config providers`; create an OpenRouter free-model config and attach it to the hello-world agent; then test Ollama through an OpenAI-compatible base URL (`OPENAI_BASE_URL` in `.env`) and record what works (D-03).
- **0.3.7** Routing engine: confirm which chat and embedding models it needs (`ROUTER_MODEL`, `EMBEDDING_MODEL`), that free options work, and how well routing performs with them.
- **0.3.8** Backend to Nasiko: how our backend authenticates and calls agents; access-control and flow-guard defaults; how new agents appear in the routing engine.
- **0.3.9** Record findings and Windows and Docker networking notes; update the Decision Log.

### Part 0.4: Free LLM feasibility
- **0.4.1** Pull the candidate Ollama model(s) and measure RAM use and latency on this machine.
- **0.4.2** Check structured-JSON reliability with the listing-free tasks we need (tier classification, narrative from JSON).
- **0.4.3** Check that a container on the Nasiko agent network can reach Ollama on the host.
- **0.4.4** Test the OpenRouter free backup and note rate limits and model availability.
- **0.4.5** Decide the primary and backup model ids; record in the Decision Log.

### Part 0.5: Free data and UI feasibility
- **0.5.1** Confirm Overpass responds for Bengaluru and spot-check OSM coverage (markets, colleges, hospitals, offices).
- **0.5.2** Confirm the population source is downloadable for the city (WorldPop or Census).
- **0.5.3** Confirm Nominatim or Photon usage terms allow our low-volume use.
- **0.5.4** Streamlit spike: a hello page that draws H3 hexagons coloured by a dummy score with folium or pydeck and reacts to a click.
- **0.5.5** Write the free-stack inventory: every dependency, image, model and service with its licence and cost; confirm none is paid.

### Part 0.6: Repository scaffolding and engineering standards
- **0.6.1** Agree the repo root and create the folder layout of §17, adapted: `frontend/streamlit_app/` replaces `dronahq/` and `frontend/map_embed/` (G-DEVIATE); empty packages only.
- **0.6.2** Configure ruff, mypy, pytest and pre-commit.
- **0.6.3** Create `.env.example` (§18, without Anakin variables, with Nasiko's base URL `http://localhost:8080`) and `.gitignore`.
- **0.6.4** Write short engineering conventions (logging fields, error envelope, module boundaries).
- **0.6.5** Decide whether to `git init` here (the folder is not a git repository today); if yes, make the first local commit.
- **0.6.6** Write the Phase-0 go/no-go report and update the Decision Log.

---

## Phase 1: Data foundation

**Goal:** a versioned database, the config layer, a populated grid of cells and POIs for the demo city, and a shared LLM client.
**Exit criteria:** cells, POIs, land use, residential and road attributes stored; ingestion is idempotent and tested; a data QA report exists; the LLM client works with both providers; every DB action was approved (G-DB).

### Part 1.1: Database schema and migrations *(G-DB on every step that touches a database)*
- **1.1.1** Provision PostGIS (`postgis/postgis:16-3.4`) via docker compose, after approval of where it runs. Check port conflicts with Nasiko's own Postgres, and never use or touch Nasiko's databases.
- **1.1.2** Set up Alembic and the SQLAlchemy base.
- **1.1.3** Write the initial migration from the §8.2 DDL. The user reviews the SQL before it is applied. The Anakin-specific parts (`scrape_jobs.anakin_job_id`, `credits_used`, Anakin source names) are shown with a proposed simplification for approval (D-24, G-DEVIATE).
- **1.1.4** Apply the migration after explicit approval; verify tables, indexes and PostGIS extension.
- **1.1.5** Write typed models and repositories matching the approved schema.
- **1.1.6** Write idempotent upsert helpers keyed on natural keys (`osm_type+osm_id`, `h3_index`, listing key).

### Part 1.2: Configuration layer
- **1.2.1** Write `config/osm_tags.yaml` from Appendix A.
- **1.2.2** Write `config/categories/{cafe,clothing,pharmacy}.yaml` from Appendix B, §5.3 and §5.6; values exactly as documented until D-22 is decided. Tier labels shown to users are lower class, medium class and niche, mapped to the internal ids `budget`, `mid`, `premium` (D-28).
- **1.2.3** Write `config/brands_premium.yaml`; the brand content is provided or approved by the owner.
- **1.2.4** Build a Pydantic config loader and validator (weights sum to 1.0, known feature keys, tier targets in 0..1).
- **1.2.5** Sync configs into `category_configs` *(G-DB)*.

### Part 1.3: City and H3 grid
- **1.3.1** Create the city record and obtain the city boundary and bbox.
- **1.3.2** Generate H3 res-9 cells covering the boundary.
- **1.3.3** Assign `locality_name` from OSM suburb polygons.
- **1.3.4** Persist cells with centroid and boundary *(G-DB)*.

### Part 1.4: OSM POI ingestion
- **1.4.1** Overpass client with timeout, retry, caching and rate-limit respect (§Appendix C). Bengaluru is large, so the client fetches by bounding-box tiles; if the public server is too slow or rate-limits us, fall back to a free Karnataka extract from Geofabrik loaded locally (D-29).
- **1.4.2** Query builder that groups tags per call from `osm_tags.yaml`.
- **1.4.3** Normalise OSM elements (nodes and way centres) to internal categories, including hotel star handling.
- **1.4.4** Assign each POI to its H3 cell.
- **1.4.5** Upsert POIs *(G-DB)*.
- **1.4.6** OSM coverage sanity check per area (feeds `poi_coverage` confidence, §4.5).

### Part 1.5: Land use, buildings, population and roads
- **1.5.1** Classify land use per cell (residential, commercial, mixed, other).
- **1.5.2** Compute residential building density and apartment share.
- **1.5.3** Ingest population density from the chosen free source (D-06).
- **1.5.4** Extract road class, distance to main road, transit stops and parking presence (inputs to F7).

### Part 1.6: Geo-data pipeline and QA
- **1.6.1** `pipelines/ingest_city.py` covering §4.4 steps 1–3.
- **1.6.2** Idempotency test: two runs produce identical row counts.
- **1.6.3** Data QA report: counts per category and per cell, spot checks against areas the owner knows.
- **1.6.4** Unit and integration tests with fixture Overpass responses.

### Part 1.7: Shared LLM client
- **1.7.1** Provider abstraction selected by environment: Ollama primary, OpenRouter free as backup, both through an OpenAI-compatible interface. Inside Nasiko agents the base URL is Nasiko's LLM Router (no real key in the agent); outside agents (backend, pipelines) the client talks to Ollama or OpenRouter directly.
- **1.7.2** Strict-JSON output helper with Pydantic validation, bounded retries and timeouts.
- **1.7.3** Automatic fallback from primary to backup with the failure logged.
- **1.7.4** Tests with mocked providers (no network).

---

## Phase 2: Optional rent data, growth signals and snapshot

**Goal:** rent and price signals where the owner can supply them, an OSM-based growth signal, and a snapshot dataset so the demo runs offline. No scraping and no paid service.
**Exit criteria:** the CSV importer works and rejects bad rows; per-cell rent and locality price stored with estimated flags (or shown as missing when no CSV exists); growth signal stored; snapshot loads and works with the network off.

### Part 2.1: Optional rent and price CSV import
- **2.1.1** Define the CSV template and schema (rent or sale, property type, price, period, area, locality, optional coordinates, source note); no personal data columns.
- **2.1.2** Owner supplies a CSV for the demo city, or confirms the MVP runs without one (owner input).
- **2.1.3** Validation and cleaning: Pydantic rows; reject area under 50 or over 20,000 sq ft; reject prices beyond 5 standard deviations of the locality median; dedupe.
- **2.1.4** Importer CLI with a `--dry-run` that writes nothing and prints a report.
- **2.1.5** Persist listings *(G-DB)*.

### Part 2.2: Geocoding and cell assignment
- **2.2.1** Geocoder client (Nominatim or Photon, D-08) with cache and about 1 request per second.
- **2.2.2** Store `geo_precision` as `exact` or `locality`.
- **2.2.3** Assign listings to H3 cells and report unassignable rows.

### Part 2.3: Rent and price estimation
- **2.3.1** Cell rent: own listings if 3 or more, otherwise inverse-distance-weighted k-ring average, with `rent_is_estimated` set.
- **2.3.2** Assign locality-level residential price to all cells in the locality.
- **2.3.3** Compute `listing_coverage` and `price_coverage`.
- **2.3.4** Explicit "no rent data" state: the value stays null and is labelled missing, never invented.

### Part 2.4: Growth signals from OSM *(proposed, D-21)*
- **2.4.1** Fetch OSM `construction`, `proposed` and related tags (new malls, stations, large residential projects) for the city.
- **2.4.2** Optional curated notes file (`config/area_notes.yaml`) the owner can write; each note carries a source and date.
- **2.4.3** Map signals to cells and localities (input to F9).
- **2.4.4** Persist to `market_intel` with sources *(G-DB)*.

### Part 2.5: Snapshot dataset
- **2.5.1** Define and export `data/snapshots/{city}_{yyyy-mm}.json`.
- **2.5.2** `scripts/seed_demo.py` to load the snapshot *(G-DB)*.
- **2.5.3** Verify the demo path works with the network off.

---

## Phase 3: Feature and scoring engine

**Goal:** a deterministic, tested, config-driven scoring library that works on OSM-only data and improves when a rent CSV exists.
**Exit criteria:** F1–F9 computed; ranking and explanations produced; formulas match the architecture except where the owner approved a change under D-22; property tests pass; worked example within tolerance; CLI works.

### Part 3.1: Foundations
- **3.1.1** Create `scoring/` (pure, typed functions): `features.py`, `tier_fit.py`, `score.py`.
- **3.1.2** Percentile normalisation within city and inversion of negative features.
- **3.1.3** Bind category config (weights, `poi_weights`, catchment k, decay lambda, answer modifiers).

### Part 3.2: Demand and cluster features (F1, F3, F4)
- **3.2.1** F1 `anchor_footfall` with distance decay and per-category lambda (§5.2).
- **3.2.2** F3 `residential_demand` from population and building density.
- **3.2.3** F4 `retail_cluster` (same-category and complementary shops).
- **3.2.4** Apply questionnaire `answer_modifiers` (e.g. students multiply college weight).

### Part 3.3: Affluence and tier fit (F2)
- **3.3.1** `premium_poi_density` from OSM tags and the premium-brand list.
- **3.3.2** Affluence index. With rent CSV data it uses the §5.3 formula; without it, the owner-approved variant from D-22 is used.
- **3.3.3** Tier fit with shortfall and overshoot penalties.

### Part 3.4: Competition, gap and rent efficiency (F5, F6, F8)
- **3.4.1** Competitor `tier_guess` in this order: brand list, area affluence, optional small-LLM classification through the shared client (Google Places is dropped).
- **3.4.2** F5 supply with tier weights (1.0 / 0.5 / 0.2), inverted when scored.
- **3.4.3** F6 `gap_opportunity` (demand over supply plus 0.5, percentile).
- **3.4.4** F8 `rent_efficiency` when rent exists; the fallback when it does not is decided under D-22.

### Part 3.5: Accessibility and growth (F7, F9)
- **3.5.1** F7 from road class, main-road distance, transit stops and parking.
- **3.5.2** F9 from the OSM growth signal and curated notes (D-21); neutral value when there is no signal, flagged in confidence.

### Part 3.6: Accuracy boosters
- **3.6.1** Day-part profile (#7), age-skew proxy (#16), medical ecosystem density (#17). How they enter the score is decision D-19.
- **3.6.2** The rent budget hard filter (#12) and vacancy listings (#13) apply only where rent data exists; handled in 3.7 and Phase 4.
- **3.6.3** Optional boosters only if approved under D-18: parking (#9), late-night (#15), seasonality (#14). Isochrones (#4) are proposed out of the MVP.

### Part 3.7: Constraints, ranking and explanations
- **3.7.1** Hard filters: rent limit (1.2 × budget) where rent data exists, residential-only exclusion (pharmacy exception, flagged), confidence below 0.25 shown greyed and unranked.
- **3.7.2** Score and per-feature `contributions`.
- **3.7.3** Confidence formula (§5.7), with the missing-data handling decided under D-22.
- **3.7.4** Top 3 drivers and top 2 risks, from templates rather than an LLM.
- **3.7.5** Rank and `top_n`; merge adjacent high-scoring cells into named zones (§4.3).
- **3.7.6** `NO_CANDIDATES` behaviour with the cheapest 3 zones and their rent when rent data exists (§15.2).

### Part 3.8: Feature build pipeline
- **3.8.1** `pipelines/build_features.py` writing `cell_features` *(G-DB)*.
- **3.8.2** `feature_version`, `data_freshness` and confidence handling.

### Part 3.9: Tests and CLI
- **3.9.1** Tests: weights sum to 1.0 for every config; contributions sum to score; score in [0, 100]; premium tier lowers scores in low-affluence cells; worked example §5.8 within tolerance.
- **3.9.2** Hypothesis property tests for monotonicity and bounds.
- **3.9.3** CLI that scores from `cell_features` or the snapshot.
- **3.9.4** Category-awareness check: the same location gives different scores for the three categories.
- **3.9.5** OSM-only mode test: scoring works end to end with no rent data and labels what is missing.

---

## Phase 4: Backend API

**Goal:** the FastAPI service from §10, with async analyses, persistence, admin and standard errors, free of any paid dependency.
**Exit criteria:** every endpoint in §10.1 implemented and tested; end-to-end analysis works from snapshot data; container runs.

### Part 4.1: Application skeleton
- **4.1.1** App factory, settings via environment, structured JSON logging with request IDs.
- **4.1.2** Auth: `X-API-Key` check (shared with the Streamlit app) and `X-User-Id` propagation; user upsert by `external_id`.
- **4.1.3** CORS from `ALLOWED_ORIGINS`.

### Part 4.2: Persistence layer
- **4.2.1** Session and transaction management.
- **4.2.2** Repositories for cities, cells, features, analyses, recommendations, jobs, configs.

### Part 4.3: Schemas and errors
- **4.3.1** Pydantic request and response models (§10.2, §10.3).
- **4.3.2** Error envelope and codes `INVALID_INPUT`, `CITY_NOT_READY`, `NO_CANDIDATES`, `UPSTREAM_TIMEOUT`, `INTERNAL`.

### Part 4.4: Meta endpoints
- **4.4.1** `GET /health` (liveness and versions).
- **4.4.2** `GET /cities` (ready only).
- **4.4.3** `GET /categories` (tiers, questions, labels from config).

### Part 4.5: Analysis lifecycle
- **4.5.1** `POST /analyses`: validate, insert as queued, return immediately *(G-DB at first real run)*.
- **4.5.2** Async pipeline runner: load features, score, generate narratives, mark done; failures recorded.
- **4.5.3** `GET /analyses/{id}` status and summary.
- **4.5.4** `GET /analyses/{id}/recommendations` with GeoJSON option, nearby listings (when a CSV exists) and data notes.
- **4.5.5** `GET /analyses/{id}/zones/{rank}` detail.
- **4.5.6** Fallback to the last good snapshot with its date when an upstream step fails (§15.2).

### Part 4.6: Analysis extras
- **4.6.1** `POST /analyses/{id}/compare` for 2–3 zones.
- **4.6.2** `POST /analyses/{id}/what-if` (tier, budget, size, category) with rank-change output.
- **4.6.3** `POST /chat` (wired to Nasiko in Phase 5).
- **4.6.4** `GET /analyses/{id}/report.pdf` with WeasyPrint (D-10).

### Part 4.7: Admin endpoints
- **4.7.1** `POST /admin/cities/{id}/ingest`.
- **4.7.2** `GET /admin/jobs` (ingestion jobs and errors) and `GET /admin/data-freshness`.
- **4.7.3** `PUT /admin/configs/{category}` creating a new version, with weight-sum validation *(G-DB)*.
- **4.7.4** Admin role enforcement.

### Part 4.8: Hardening
- **4.8.1** Rate limiting and request size limits.
- **4.8.2** Timeouts and retry policy for outbound calls.
- **4.8.3** Input validation edge cases (unknown city, tier not offered for category, budget or size unrealistic).

### Part 4.9: Tests and packaging
- **4.9.1** Unit and API tests with a dedicated test database (its provisioning is approved separately under G-DB).
- **4.9.2** Backend Dockerfile and compose service (§19.2). Migrations are never auto-run at startup.
- **4.9.3** `scripts/smoke_test.sh` and sample request payloads (§19.4).

---

## Phase 5: Agents on Nasiko

**Goal:** the pipeline components run as containerized A2A v1.0 agents deployed on the installed Nasiko, reached through its proxy and routing engine, using the free LLM route.
**Exit criteria:** all agents uploaded and callable; router picks the right agent for sample chat queries; traces visible; scheduler runs refreshes.

### Part 5.1: Agent framework
- **5.1.1** Shared agent base built from a Nasiko template (`nasiko new` if the CLI is installed, otherwise a copy of a template from `D:\Projects\Nasiko\agents\`): an A2A v1.0 JSON-RPC server with an Agent Card and `SendMessage`, carrying Pydantic-validated JSON payloads and the response envelope (`agent`, `version`, `latency_ms`, `warnings[]`).
- **5.1.2** Secrets only through Nasiko's encrypted per-agent secrets (`nasiko secrets set`) or environment; minimal variables per agent.
- **5.1.3** Reuse the shared LLM client (1.7) inside agents through Nasiko's LLM Router (`OPENAI_BASE_URL` plus an identity token), using the provider and model set with `nasiko llm-config`.
- **5.1.4** Network path: agent containers can reach our PostGIS (and the backend where needed); Nasiko's own databases are never used or touched.

### Part 5.2: Data-side agents
- **5.2.1** `geo-data` (wraps the Phase 1 pipeline).
- **5.2.2** `listings` (wraps CSV import, geocoding and rent estimation; there is no scraping).
- **5.2.3** `market-intel` (answers growth and area questions from OSM construction data and curated notes, cited, with no live web search). The agent name is kept from the architecture; its description changes (D-21).
- **5.2.4** `affluence` (affluence, competitor tiers, rent estimates and smoothing).

### Part 5.3: Analysis-side agents
- **5.3.1** `scoring` (wraps the `scoring/` library; rank, explain, what-if, compare).
- **5.3.2** `report-chat`: narratives, follow-ups, what-if, PDF hook.
- **5.3.3** Narrative guardrails: structured JSON only, 3–5 sentences, post-check that every number appears in the input, one regeneration (Appendix F). Extra care because the primary model is small and local.
- **5.3.4** `orchestrator` runs the fixed pipeline with retries. Whether it is a Nasiko agent or lives inside the backend is decision D-04.

### Part 5.4: Cards and containers
- **5.4.1** A2A Agent Card per agent with skill descriptions the routing engine can match (shortlist, rerank, select).
- **5.4.2** Dockerfile, compose file and `sample_request.json` per agent.

### Part 5.5: Deploy and routing
- **5.5.1** Deploy each agent with the `nasiko` CLI (`deploy` or `upload`) or the dashboard; confirm whether the routing engine sees new agents immediately or needs a refresh.
- **5.5.2** Verify direct A2A calls to each agent through Nasiko's proxy (dashboard chat or `nasiko chat --agent ...`, and a scripted `SendMessage`).
- **5.5.3** Verify router selection for sample questions (explanations go to `report-chat`, area and growth questions to `market-intel`), with the local model and with the backup.
- **5.5.4** Configure access control and flow guards so backend-to-agent and orchestrator-to-agent calls are allowed, and depth, fan-out and token limits fit the pipeline.

### Part 5.6: Backend integration
- **5.6.1** `nasiko_client` service in the backend that authenticates to Nasiko and sends A2A `SendMessage` calls.
- **5.6.2** Record every agent call in `agent_runs` (latency, tokens, trace ID; cost is zero) *(G-DB)*.
- **5.6.3** Connect `/chat` to the router; return the routed agent's answer with sources or an explicit "not available".

### Part 5.7: Scheduler
- **5.7.1** APScheduler job for OSM refresh following the freshness policy (POIs monthly). Rent CSV updates are manual.
- **5.7.2** Staleness marking (`stale` city status after the window).

### Part 5.8: Observability
- **5.8.1** Confirm one OpenTelemetry trace per agent call in the Nasiko dashboard and with `nasiko observe` (Tempo and Loki replace the Phoenix mentioned in the architecture).
- **5.8.2** Token and latency tracking per analysis.

---

## Phase 6: Streamlit app

**Goal:** the owner and admin interface of §14 as a Streamlit app that holds no business logic and only calls the backend.
**Exit criteria:** owner flow (wizard to export) and admin screens work against the backend; edge-case states implemented; the app runs from Docker Compose.

### Part 6.1: App skeleton and backend client
- **6.1.1** Multipage Streamlit app layout under `frontend/streamlit_app/`.
- **6.1.2** Typed backend client with `X-API-Key` and `X-User-Id` headers, timeouts and error mapping to friendly messages. The key stays on the server side of Streamlit.
- **6.1.3** Users and roles for the MVP (`owner`, `admin`) as decided in D-23.
- **6.1.4** Configuration through environment variables.

### Part 6.2: Owner screens
- **6.2.1** Screen 1 "My analyses" table.
- **6.2.2** Screen 2 wizard (4 steps), with tier and category questions loaded from `/categories`.
- **6.2.3** Progress state that polls the backend until the analysis is done.
- **6.2.4** Screen 3 results: map, ranked table, KPI tiles, layer toggles, filters for confidence and (where available) rent.
- **6.2.5** Screen 4 zone detail with 7 tabs (overview, score breakdown, landmarks, spending power, competition, rent and listings when data exists, risks and checklist).
- **6.2.6** Screen 5 compare zones.
- **6.2.7** Screen 6 what-if panel.
- **6.2.8** Screen 7 chat (Streamlit chat components) backed by `/chat`.
- **6.2.9** Screen 8 export.

### Part 6.3: Admin screens
- **6.3.1** Data and jobs (city table, ingestion jobs, freshness, ingest and refresh buttons).
- **6.3.2** Weights editor (live sum check, save as new version, set active, last back-test result).
- **6.3.3** System health (agent status, latency and error rate, link to the Nasiko dashboard).

### Part 6.4: Map
- **6.4.1** Choose the map library from the Phase-0 spike (folium via `streamlit-folium`, or pydeck).
- **6.4.2** Hex overlay coloured by score with legend, top-10 pins and layer toggles (landmarks, competitors, listings).
- **6.4.3** Click a hex or pin to select a zone and show its summary.

### Part 6.5: Packaging and access
- **6.5.1** Streamlit Dockerfile and compose service.
- **6.5.2** Network layout: only Streamlit is exposed to the user; the backend and the Nasiko gateway stay private.
- **6.5.3** Only if remote access is needed and the owner approves: a free tunnel (Cloudflare Tunnel) to Streamlit only (D-12).

### Part 6.6: UX states
- **6.6.1** City not ready, `NO_CANDIDATES`, low-confidence warning, tier-area mismatch reason, out-of-scope chat, upstream failure with snapshot date (§15.2).
- **6.6.2** Data-source caveats on every result, including "rent data not available for this city" when there is no CSV.

### Part 6.7: Documentation
- **6.7.1** Screenshots and a short README for the app in `frontend/streamlit_app/`.

---

## Phase 7: Validation and tuning

**Goal:** evidence that the model behaves sensibly, and honest numbers for the pitch.
**Exit criteria:** back-test and sensitivity results recorded; any weight change approved and versioned.

### Part 7.1: Back-test dataset
- **7.1.1** Owner supplies about 10 known places per category (§21.1): busy markets, dense residential streets, mixed areas.
- **7.1.2** Store cases with expected order in `data/backtest/`.

### Part 7.2: Back-test run
- **7.2.1** `scripts/backtest.py` producing top-3 hit rate and pass/fail per case.
- **7.2.2** Repeat for cafe and pharmacy expectations.

### Part 7.3: Popularity correlation (optional)
- **7.3.1** Only if the owner supplies shop popularity data: Spearman correlation between cell score and popularity, excluding each shop from its own competition feature. Otherwise skipped and stated as a limitation (D-07).

### Part 7.4: Sensitivity and stability
- **7.4.1** Perturb weights by ±20 percent and report top-10 change.
- **7.4.2** Tier-change direction checks.

### Part 7.5: Tuning
- **7.5.1** Propose weight changes with evidence; the owner approves; save as a new config version (G-DB, G-DEVIATE).
- **7.5.2** Re-run the back-test and record the result per version.

### Part 7.6: Metrics
- **7.6.1** Record top-3 hit rate, average confidence of top 10 and end-to-end latency (and Spearman if 7.3 ran) for the slide.

---

## Phase 8: Polish, hardening and demo

**Goal:** demo-ready and production-grade end to end, provably free, with Nasiko visibly central.
**Exit criteria:** definition of done (§20.1, adapted) and success criteria (§1.7, adapted) verified; demo runs from snapshot with the network off; cost audit shows zero paid services.

### Part 8.1: Feature completion
- **8.1.1** Verify compare, what-if, chat and PDF across all three categories.
- **8.1.2** Verify the demo checks in §1.7 (30-second result, clothing example, category difference, tier effect, back-test).
- **8.1.3** Nasiko showcase check: every agent appears in the Nasiko dashboard, traces are visible, and the router is demonstrated on a chat question.

### Part 8.2: Offline and resilience
- **8.2.1** Demo mode entirely from the snapshot.
- **8.2.2** Failure drills: Ollama down (fall back to OpenRouter), Overpass unavailable (snapshot), an agent down.

### Part 8.3: End-to-end and performance
- **8.3.1** Automated end-to-end test of the smoke path.
- **8.3.2** Latency measurement against the 30-second target, including local-LLM narrative time.

### Part 8.4: Documentation
- **8.4.1** README with setup (§19.3, adapted), run and test instructions.
- **8.4.2** Runbook: refresh procedures, CSV import, troubleshooting.
- **8.4.3** Any correction to `architecture-1.md` is proposed to the owner first (G-EDIT).

### Part 8.5: Final quality pass and cost audit
- **8.5.1** ruff, mypy and full pytest run clean.
- **8.5.2** Secret scan; confirm `.env` and raw data are not committed.
- **8.5.3** Dependency and container review.
- **8.5.4** Cost audit: re-run the free-stack inventory from 0.5.5 and confirm no paid service, plan or credit-limited API is in the path.

### Part 8.6: Demo
- **8.6.1** Rehearse the 5-minute script (§23, adapted: no Anakin or DronaHQ segments).
- **8.6.2** Prepare slides: problem, limitations statement (§21.5), back-test numbers, roadmap.
- **8.6.3** Backup plan: recorded run and snapshot.

### Part 8.7: Stretch: Mumbai (only if time remains)
- **8.7.1** Owner confirms that time remains and Mumbai goes ahead.
- **8.7.2** Run the same ingestion pipeline for Mumbai (configuration only, no code change), with the tiled Overpass fetch, the QA report and a snapshot.
- **8.7.3** Add Mumbai back-test cases from the owner, enable the city in the wizard and check scores for all three categories.

### Part 8.8: Sign-off
- **8.8.1** Check every item of §20.1 and §1.7 (adapted) for Bengaluru, and for Mumbai only if it was done; list gaps.

---

## 6. Priority cuts (from §20, applied only if approved)

If time is short, in this order: growth momentum (F9), compare screen, PDF; keep one category polished and configure the other two with weights only. Isochrones are already outside the MVP.

## 7. Out of scope for this build

Anakin and DronaHQ integrations (may return later as optional, pluggable extras), Google Places, isochrones, live web search, and the roadmap in §25 (more categories, multi-city, real footfall data, outcome feedback loop, WhatsApp, voice assistant, wholesaler comparison, monetisation), plus the non-goals in §1.5.

## 8. Change control

Any change to this plan is made only with the owner's approval and recorded in the change log at the end of `progress.md`.

---

## 9. Parallel work split (two Claude agents)

Two Claude sessions work at the same time on the same machine and folder (owner confirmed 2026-09-20). **Agent A** is the session that wrote this plan. **Agent B** is the second session. Both follow the working rules in §1 and the gates in §3.

### 9.1 What is independent

| Phase | Independent of the others? | Who | Notes |
|---|---|---|---|
| 0 Setup and verification | Mostly A | A | Nasiko, Ollama, Overpass, decisions, scaffold. Only the Streamlit map spike (0.5.4) goes to B. |
| 1 Data foundation | **Splits cleanly** | A: 1.1, 1.2.1, 1.2.5, 1.3–1.6. B: 1.2.2–1.2.4, 1.7 | B's parts need no database and no network. |
| 2 Rent, growth, snapshot | **Splits cleanly** | B: 2.1.1–2.1.4, 2.2.1–2.2.2, 2.3 (pure logic). A: 2.1.5, 2.2.3, 2.4, 2.5 | B's parts are pure functions on data frames. |
| 3 Scoring engine | **Yes, fully** | B: 3.1–3.5, 3.7, 3.9. A: 3.8 | B works against synthetic fixtures. Blocked until the owner answers: 3.3.2 no-rent variant, 3.4.4 fallback, 3.7.3 (D-22, deferred) and 3.6 boosters (D-18, D-19). |
| 4 Backend API | Mostly A | A: everything except below. B: 4.3 (schemas, errors) and 4.6.4 (PDF renderer) | A's endpoint work needs the database (1.1) and B's scoring library. |
| 5 Agents on Nasiko | A | A (report-chat agent may move to B later) | Needs Nasiko, the LLM client, scoring and backend. |
| 6 Streamlit app | **Yes, after 4.3** | B | Built against a stub client that returns fixture JSON, then switched to the real backend. |
| 7 Validation and tuning | Needs data and scoring | B, once A and B are integrated | |
| 8 Polish and demo | Shared | A: 8.2, 8.3, 8.5, 8.7. B: 8.1, 8.4, 8.6 | 8.8 sign-off is joint. |

Rough load: Agent A about 60 percent of the micro-tasks, Agent B about 40 percent. Work is rebalanced when either agent runs out of unblocked tasks (for example, B takes the `report-chat` agent).

### 9.2 Contracts between the two tracks

| Contract | Owner | Consumer | Where |
|---|---|---|---|
| Data-frame and row shapes for cells, POIs, listings, market signals, and the `CellFeatures` output | B defines, A reviews | A writes database loaders that produce exactly these | `shared/contracts.py` |
| Category config format and loader | B | A (`/categories`, ingestion), agents | `config/categories/*.yaml`, `shared/config.py` |
| LLM client (Ollama primary, OpenRouter backup) | B | A (agents, backend) | `shared/llm/` |
| API request and response schemas, error envelope | B | A (backend), B (Streamlit) | `backend/app/schemas/` |
| Scoring library | B | A (pipeline runner, agents) | `scoring/` |

### 9.3 Folder ownership (no two agents edit the same file)

| Agent | Owns |
|---|---|
| **A** | `backend/` except the two B items, `agents/`, `pipelines/` except `pipelines/rent_data/`, `config/osm_tags.yaml`, `config/area_notes.yaml`, `data/raw/`, `data/snapshots/`, `tests/pipelines/`, `backend/tests/`, `scripts/` except `backtest.py`, Docker and compose files, database migrations |
| **B** | `scoring/`, `shared/`, `backend/app/schemas/`, `backend/app/services/report_pdf.py`, `pipelines/rent_data/`, `config/categories/`, `config/brands_premium.yaml`, `frontend/`, `tests/scoring/`, `tests/shared/`, `scripts/backtest.py`, `data/backtest/` |
| **Shared files** | `plan.md`, `progress.md`, `pyproject.toml`, `requirements/*.txt`, `.gitignore`, `.env.example`, `.pre-commit-config.yaml`. Edit only with small targeted changes, and only your own sections of `progress.md`. |

### 9.4 Coordination rules

1. **One owner per file.** To change a file you do not own, add a row to the Handoffs table in `progress.md` and let its owner do it.
2. **`progress.md`:** tick only your own micro-tasks, with targeted edits. Never rewrite the whole file. Refresh the summary table with `python scripts/update_progress_summary.py` after you finish a batch.
3. **Database:** only Agent A ever connects to a database, and only after the owner approves (gate G-DB). Agent B works on fixtures and never opens a connection. Nasiko's own databases are never touched by anyone.
4. **Nasiko and Docker:** only Agent A operates the Nasiko stack at `D:\Projects\Nasiko`.
5. **Git:** local commits only, no push (rule 5). Each agent stages only its own paths (never `git add -A`), never rewrites history, and prefixes commit subjects with `[A]` or `[B]`.
6. **Dependencies:** each agent adds its own `requirements/<area>.txt`. Adding to `requirements/base.txt` is announced in the Handoffs table. Every package must be free and open source (standard 10).
7. **Decisions and questions for the owner:** either agent may ask the owner in its own chat and must record the question and answer in the Decision Log. Nothing is assumed (rule 6).
8. **Tests:** no network and no database in default test runs; use the `integration` marker for anything that needs them.
9. **Quality:** every change meets the production-grade standards in §4 before it is called done.
