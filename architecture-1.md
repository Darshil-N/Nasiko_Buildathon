# SiteScout: AI Store-Location Advisor

> Working title. Architecture and build guide for a hackathon project built on **Anakin**, **Nasiko** and **DronaHQ**.
> Draft v0.1, 20 Sep 2026. Everything marked **[VERIFY]** is an assumption to confirm before building.

---

## Table of contents

1. Product overview
2. The three platforms and their roles
3. System architecture
4. Data sources and collection
5. Feature engineering and scoring engine (the core)
6. Accuracy boosters (extra signals)
7. Store tiers ("how premium") and the questionnaire
8. Data model (PostgreSQL + PostGIS)
9. Agents (registered on Nasiko)
10. Backend API specification
11. Data flow and sequence diagrams
12. Anakin integration details
13. Nasiko integration details
14. DronaHQ app: screens, dashboards, wireframes
15. User flows
16. Tech stack
17. Repository structure
18. Environment variables and configuration
19. Deployment and local setup
20. Build plan (hackathon timeline)
21. Validation and back-testing
22. Risks, legal and limitations
23. Demo script
24. Open questions to verify
25. Roadmap
26. Appendix (OSM tags, configs, code samples)

---

## 1. Product overview

### 1.1 Problem

Opening a store in the wrong place is the most expensive and least reversible decision a new retailer makes: lease deposit, interiors and inventory are all sunk before the first sale. Owners today decide by gut feeling, a broker's advice and walking around. Existing tools are either generic population maps (which ignore what each business type actually needs) or expensive consulting reports.

### 1.2 Solution

The user enters a **city**, a **business category** (clothing store, cafe, pharmacy), a **tier** (how premium the store will be) and a few constraints (rent budget, shop size). SiteScout ranks candidate zones and explains each ranking with evidence: nearby landmarks, area spending power, competition, rent, accessibility and growth signals. It also shows real commercial listings currently available in or near the top zones.

### 1.3 Core insight: the scoring must be category-aware

A dense residential block has many people but few clothing buyers. Clothing is comparison shopping, so shops cluster in markets and shoppers travel to them. A grocery store or pharmacy is the opposite: it wants residential streets and short walks. A cafe wants offices, colleges and pass-by traffic. So the same location scores differently per category, and "more people nearby" is never the whole answer.

| Signal | Clothing | Cafe | Pharmacy |
|---|---|---|---|
| Existing cluster of same shops | Strong positive | Mild positive | Negative (competition) |
| Residential density | Weak | Weak | Strong positive |
| Colleges / offices | Medium | Strong | Weak |
| Hospitals / clinics | Negligible | Weak | Strong positive |
| Malls / markets | Strong | Medium | Weak |
| Spending power match | Important | Important | Less important |

### 1.4 Who uses it and who pays (hypotheses to validate)

Small existing owners will not pay for information they can look up. Opening a new store is a one-time, high-stakes decision, so the likely buyers are:

- First-time and aspiring store owners (pay per report).
- Franchise brands and chains vetting applicants or planning expansion (subscription).
- Commercial real-estate brokers (lead generation: "which shops suit which businesses").
- Banks and lenders assessing shop-loan applications.

**[VERIFY]** by talking to 2 or 3 real people from these groups before the demo.

### 1.5 Non-goals

- No guarantee of success. Output is decision support, and the owner still visits the site.
- No real footfall counts (no access to mobile or CCTV data). We use proxies.
- Wholesaler comparison, refund voice assistant and other earlier ideas are out of scope (see Roadmap).

### 1.6 Scope of this build

| Item | Value |
|---|---|
| Categories | Clothing store, Cafe, Pharmacy |
| Tiers per category | 3 (budget / regular, mid, premium) |
| Geography for the demo | 1 city (example: Pune), chosen for data availability |
| Candidate unit | H3 hexagon, resolution 9 (about 0.1 km² each) |
| Output | Ranked zones, score breakdown, available listings, narrative report, follow-up chat |

### 1.7 Hackathon success criteria

1. A user completes the wizard and gets a ranked map in under 30 seconds (precomputed city data).
2. The clothing example works: a dense residential area ranks below an established cloth market, with the reason shown.
3. The same location gets different scores for the three categories.
4. Changing tier from regular to premium visibly changes the ranking.
5. Back-test shows the model ranks known good locations above known bad ones (see section 21).
6. All three platforms are visibly used: Anakin (data), Nasiko (agents and routing), DronaHQ (interface).

---

## 2. The three platforms and their roles

| Platform | Role in SiteScout | What we use it for |
|---|---|---|
| **Anakin** (anakin.io) | Web data layer | Scrape commercial-rent and property-price listings, run search and agentic search for market reputation and growth news, optional competitor pages |
| **Nasiko** (Nasiko-Labs/nasiko) | Agent control plane | Registers our agents, routes free-text questions to the right agent, provides gateway and observability |
| **DronaHQ** (dronahq.com/agents) | Interface and workflow layer | Wizard, map and dashboards, admin screens, follow-up chat, PDF export |

### 2.1 What we know about each (from public docs)

**Anakin**
- REST API at `api.anakin.io`. Auth via `X-API-Key` header. Python SDK `anakin-sdk` (import `anakin`), CLI `anakin-cli`.
- Credits: scrape 1, crawl 1 per page, map 1, search 3, agentic search 10 plus 1 per URL read.
- Limits: crawl up to 100 pages per job, map up to 5,000 URLs per request. Free plan 300 credits and 5 concurrent requests (per the pricing page). Rate limits apply to submit endpoints only. A batch of up to 10 URLs uses 1 rate-limit slot.
- Jobs are asynchronous (submit, then poll). The SDK polls for you.
- Wire endpoints cover 940+ sites, mainly e-commerce. **[VERIFY]** whether any Wire endpoint covers property portals or maps. Assume not and use the generic URL scraper.

**Nasiko**
- Agent registry, LangChain-based intelligent router, Kong API gateway (port 9100 locally), OpenTelemetry observability, web UI at `/app/`.
- Agents are containerized, described by an `AgentCard.json`, uploaded with the `nasiko` CLI and reachable through the gateway at `/agents/{name}/...`.
- Router endpoint example from the README: `GET /router/route?query=...`.
- Needs Docker, Python 3.12+, about 4 GB RAM, and an LLM key (OpenRouter or OpenAI) in `.nasiko-local.env`.
- The repository has multiple versions with different internals. **[VERIFY]** endpoints and ports in the version you clone.

**DronaHQ**
- Low-code app builder (forms, dashboards, admin panels, connectors to REST APIs and databases) plus an agentic platform (chat, webhook, voice and data agents, tools, memory, RAG).
- Managed add-ons listed include Database, File Storage and PDF Generator.
- **[VERIFY]** whether it has a native map component. If not, embed a small Leaflet or MapLibre page (see 14.6).

### 2.2 Where LLMs are used, and where they are not

| Task | LLM? | Reason |
|---|---|---|
| Score computation | **No** (plain Python) | Numbers must be reproducible and explainable |
| Feature extraction from OSM | No | Deterministic queries |
| Extract fields from scraped listing pages | Optional (fallback) | Only if Anakin's AI extraction is not enough |
| Classify competitor tier from name and reviews | Yes (small model) | Fuzzy judgement |
| Parse free-text follow-up questions | Yes | Intent and parameters |
| Write the narrative report | Yes | Turns structured JSON into readable text; must not invent numbers |

---

## 3. System architecture

### 3.1 High-level diagram

```mermaid
flowchart LR
  U["Business owner"] --> D["DronaHQ app: wizard, map, dashboards, chat"]
  D -->|"HTTPS + API key"| B["SiteScout Backend API (FastAPI)"]
  B --> DB[("PostgreSQL + PostGIS")]
  B -->|"agent calls via gateway"| N["Nasiko: registry, router, Kong gateway, observability"]
  N --> A1["Geo Data agent"]
  N --> A2["Listings agent"]
  N --> A3["Market Intel agent"]
  N --> A4["Affluence agent"]
  N --> A5["Scoring agent"]
  N --> A6["Report and Chat agent"]
  A1 --> OSM["OpenStreetMap / Overpass"]
  A2 --> AN["Anakin API"]
  A3 --> AN
  AN --> WEB["Property portals, news, public web"]
  A1 --> DB
  A2 --> DB
  A3 --> DB
  A4 --> DB
  A5 --> DB
  A6 --> LLM["LLM provider (OpenRouter / OpenAI / local)"]
  S["Scheduler: refresh jobs"] --> B
```

### 3.2 Layers

| Layer | Components | Responsibility |
|---|---|---|
| Presentation | DronaHQ app (plus optional embedded map page) | Collect inputs, show results, admin |
| API | FastAPI backend | Auth check, create analyses, serve results, orchestrate agents |
| Agents | 6 containerized agents on Nasiko | Data collection, feature building, scoring, reporting |
| Data | PostgreSQL + PostGIS, object storage for raw scrapes | Structured data, raw payload archive |
| External data | OSM, Anakin (property portals, news) | Raw signals |
| Ops | Nasiko observability, scheduler, logs | Tracing, refresh, cost tracking |

### 3.3 Two pipelines

1. **Offline ingestion (per city, run by admin or scheduler).** Build the H3 grid, pull POIs from OSM, scrape listings and prices through Anakin, collect market intel, compute cell features. Takes minutes and uses Anakin credits.
2. **Online analysis (per user request).** Read precomputed cell features, apply category weights and tier fit, apply the user's constraints, rank, attach listings, generate narrative. Should take seconds.

### 3.4 Design principles

1. **Deterministic scoring, LLM for language only.** The LLM never produces a score.
2. **Precompute, then cache.** The demo must never depend on a live scrape.
3. **Config-driven categories.** Adding a category means adding a YAML file (POI weights, feature weights, tier targets), not code.
4. **Explainable output.** Every recommendation carries a per-feature contribution breakdown.
5. **Confidence scoring.** Each zone shows how much data backed it, so thin data is visible.
6. **Honest proxies.** Anything estimated is labelled as estimated.

---

## 4. Data sources and collection

### 4.1 Source matrix

| Data | Source | Method | Refresh | Cost | Risk |
|---|---|---|---|---|---|
| Landmarks and POIs (schools, colleges, malls, hospitals, offices, transit, competitors) | OpenStreetMap via Overpass API | Direct API calls, no scraping | Monthly | Free | Coverage gaps in some areas |
| Road network, walking isochrones | OSM, plus OpenRouteService, Valhalla or OSRM **[VERIFY]** | API or local routing | Monthly | Free tier | Rate limits |
| Commercial rent per sqft | Property portals (99acres, MagicBricks, Housing.com and similar) | Anakin URL scraper on filtered search URLs | Weekly | Anakin credits | Terms of service, anti-bot, listing noise |
| Residential sale price per sqft (spending-power proxy) | Same portals or locality price-trend pages | Anakin URL scraper | Monthly | Anakin credits | Asking prices differ from sale prices |
| Population density | WorldPop gridded data or Census ward data **[VERIFY]** | One-time download | Yearly | Free | Resolution and date |
| Market reputation ("best cloth market in X"), growth news (new mall, metro line) | Web search and news | Anakin search and agentic search | Weekly | Anakin credits | Source quality |
| Competitor popularity (rating, review count, price level) | Google Places API (paid) or scraped listings **[VERIFY]** | API or Anakin | Monthly | Paid or credits | Terms, cost |
| Premium brand list | Curated by us (YAML) | Manual | As needed | Free | Needs upkeep |

### 4.2 Legal and ethical rules for data collection

- Use public pages only. No logins to third-party sites. No personal data (owner names, phone numbers) stored. Drop those fields at extraction time.
- Read each site's terms and robots.txt before scraping. Prefer open data (OSM) wherever it can replace scraping.
- Keep volumes small and cache aggressively.
- Show data sources and "asking price, not transaction price" caveats in the UI.

### 4.3 Spatial unit

- Grid: **H3 resolution 9** cells (about 0.1 km², edge about 175 m). Candidates are cells.
- Catchment: features for a cell are aggregated over the cell plus its **k-ring** neighbours (k depends on category: cafe and pharmacy k=2 for a walkable radius, clothing k=4 for shoppers who travel).
- Upgrade path: replace k-ring with walking isochrones (5 and 10 minutes) for more realism (see section 6).
- Presentation: adjacent high-scoring cells are merged into named **zones** (using OSM suburb polygons) so users see "Koregaon Park, north side" instead of hexagon IDs.

### 4.4 Ingestion steps (per city)

1. Create the city record and bounding box.
2. Generate H3 cells covering the city polygon and store them.
3. Fetch POIs from Overpass by tag groups (Appendix A), normalise to internal categories, assign each POI to a cell.
4. Build the rent and price scrape plan: one search URL per locality per property type. Run through Anakin (batch of 10 URLs per request), store raw markdown or JSON, extract listings, geocode to locality, store.
5. Run market-intel searches per city and per category, store cited summaries.
6. Compute cell features (section 5), including smoothing where data is sparse.
7. Record `data_freshness` and `confidence` per cell. Publish the city as "ready".

### 4.5 Handling sparse or missing data

- **Rents:** if a cell has fewer than 3 listings, use the average of k-ring neighbours (inverse-distance weighted) and mark it `estimated`.
- **Prices:** aggregate at locality level and assign to all cells in that locality.
- **POIs:** if OSM density in an area looks implausibly low (for example zero shops in a known market), lower that cell's confidence.
- **Geocoding of listings:** if a listing has no coordinates, geocode its locality name (Nominatim or Photon, cached, respect usage policy of about 1 request per second **[VERIFY]**). Store `geo_precision` as `exact` or `locality`.

---

## 5. Feature engineering and scoring engine (the core)

### 5.1 Feature list

All features are normalised to 0 to 1 using **percentile rank within the city**. Negative features are inverted (1 minus value) before weighting so that higher is always better.

| ID | Feature | Definition | Source |
|---|---|---|---|
| F1 | `anchor_footfall` | Distance-decayed sum of category-specific landmark weights in catchment | OSM |
| F2 | `affluence_fit` | How well the area's spending power matches the chosen tier (see 5.3) | Portal prices, premium POIs |
| F3 | `residential_demand` | Population or residential building density in catchment | WorldPop / OSM buildings |
| F4 | `retail_cluster` | Density of same-category and complementary shops (market effect) | OSM |
| F5 | `competition_pressure` | Distance-weighted count of same-category shops, extra weight for same tier (inverted when scored) | OSM, tier guesses |
| F6 | `gap_opportunity` | Estimated demand divided by same-tier supply | Derived |
| F7 | `accessibility` | Road class, distance to main road, transit stops within walking distance, parking presence | OSM |
| F8 | `rent_efficiency` | Footfall relative to local rent (value for money) | Listings, F1 |
| F9 | `growth_momentum` | New residential projects, infrastructure and mall announcements | Anakin search |

### 5.2 Landmark footfall (F1)

Landmark weights depend on the category (config in Appendix B). Score for a cell:

```
anchor_raw = sum over POIs p in catchment of ( w[category][type(p)] * exp(-d(cell, p) / lambda[category]) )
```

Suggested `lambda` (metres): cafe 350, pharmacy 300, clothing 600. Then percentile-normalise across cells.

Landmark types and the footfall pattern they imply (also used for the day-part profile in section 6):

| Landmark | Typical crowd | Time pattern |
|---|---|---|
| College / university | Young, price-sensitive | Weekdays, morning to evening |
| School | Parents, children | Drop-off and pick-up times |
| Office cluster / coworking | Working adults, mid to high income | Weekday mornings, lunch, evening |
| Mall / marketplace | Shoppers | Evenings and weekends |
| Hospital / clinic / doctors | Patients, families, all ages | Daytime, some 24x7 |
| Metro / bus / railway station | Commuters | Peak hours |
| Temple / place of worship | Families | Specific days and festivals |
| Cinema, gym, park | Leisure | Evenings and weekends |

### 5.3 Spending power (affluence index) and tier fit (F2)

**Affluence index** (0 to 1, per cell), initial weights to be tuned:

```
affluence = 0.40 * pct(resi_price_per_sqft)
          + 0.15 * pct(resi_rent_per_sqft)
          + 0.30 * pct(premium_poi_density)
          + 0.15 * pct(apartment_share_of_buildings)
```

- `premium_poi_density`: premium brands, car showrooms, fine-dining and 4-5 star hotels within the catchment, from OSM tags, the curated premium-brand list, and (if available) Places price level.
- Property price is the anchor signal because it reflects who can afford to live there.

**Tier fit:**

```
tier_target = { budget: 0.30, mid: 0.55, premium: 0.80 }
short = max(0, tier_target - affluence)      # area poorer than the tier needs
over  = max(0, affluence - tier_target)      # area richer than the tier needs
affluence_fit = clamp(1 - 2.0 * short - 0.8 * over, 0, 1)
```

Meaning: a premium store in a poor area is punished hard. A budget store in a rich area is only mildly punished here (its real penalty appears through higher rent in F8).

### 5.4 Competition and gap (F5, F6)

```
supply(cell)  = sum over competitors c in catchment of ( exp(-d/lambda) * tier_weight(c.tier, user.tier) )
tier_weight   = 1.0 if same tier, 0.5 if adjacent tier, 0.2 otherwise
demand(cell)  = F1_raw * affluence_fit
gap           = pct( demand / (supply + 0.5) )
```

Competitor tier (`tier_guess`) is assigned by, in order: curated brand list, Places price level if available, nearby-area affluence, then an optional small-LLM classification of name and review snippets. Unknown stays `unknown` and counts as adjacent.

Clothing note: same-category shops are also a **positive** cluster signal (F4). The weights below reflect that clothing tolerates competition.

### 5.5 Rent efficiency (F8) and hard constraints

```
rent_efficiency = pct( F1_norm / (rent_norm + 0.1) )
```

Hard filters applied before ranking:

- `estimated_rent_per_sqft * shop_size_sqft > 1.2 * user.monthly_rent_budget` then exclude.
- Residential-only cells (no commercial land use and no commercial listings) are excluded for all categories except pharmacy, where they are kept but flagged for "needs a ground-floor unit".
- Cells with confidence below 0.25 are shown greyed out, not ranked.

### 5.6 Category weight table (initial values, all sum to 1.0)

| Feature | Clothing | Cafe | Pharmacy |
|---|---|---|---|
| F1 anchor_footfall | 0.15 | 0.28 | 0.20 |
| F2 affluence_fit | 0.15 | 0.20 | 0.07 |
| F3 residential_demand | 0.05 | 0.07 | 0.25 |
| F4 retail_cluster | 0.25 | 0.05 | 0.03 |
| F5 competition (inverted) | 0.05 | 0.10 | 0.20 |
| F6 gap_opportunity | 0.10 | 0.10 | 0.10 |
| F7 accessibility | 0.10 | 0.08 | 0.07 |
| F8 rent_efficiency | 0.10 | 0.07 | 0.05 |
| F9 growth_momentum | 0.05 | 0.05 | 0.03 |

These are starting heuristics. They must be tuned with the back-test (section 21) and stated openly as heuristics.

### 5.7 Final score, confidence and explanation

```
score      = 100 * sum(w[i] * f[i])
confidence = 0.4 * poi_coverage + 0.3 * listing_coverage + 0.2 * recency + 0.1 * price_coverage   (each 0..1)
```

Each recommendation stores `contributions[i] = 100 * w[i] * f[i]`, the top 3 positive drivers, the top 2 risks (lowest weighted features), and the confidence. The narrative agent only receives this JSON.

### 5.8 Worked example (clothing store, regular tier, illustrative numbers)

Feature values are already normalised, with F5 shown after inversion (higher = less competition).

| Feature (weight) | Cell A: dense residential, no shops | Cell B: established cloth market plus bus hub |
|---|---|---|
| F1 anchor_footfall (0.15) | 0.30 | 0.85 |
| F2 affluence_fit (0.15) | 0.55 | 0.60 |
| F3 residential_demand (0.05) | 0.95 | 0.60 |
| F4 retail_cluster (0.25) | 0.05 | 0.95 |
| F5 competition, inverted (0.05) | 0.70 | 0.35 |
| F6 gap_opportunity (0.10) | 0.40 | 0.45 |
| F7 accessibility (0.10) | 0.50 | 0.85 |
| F8 rent_efficiency (0.10) | 0.60 | 0.40 |
| F9 growth_momentum (0.05) | 0.40 | 0.50 |
| **Score** | **about 39** | **about 70** |

A naive population-based model would rank A first because it has the most people. Category weights fix that: F4 (market cluster) and F1 (footfall anchors) dominate for clothing. With the pharmacy weights, the same feature values give A about 60 and B about 60, a near tie, because F3 (residential demand) and F5 (low competition) carry the weight there. In practice the pharmacy's F1 would also use hospital-centric landmark weights, so the values would differ.

---

## 6. Accuracy boosters (extra signals)

Beyond landmarks (your item 1) and property prices (your item 2), these make the model more accurate. "Effort" is for a hackathon scale.

| # | Signal | What it adds | Source | Categories | Effort |
|---|---|---|---|---|---|
| 1 | Landmark anchors with distance decay | Type of footfall | OSM | All | Low |
| 2 | Property price and rent per sqft | Spending power | Anakin | All | Medium |
| 3 | Tier-fit scoring | Match store premium level to area | Config | All | Low |
| 4 | Walking isochrone catchments | Realistic reach instead of a circle | OpenRouteService / Valhalla | Cafe, Pharmacy | Medium |
| 5 | Same-tier competitor gap analysis | "Nobody serves premium here" | OSM, Places | All | Medium |
| 6 | Competitor popularity (review count, rating) | Proxy for demand in the area | Places API or scraped | All | Medium |
| 7 | Day-part profile | Does the crowd match opening hours (office = weekdays, mall = evenings) | Derived from POI types | Cafe, Clothing | Low |
| 8 | Road class, visibility, transit access | Pass-by traffic | OSM highway tags | All | Low |
| 9 | Parking availability | Matters for clothing and pharmacy | OSM | Clothing, Pharmacy | Low |
| 10 | Residential density and building mix | Local customer base | WorldPop, OSM | Pharmacy, Cafe | Medium |
| 11 | Growth signals (new projects, metro, mall) | Future demand | Anakin search | All | Medium |
| 12 | Rent budget as a hard filter | Removes unaffordable zones | Listings | All | Low |
| 13 | Vacancy: real listings in top zones | Makes output actionable | Anakin | All | Medium |
| 14 | Seasonality calendar | Festival, wedding and semester effects | Static config | Clothing, Cafe | Low |
| 15 | Late-night activity (POIs open late) | Safety and evening trade | OSM opening_hours | Cafe, Pharmacy (24x7) | Medium |
| 16 | Age-skew proxy | Colleges, hostels, PGs mean young; hospitals mean older | OSM | All | Low |
| 17 | Medical ecosystem density | Clinics, doctors, labs within 300 m | OSM | Pharmacy | Low |
| 18 | Regulatory checklist (licences, pharmacist requirement, signage rules) | Advisory only, not scored | Static, verify locally | Pharmacy | Low |
| 19 | Outcome feedback loop | Owners report results after 6 months, weights recalibrated | User input | All | Long term |
| 20 | Paid footfall data (mobile-location providers) | Real footfall | Partners | All | Roadmap |

Recommended for the hackathon: items 1, 2, 3, 5, 7, 8, 12, 13, 16, 17. Add 4 and 11 if time allows.

---

## 7. Store tiers ("how premium") and the questionnaire

The wizard asks the user to pick a tier, then a few category-specific questions. Tier labels and ticket-size bands below are **configurable defaults**, not facts.

### 7.1 Tier definitions

| Category | Budget / Regular | Mid | Premium |
|---|---|---|---|
| Cafe | Chai-and-snacks or regular coffee counter, low ticket | Branded-style cafe with seating | Specialty coffee, designer interiors, higher ticket |
| Clothing | Value and basic wear | Branded and regional labels | Boutique, designer, premium ethnic or western |
| Pharmacy | Neighbourhood standard pharmacy | Pharmacy plus OTC and personal care | Wellness and health-store style with home delivery, specialty (chronic care) |

### 7.2 Common questions (all categories)

1. City and preferred areas (optional).
2. Tier (as above, with short descriptions).
3. Monthly rent budget (INR) and shop size (sq ft).
4. Total investment budget (used for the summary, not scored).
5. Target customer (multi-select): students, young professionals, families, seniors, tourists.
6. Opening hours (used with the day-part profile).

### 7.3 Category-specific questions

- **Cafe:** format (takeaway kiosk, sit-down, co-working style), alcohol or food-heavy menu (affects footfall needs), expected average ticket band.
- **Clothing:** segment (men, women, kids, ethnic, multi), walk-in versus destination shop, need for parking (yes or no).
- **Pharmacy:** 24x7 planned (yes or no), home delivery planned, prescription-led or OTC-led, nearby clinics acceptable (yes or no).

Answers map to config parameters (tier target, POI weight multipliers, hard filters). Example: "students" multiplies the college weight by 1.3 for cafes; "24x7" adds the late-night activity signal for pharmacies.

---

## 8. Data model (PostgreSQL + PostGIS)

MVP shortcut: SQLite plus Shapely and H3 in Python also works for a single city, but PostGIS makes radius and polygon queries simple. Raw scrape payloads go to files (`data/raw/`) or an object store, with the path saved in the database.

### 8.1 Entity overview

```mermaid
erDiagram
  cities ||--o{ cells : has
  cells ||--o{ pois : contains
  cells ||--o{ listings : "near"
  cells ||--|| cell_features : "has"
  users ||--o{ analyses : creates
  analyses ||--o{ recommendations : yields
  cells ||--o{ recommendations : "ranked as"
  scrape_jobs ||--o{ listings : produces
  analyses ||--o{ agent_runs : "traced by"
```

### 8.2 DDL

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE cities (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  state TEXT,
  country TEXT DEFAULT 'IN',
  bbox GEOMETRY(Polygon, 4326),
  status TEXT DEFAULT 'draft',              -- draft | ingesting | ready | stale
  last_full_refresh TIMESTAMPTZ
);

CREATE TABLE cells (
  h3_index TEXT PRIMARY KEY,                -- H3 resolution 9
  city_id INT REFERENCES cities(id),
  centroid GEOMETRY(Point, 4326) NOT NULL,
  boundary GEOMETRY(Polygon, 4326),
  locality_name TEXT,
  land_use TEXT                             -- residential | commercial | mixed | other
);
CREATE INDEX cells_centroid_gix ON cells USING GIST (centroid);

CREATE TABLE pois (
  id BIGSERIAL PRIMARY KEY,
  osm_type TEXT,
  osm_id BIGINT,
  city_id INT REFERENCES cities(id),
  category TEXT NOT NULL,                   -- normalised: school, college, mall, hospital, cafe, pharmacy, clothes...
  name TEXT,
  brand TEXT,
  tier_guess TEXT DEFAULT 'unknown',        -- budget | mid | premium | unknown
  location GEOMETRY(Point, 4326) NOT NULL,
  h3_index TEXT REFERENCES cells(h3_index),
  tags JSONB,
  source TEXT DEFAULT 'osm',
  fetched_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (osm_type, osm_id)
);
CREATE INDEX pois_location_gix ON pois USING GIST (location);
CREATE INDEX pois_category_idx ON pois (category);

CREATE TABLE scrape_jobs (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,                     -- 99acres | magicbricks | news | search
  purpose TEXT,                             -- commercial_rent | resi_price | market_intel
  target_url TEXT,
  anakin_job_id TEXT,
  credits_used NUMERIC,
  status TEXT DEFAULT 'queued',             -- queued | running | done | failed
  raw_path TEXT,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE TABLE listings (
  id BIGSERIAL PRIMARY KEY,
  scrape_job_id BIGINT REFERENCES scrape_jobs(id),
  city_id INT REFERENCES cities(id),
  source TEXT,
  url TEXT,
  listing_type TEXT,                        -- rent | sale
  property_type TEXT,                       -- shop | office | showroom | apartment | plot
  price_inr NUMERIC,
  price_period TEXT,                        -- month | total
  area_sqft NUMERIC,
  price_per_sqft NUMERIC,
  locality TEXT,
  address_text TEXT,
  location GEOMETRY(Point, 4326),
  geo_precision TEXT,                       -- exact | locality
  h3_index TEXT REFERENCES cells(h3_index),
  posted_date DATE,
  scraped_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX listings_h3_idx ON listings (h3_index);

CREATE TABLE market_intel (
  id BIGSERIAL PRIMARY KEY,
  city_id INT REFERENCES cities(id),
  category TEXT,                            -- clothing | cafe | pharmacy | general
  topic TEXT,                               -- market_reputation | growth_news
  summary TEXT,
  sources JSONB,                            -- [{title, url}]
  locality_mentions TEXT[],
  fetched_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE cell_features (
  h3_index TEXT REFERENCES cells(h3_index),
  feature_version INT NOT NULL,
  features JSONB NOT NULL,                  -- raw + normalised values for F1..F9 and helper metrics
  affluence NUMERIC,
  rent_per_sqft_est NUMERIC,
  rent_is_estimated BOOLEAN,
  confidence NUMERIC,
  computed_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (h3_index, feature_version)
);

CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  external_id TEXT UNIQUE,                  -- id from DronaHQ auth
  email TEXT,
  role TEXT DEFAULT 'owner',                -- owner | analyst | admin
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE analyses (
  id TEXT PRIMARY KEY,                      -- an_xxxxxxxx
  user_id BIGINT REFERENCES users(id),
  city_id INT REFERENCES cities(id),
  category TEXT NOT NULL,
  tier TEXT NOT NULL,
  answers JSONB,                            -- questionnaire answers
  constraints JSONB,                        -- rent budget, shop size, preferred areas
  config_version TEXT,                      -- which weights file was used
  status TEXT DEFAULT 'queued',             -- queued | running | done | failed
  summary_narrative TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE TABLE recommendations (
  id BIGSERIAL PRIMARY KEY,
  analysis_id TEXT REFERENCES analyses(id) ON DELETE CASCADE,
  rank INT,
  h3_index TEXT REFERENCES cells(h3_index),
  zone_name TEXT,
  score NUMERIC,
  confidence NUMERIC,
  contributions JSONB,                      -- {F1: 4.2, F2: 8.1, ...}
  top_drivers JSONB,
  top_risks JSONB,
  nearby_listing_ids BIGINT[],
  narrative TEXT
);

CREATE TABLE agent_runs (
  id BIGSERIAL PRIMARY KEY,
  analysis_id TEXT,
  agent_name TEXT,
  status TEXT,
  latency_ms INT,
  tokens_in INT,
  tokens_out INT,
  cost_usd NUMERIC,
  trace_id TEXT,                            -- link to Nasiko / OpenTelemetry trace
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE category_configs (
  category TEXT,
  version TEXT,
  config JSONB,                             -- mirrors the YAML in the repo, editable in the admin screen
  is_active BOOLEAN DEFAULT true,
  PRIMARY KEY (category, version)
);
```

### 8.3 Raw data storage

```
data/raw/{source}/{city}/{yyyy-mm-dd}/{job_id}.md|json    # scraped payloads
data/exports/{analysis_id}.pdf                            # generated reports
```

---

## 9. Agents (registered on Nasiko)

Six agents registered on Nasiko, plus an `orchestrator` that can simply live inside the backend if Nasiko-side orchestration is not needed. Each agent is a small containerized service with an `AgentCard.json` describing what it can do so the Nasiko router can match queries to it. **[VERIFY]** the exact card schema and agent template in the Nasiko repo (agent development guide).

### 9.1 Agent catalogue

| Agent | Purpose | Uses LLM | External calls | Reads / writes |
|---|---|---|---|---|
| `orchestrator` | Runs the analysis pipeline in order, handles retries, aggregates results | No | Other agents via gateway | analyses, agent_runs |
| `geo-data` | Builds cells, fetches POIs from OSM, assigns to cells, computes landmark features | No | Overpass API | cells, pois, cell_features |
| `listings` | Builds the scrape plan, calls Anakin, extracts and geocodes listings | Fallback only | Anakin, geocoder | scrape_jobs, listings |
| `market-intel` | Anakin search and agentic search for market reputation and growth news, produces cited summaries | Yes (summarise) | Anakin | market_intel |
| `affluence` | Computes affluence, competitor tier guesses, rent estimates and smoothing | Optional (tier classify) | none | cell_features |
| `scoring` | Applies category weights, tier fit, constraints, ranking, confidence and explanations | No | none | recommendations |
| `report-chat` | Writes narratives, answers follow-ups, runs what-if requests, builds PDF | Yes | LLM | analyses, recommendations |

### 9.2 Who calls whom

- **Batch ingestion:** scheduler triggers `geo-data`, then `listings` and `market-intel` in parallel, then `affluence`.
- **Online analysis:** backend calls `orchestrator`, which calls `scoring`, then `report-chat`.
- **Free-text chat:** DronaHQ chat sends the message to the Nasiko router (`/router/route?query=...`), which selects `report-chat` (explanations, what-ifs) or `market-intel` (fresh questions like "any new mall planned near Baner?").

For a fixed pipeline, call agents directly by name (`/agents/{name}/...`). Use the router only for open-ended user questions. This keeps the demo predictable.

### 9.3 Illustrative AgentCard (adapt to the real schema)

```json
{
  "name": "scoring",
  "description": "Ranks candidate zones for a chosen business category and tier using precomputed area features. Use for questions about rankings, score breakdowns and what-if changes to tier, budget or category.",
  "version": "0.1.0",
  "capabilities": [
    "rank_locations",
    "explain_score",
    "what_if_tier_change",
    "compare_zones"
  ],
  "input_schema": {
    "city": "string",
    "category": "clothing | cafe | pharmacy",
    "tier": "budget | mid | premium",
    "constraints": {"monthly_rent_budget_inr": "number", "shop_size_sqft": "number"}
  }
}
```

### 9.4 Agent contract rules

- Input and output are JSON validated with Pydantic.
- Every response includes `agent`, `version`, `latency_ms`, `warnings[]`.
- Agents never hold provider keys in code. Read from environment (or Nasiko's LLM routing if available).
- Idempotent: rerunning ingestion for the same city and date must not duplicate rows (upsert on natural keys).

---

## 10. Backend API specification (FastAPI)

Base URL `https://<backend-host>/v1`. All routes require header `X-API-Key: <shared secret with DronaHQ>`. DronaHQ passes `X-User-Id` for the signed-in user.

### 10.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and versions |
| GET | `/cities` | Cities with status `ready` |
| GET | `/categories` | Category configs: tiers, questions, labels |
| POST | `/analyses` | Create an analysis (returns immediately) |
| GET | `/analyses/{id}` | Status and summary |
| GET | `/analyses/{id}/recommendations` | Ranked zones with breakdown (GeoJSON option) |
| GET | `/analyses/{id}/zones/{rank}` | Full detail for one zone |
| POST | `/analyses/{id}/compare` | Compare 2 or 3 zones |
| POST | `/analyses/{id}/what-if` | Re-score with changed tier, budget or category |
| POST | `/chat` | Follow-up question (routed via Nasiko) |
| GET | `/analyses/{id}/report.pdf` | Export |
| POST | `/admin/cities/{id}/ingest` | Start city ingestion (admin only) |
| GET | `/admin/jobs` | Scrape jobs, credits, errors |
| GET | `/admin/data-freshness` | Freshness per source and city |
| PUT | `/admin/configs/{category}` | Update weights (creates a new version) |

### 10.2 Create analysis

Request:

```json
{
  "city": "Pune",
  "category": "cafe",
  "tier": "premium",
  "answers": {
    "format": "sit_down",
    "target_customer": ["young_professionals", "students"],
    "opening_hours": "08:00-23:00"
  },
  "constraints": {
    "monthly_rent_budget_inr": 120000,
    "shop_size_sqft": 800,
    "preferred_areas": []
  },
  "top_n": 10
}
```

Response:

```json
{ "analysis_id": "an_7f3a9c21", "status": "queued" }
```

### 10.3 Recommendations response

```json
{
  "analysis_id": "an_7f3a9c21",
  "status": "done",
  "category": "cafe",
  "tier": "premium",
  "recommendations": [
    {
      "rank": 1,
      "zone_name": "Koregaon Park (north)",
      "h3_index": "8961a...",
      "centroid": {"lat": 18.5362, "lon": 73.8939},
      "score": 78.4,
      "confidence": 0.82,
      "contributions": {"F1": 21.3, "F2": 16.0, "F3": 3.1, "F4": 2.4, "F5": 6.2, "F6": 7.9, "F7": 6.8, "F8": 3.2, "F9": 2.5},
      "top_drivers": ["Many offices and coworking spaces within 400 m", "Area affluence matches premium tier", "No premium cafe within 300 m"],
      "top_risks": ["Rent about 15 percent above your budget midpoint", "Weak weekend footfall signals"],
      "nearby_listings": [
        {"title": "Ground floor shop, 750 sq ft", "rent_inr_month": 110000, "url": "https://...", "distance_m": 220}
      ],
      "narrative": "..."
    }
  ],
  "data_notes": ["Rents are asking prices from listing sites", "Footfall is estimated from landmarks, not measured"]
}
```

### 10.4 Errors

Use standard JSON errors: `{"error": {"code": "CITY_NOT_READY", "message": "...", "retryable": false}}`. Codes: `INVALID_INPUT`, `CITY_NOT_READY`, `NO_CANDIDATES` (constraints too strict), `UPSTREAM_TIMEOUT`, `INTERNAL`.

---

## 11. Data flow and sequence diagrams

### 11.1 Online analysis

```mermaid
sequenceDiagram
  participant U as User
  participant D as DronaHQ app
  participant B as Backend API
  participant O as Orchestrator
  participant S as Scoring agent
  participant R as Report agent
  participant DB as PostGIS

  U->>D: Fill wizard (city, category, tier, budget)
  D->>B: POST /analyses
  B->>DB: Insert analysis (queued)
  B-->>D: analysis_id
  B->>O: Run pipeline (async)
  O->>DB: Load cell_features for city
  O->>S: Score with category config and constraints
  S->>DB: Write recommendations
  O->>R: Generate narratives from JSON
  R->>DB: Write narratives
  O->>DB: Mark analysis done
  D->>B: Poll GET /analyses/{id}
  B-->>D: status done
  D->>B: GET recommendations
  B-->>D: Ranked zones
  D-->>U: Map, list, breakdown
```

### 11.2 Offline ingestion

```mermaid
sequenceDiagram
  participant A as Admin or Scheduler
  participant G as Geo-data agent
  participant L as Listings agent
  participant M as Market-intel agent
  participant F as Affluence agent
  participant AN as Anakin
  participant OSM as Overpass
  participant DB as PostGIS

  A->>G: Ingest city
  G->>OSM: Fetch POIs by tag groups
  G->>DB: Save cells and POIs
  par Listings
    A->>L: Scrape plan
    L->>AN: Batch scrape search URLs
    AN-->>L: Markdown or JSON
    L->>DB: Save listings
  and Market intel
    A->>M: Research questions
    M->>AN: Search and agentic search
    AN-->>M: Cited answers
    M->>DB: Save summaries
  end
  A->>F: Compute features
  F->>DB: Write cell_features (with confidence)
```

### 11.3 Data lifecycle summary

Raw (OSM JSON, scraped markdown) becomes normalised tables (pois, listings), then derived (cell_features), then per-request output (recommendations, narratives, PDF). Only the last step is user-specific.

### 11.4 Freshness policy

| Data | Refresh | Stale after |
|---|---|---|
| POIs (OSM) | Monthly | 60 days |
| Commercial rents | Weekly | 21 days |
| Residential prices | Monthly | 60 days |
| Market intel and news | Weekly | 21 days |
| Features | After any upstream refresh | n/a |

The UI shows the oldest data date used in each analysis.

---

## 12. Anakin integration details

### 12.1 What we call

| Need | Anakin capability | Notes |
|---|---|---|
| Rent listings | URL scraper (single or batch) on filtered search URLs | 1 credit each. Batch 10 URLs per request |
| Locality price pages | URL scraper | 1 credit each |
| Discover pages on a portal | Map, Crawl | Crawl is 1 credit per page, max 100 pages per job |
| Market reputation, growth news | Search (3 credits) and Agentic Search (10 plus 1 per URL read) | Returns cited answers |
| Competitor pages (optional) | URL scraper | Respect terms |

### 12.2 Request pattern (REST, as shown in Anakin's docs and blog)

```bash
# submit
curl -X POST https://api.anakin.io/v1/url-scraper \
  -H "X-API-Key: $ANAKIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/commercial-rent-pune", "useBrowser": true}'
# -> {"jobId": "job_abc123"}

# poll (polling URL scraper jobs is not rate limited)
curl https://api.anakin.io/v1/url-scraper/job_abc123 -H "X-API-Key: $ANAKIN_API_KEY"

# batch (up to 10 URLs, uses 1 rate-limit slot)
curl -X POST https://api.anakin.io/v1/url-scraper/batch \
  -H "X-API-Key: $ANAKIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"urls": ["url1", "url2"]}'
```

Python SDK (alpha, API may change):

```python
from anakin import Anakin
client = Anakin()   # reads ANAKIN_API_KEY
doc = client.scrape(url, formats=["markdown"])
print(doc.markdown)
```

**[VERIFY]** parameter names for AI JSON extraction (the Anakin blog mentions `generateJson: true`) and the response shape in the current docs at anakin.io/docs.

### 12.3 Extraction approach

1. **Try Anakin's AI extraction** with the schema below.
2. **Fallback:** scrape to markdown, then run a small LLM with a strict JSON schema, validate with Pydantic, and drop rows that fail validation.
3. Drop personal data (owner or agent names, phone numbers) at this step.

Listing schema:

```json
{
  "title": "string",
  "listing_type": "rent | sale",
  "property_type": "shop | office | showroom | apartment | plot",
  "price_inr": "number",
  "price_period": "month | total",
  "area_sqft": "number",
  "locality": "string",
  "address_text": "string or null",
  "lat": "number or null",
  "lon": "number or null",
  "floor": "string or null",
  "posted_date": "YYYY-MM-DD or null",
  "url": "string"
}
```

Computed after extraction: `price_per_sqft = price_inr / area_sqft`. Reject rows with area under 50 or over 20,000 sq ft, or with prices more than 5 standard deviations from the locality median.

### 12.4 Scrape plan and credit budget (demo city, estimates)

Free plan is about 300 credits. Estimate for one city:

| Job | Count | Credits each | Total |
|---|---|---|---|
| Commercial rent search pages (15 localities x 2 pages) | 30 | 1 | 30 |
| Residential price pages (15 localities) | 15 | 1 | 15 |
| Agentic searches (market reputation per category, growth news) | 6 | about 15 | about 90 |
| Plain searches (news, checks) | 8 | 3 | 24 |
| Retries and testing buffer | | | about 100 |
| **Total** | | | **about 260** |

Track `credits_used` per job in `scrape_jobs` and show it on the admin screen. **Test with 2 or 3 URLs first** before running the whole plan.

### 12.5 Reliability rules

- Cache by URL and date. Never re-scrape the same URL within its freshness window.
- Exponential backoff on rate-limit errors.
- Save raw output before parsing, so parsing bugs do not cost credits.
- Ship a **snapshot dataset** (`data/snapshots/pune_2026-09.json`) with the repo, so the demo works even if scraping fails on the day.
- If a target portal blocks scraping, switch to another portal or reduce to locality-level price pages. Do not try to defeat protections that a site has explicitly put in place.

---

## 13. Nasiko integration details

### 13.1 Local setup (from the repo README)

```bash
git clone https://github.com/Nasiko-Labs/nasiko.git
cd nasiko
cp .nasiko-local.env.example .nasiko-local.env
# edit .nasiko-local.env: add OPENROUTER_API_KEY or OPENAI_API_KEY, encryption key, etc.
uv sync
make start-nasiko
```

Requirements: Docker, Docker Compose, Python 3.12+, about 4 GB RAM.

### 13.2 Ports and routes (Kong gateway, local)

| Route | Goes to |
|---|---|
| `http://localhost:9100/app/` | Nasiko web dashboard |
| `http://localhost:9100/router/route?query=...` | Intelligent router (picks an agent) |
| `http://localhost:9100/agents/{name}/...` | A specific agent |
| `http://localhost:9100/api/...` | Nasiko backend API |
| `http://localhost:9100/auth/...` | Nasiko auth service |

**[VERIFY]** against the version you clone. Newer versions of the repo describe a different internal layout.

### 13.3 Deploying one of our agents

```bash
cd agents/scoring
docker compose up -d                       # test the agent alone
nasiko agent upload-directory . --name scoring
curl -X POST http://localhost:9100/agents/scoring/rank \
  -H "Content-Type: application/json" -d @sample_request.json
```

Notes from the docs:
- Agents run on an internal Docker network and are reached through the gateway.
- The router caches the agent registry. **Restart the router after deploying a new agent** or it will not see it.
- The router's vector store only activates at 15 or more agents. With six agents the router asks the LLM directly, so no embedding provider is needed.

### 13.4 How SiteScout uses Nasiko

| Use | Mechanism |
|---|---|
| Registry and deployment | Upload each agent, keep versioned cards |
| Fixed pipeline | Backend calls `/agents/{name}/...` directly |
| Free-text chat | Backend calls `/router/route?query=...` and returns the routed agent's answer |
| Observability | OpenTelemetry traces (Phoenix dashboard in the README) for each agent call, shown in the demo |
| LLM access | Keys in Nasiko env, or agents read their own env |

### 13.5 Exposing to DronaHQ

DronaHQ is a cloud platform and cannot reach `localhost`. Options, in order of simplicity for a demo:

1. Run the backend on your laptop and expose it with a tunnel (ngrok or Cloudflare Tunnel). Keep the Nasiko gateway private. Only the backend is public.
2. Deploy backend and Nasiko on one small cloud VM (Nasiko has a DigitalOcean marketplace listing and cloud deployment docs).

Never expose the Nasiko gateway publicly without auth.

---

## 14. DronaHQ app: screens, dashboards, wireframes

### 14.1 Integration approach

- **Connector:** one REST connector pointing to the backend base URL, with `X-API-Key` stored as a secret and `X-User-Id` from the signed-in user.
- **Auth and roles:** use DronaHQ's own login. Roles: `owner` (wizard, results), `admin` (ingestion, configs, cost). **[VERIFY]** role features on your plan.
- **Async handling:** after `POST /analyses`, poll `GET /analyses/{id}` every 3 seconds until `done`. Show a progress state.
- **Chat:** DronaHQ chat agent or chat component calls `POST /chat`. Do not put business logic inside DronaHQ; keep it in the backend.
- **PDF:** either the backend's `report.pdf` or DronaHQ's PDF generator add-on.

### 14.2 Screen map

```mermaid
flowchart TD
  S1["1. Home / My analyses"] --> S2["2. New analysis wizard"]
  S2 --> S3["3. Results: map + ranked list"]
  S3 --> S4["4. Zone detail"]
  S3 --> S5["5. Compare zones"]
  S3 --> S6["6. What-if panel"]
  S3 --> S7["7. Chat drawer"]
  S3 --> S8["8. Export report"]
  A1["Admin: Data and jobs"] --> A2["Admin: Weights editor"]
  A1 --> A3["Admin: System health"]
```

### 14.3 Owner-facing screens

**Screen 1: My analyses.** Table of past analyses (date, city, category, tier, top zone, status). Button "New analysis".

**Screen 2: New analysis wizard** (4 steps)
1. City and category (three large cards: Clothing, Cafe, Pharmacy).
2. Tier selection with plain descriptions (see 7.1).
3. Constraints: monthly rent budget, shop size, opening hours, target customers, category-specific questions.
4. Review and submit.

```
+--------------------------------------------------+
| New analysis                        Step 2 of 4  |
|--------------------------------------------------|
| How premium will your cafe be?                   |
|                                                  |
| ( ) Regular   chai and snacks, low ticket        |
| ( ) Mid       branded-style cafe with seating    |
| (o) Premium   specialty coffee, designer interior|
|                                                  |
| Tip: premium needs an area where people spend    |
| more. We check this using property prices.       |
|                                                  |
|                       [Back]   [Next]            |
+--------------------------------------------------+
```

**Screen 3: Results (main dashboard)**

```
+----------------------------------------------------------------------+
| Cafe, Premium, Pune                 [What-if] [Compare] [Export PDF] |
|----------------------------------------------------------------------|
| KPIs:  Best score 78 | Zones ranked 10 | Median rent/sqft 105 | Conf. |
|----------------------------------------------------------------------|
|  MAP (hex heatmap, top 10 pinned)      |  RANKED ZONES               |
|                                        |  1 Koregaon Park N   78  ██ |
|   [legend: score 0-100]                |  2 Baner Road        74  ██ |
|   [toggle layers: landmarks,           |  3 Viman Nagar       71  █  |
|    listings, competitors]              |  ...                        |
|----------------------------------------------------------------------|
|  Selected zone: drivers | risks | listings nearby | [Open detail]    |
+----------------------------------------------------------------------+
```

Widgets: map with hex overlay, ranked table, KPI tiles, layer toggles (landmarks, competitors, listings), filter by minimum confidence and maximum rent.

**Screen 4: Zone detail.** Tabs:
- *Overview:* score, confidence, narrative, data notes.
- *Score breakdown:* horizontal bar chart of `contributions` (F1 to F9) and a radar chart comparing to the city median.
- *Landmarks:* table and mini-map of colleges, offices, malls, hospitals with distances.
- *Spending power:* affluence index, price per sqft, premium POI list.
- *Competition:* competitors by tier, gap statement ("no premium cafe within 300 m").
- *Rent and listings:* rent range, available listings (title, rent, size, link).
- *Risks and checklist:* risks plus a "visit this place" checklist (peak hour visit, ask neighbours, check parking, legal checks).

**Screen 5: Compare zones.** Side-by-side columns for 2 or 3 zones: score, contributions, rent, competition, listings, pros and cons.

**Screen 6: What-if panel.** Sliders and selectors: tier, rent budget, shop size. Calls `/what-if`, shows rank changes ("Baner moves from #4 to #1 if you go regular tier").

**Screen 7: Chat drawer.** Ask "Why is Baner below Viman Nagar?", "Any new mall coming near Wakad?". Answers reference zone data. Shows source links for fresh web answers.

**Screen 8: Export.** PDF with map snapshot, top 5 zones, breakdown, listings, assumptions and limitations.

### 14.4 Admin dashboards

**Data and jobs**
- City table: status, last refresh, POI count, listing count, cells ready.
- Scrape jobs: source, URL, status, credits used, error, raw file link.
- Anakin credits: used versus remaining (from `scrape_jobs.credits_used`), with a warning at 80 percent.
- Freshness heatmap per source and city.
- Buttons: "Ingest city", "Refresh rents", "Refresh market intel".

**Weights editor**
- Per-category table of weights with live sum check (must equal 1.0).
- Tier targets and POI landmark weights.
- "Save as new version" and "Set active". Shows the last back-test correlation for each version.

**System health**
- Agent status (up or down), latency and error rate per agent, LLM tokens and cost per analysis, link to the Nasiko dashboard and traces.

### 14.5 KPIs to display (owner and admin)

Owner: best score, number of zones with confidence above 0.5, median rent per sq ft, competitor count in top zone.
Admin: analyses per day, average time to result, credits per city refresh, LLM cost per analysis, failed jobs.

### 14.6 Map fallback

If DronaHQ lacks a suitable map component **[VERIFY]**, build a single-page Leaflet or MapLibre app that reads `GET /analyses/{id}/recommendations?format=geojson` and embed it in a DronaHQ page (iframe or custom component). Pass the analysis id in the URL and protect it with a short-lived token.

---

## 15. User flows

### 15.1 Main flow (owner)

```mermaid
flowchart TD
  A["Open app"] --> B["Choose city and category"]
  B --> C["Choose tier"]
  C --> D["Answer constraints"]
  D --> E["Submit"]
  E --> F["Progress screen (polling)"]
  F --> G["Results map + ranked list"]
  G --> H["Open zone detail"]
  H --> I["Compare or what-if"]
  I --> J["Ask chat questions"]
  J --> K["Export PDF and visit shortlisted zones"]
```

### 15.2 Edge cases and behaviour

| Situation | Behaviour |
|---|---|
| City not ready | Show "Not available yet", offer to be notified |
| No zone passes the rent filter | Show `NO_CANDIDATES`, suggest raising budget or reducing size, show the cheapest 3 zones with their rent |
| Low-confidence top zone | Show a warning badge and explain what data is missing |
| Tier and area mismatch (premium in low-affluence area) | Rank low, show the reason explicitly |
| Chat asks something outside scope | Say so, suggest what the tool can answer |
| Scrape or agent failure mid-analysis | Use the last good snapshot and show its date |

### 15.3 Admin flow

Login, open Data and jobs, check freshness, click "Refresh rents", watch jobs and credits, review failures, open Weights editor if the back-test shows drift, save a new version, run the back-test, activate.

---

## 16. Tech stack

| Area | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Matches Nasiko, best geo and data libraries |
| API | FastAPI, Pydantic v2, Uvicorn | Async, typed, auto-docs |
| Database | PostgreSQL 16 + PostGIS | Spatial queries |
| Grid | `h3` (Python) | Hex cells and k-rings |
| Geo | GeoPandas, Shapely, `osmnx` or raw Overpass requests | POIs and geometry |
| Routing (optional) | OpenRouteService or Valhalla | Walking isochrones |
| Data | pandas, numpy | Percentile normalisation, features |
| Scraping | `anakin-sdk` and REST | Web data |
| Agents | Python services following the Nasiko agent template | Registry and routing |
| LLM access | OpenRouter (default), OpenAI or Gemini optional, Ollama for local | Cheap, swappable |
| Scheduling | APScheduler (or cron in the container) | Refresh jobs |
| Frontend | DronaHQ, plus optional Leaflet or MapLibre page | Required platform |
| Charts | DronaHQ charts, Chart.js in the map page | Breakdown visuals |
| PDF | DronaHQ PDF generator add-on or WeasyPrint | Report export |
| Infra | Docker Compose, ngrok or Cloudflare Tunnel, optional small VM | Simple demo hosting |
| Observability | Nasiko OpenTelemetry and Phoenix, structured JSON logs | Traces per agent call |
| Testing | pytest, Hypothesis for scoring properties, Postman or curl scripts | Confidence |
| Quality | ruff, mypy (optional), pre-commit | Hygiene |

---

## 17. Repository structure

```
sitescout/
├── README.md
├── architecture.md
├── docker-compose.yml
├── .env.example
├── config/
│   ├── categories/
│   │   ├── cafe.yaml
│   │   ├── clothing.yaml
│   │   └── pharmacy.yaml
│   ├── brands_premium.yaml
│   └── osm_tags.yaml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                  # routers: analyses, admin, chat, health
│   │   ├── core/                 # settings, auth, logging
│   │   ├── db/                   # models, migrations (alembic)
│   │   ├── services/             # analysis_service, nasiko_client, anakin_client
│   │   └── schemas/              # pydantic models
│   └── tests/
├── agents/
│   ├── geo_data/                 # Dockerfile, AgentCard.json, app.py
│   ├── listings/
│   ├── market_intel/
│   ├── affluence/
│   ├── scoring/
│   └── report_chat/
├── pipelines/
│   ├── ingest_city.py
│   ├── refresh_rents.py
│   └── build_features.py
├── scoring/                      # pure functions shared by scoring agent and tests
│   ├── features.py
│   ├── tier_fit.py
│   └── score.py
├── data/
│   ├── raw/
│   ├── snapshots/                # pre-scraped demo data (commit this)
│   └── backtest/                 # known good and bad locations
├── frontend/
│   └── map_embed/                # optional Leaflet page
├── dronahq/
│   └── export/                   # exported app definition, screenshots
└── scripts/
    ├── backtest.py
    ├── seed_demo.py
    └── smoke_test.sh
```

---

## 18. Environment variables and configuration

```bash
# .env.example
# --- Anakin ---
ANAKIN_API_KEY=ak-...
ANAKIN_MAX_CREDITS_PER_RUN=120

# --- LLM ---
LLM_PROVIDER=openrouter            # openrouter | openai | gemini | ollama
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL_SMALL=<cheap model id>   # classification and extraction fallback
LLM_MODEL_WRITER=<better model id> # narratives and chat

# --- Nasiko ---
NASIKO_BASE_URL=http://localhost:9100
NASIKO_TOKEN=                      # if auth is enabled

# --- Database ---
DATABASE_URL=postgresql+psycopg://sitescout:sitescout@localhost:5432/sitescout

# --- Backend ---
BACKEND_API_KEY=change-me          # shared with DronaHQ connector
ALLOWED_ORIGINS=https://<your-dronahq-domain>
LOG_LEVEL=INFO

# --- Geo ---
OVERPASS_URL=https://overpass-api.de/api/interpreter
GEOCODER_URL=                      # Nominatim or Photon (respect usage policy)
H3_RESOLUTION=9
```

Never commit real keys. Give agents only the variables they need.

---

## 19. Deployment and local setup

### 19.1 Services

| Service | How it runs | Port |
|---|---|---|
| PostGIS | Docker (`postgis/postgis` image) | 5432 |
| Backend | Docker, Uvicorn | 8000 |
| Nasiko stack | Its own `make start-nasiko` (Docker Compose) | 9100 (gateway) |
| SiteScout agents | Uploaded to Nasiko (containers on its agent network) | via gateway |
| Tunnel | ngrok or Cloudflare Tunnel to the backend only | public URL |

### 19.2 docker-compose (ours, excluding Nasiko)

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_USER: sitescout
      POSTGRES_PASSWORD: sitescout
      POSTGRES_DB: sitescout
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  backend:
    build: ./backend
    env_file: .env
    depends_on: [db]
    ports: ["8000:8000"]
    volumes: ["./data:/app/data", "./config:/app/config"]

volumes:
  pgdata:
```

### 19.3 First-run checklist

1. `cp .env.example .env` and fill keys.
2. Start Nasiko (`make start-nasiko` in its folder) and confirm `http://localhost:9100/app/` opens.
3. `docker compose up -d` (database and backend), run migrations.
4. Upload the six agents to Nasiko, restart the router, run the smoke test.
5. `python scripts/seed_demo.py` to load the snapshot city (works without Anakin).
6. Start the tunnel and copy the public URL into the DronaHQ connector.
7. In DronaHQ, build the screens and test the wizard end to end.
8. Only then run live ingestion with Anakin on 2 or 3 URLs, then the full plan.

### 19.4 Smoke test (`scripts/smoke_test.sh`)

```bash
curl -s $BACKEND/v1/health
curl -s -X POST $BACKEND/v1/analyses -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d @scripts/sample_cafe_premium.json
# poll, then verify: 10 recommendations, scores in [0,100], contributions sum to score
```

---

## 20. Build plan (hackathon timeline)

Adjust to the real schedule. Times are rough effort for a team of 2 to 3.

| Phase | Work | Output | Effort |
|---|---|---|---|
| 0. Setup | Sign up (Nasiko, DronaHQ, Anakin), run Nasiko locally, get LLM key, pick city, test 2 Anakin scrapes on real portal URLs | Go/no-go on data sources | 3 to 4 h |
| 1. Data foundation | PostGIS schema, H3 grid, OSM POI ingestion, tag mapping | Cells and POIs for the city | 5 to 6 h |
| 2. Listings and prices | Scrape plan, Anakin client, extraction, geocoding, smoothing | Rent and price per cell | 5 to 6 h |
| 3. Scoring engine | Features F1 to F9, tier fit, weights YAML, ranking, explanations, unit tests | `scoring/` library, CLI output | 5 to 6 h |
| 4. Backend API | Endpoints, async analysis, persistence | Working `/v1` API | 4 to 5 h |
| 5. Agents on Nasiko | Wrap components as agents, cards, upload, router test | 6 agents registered | 4 to 5 h |
| 6. DronaHQ app | Wizard, results, zone detail, admin basics, connector, tunnel | Usable UI | 6 to 8 h |
| 7. Validation | Back-test, tune weights, fix obvious errors | Numbers for the pitch | 3 to 4 h |
| 8. Polish and demo | Compare, what-if, chat, PDF, snapshot data, rehearse | Demo ready | 4 to 5 h |

**Priority cuts if time is short (in order):** drop isochrones, drop growth-momentum (F9), drop compare screen, drop PDF, keep one category polished and configure the other two with weights only.

**Suggested split for 3 people:** (A) data and pipelines (phases 1, 2), (B) scoring and backend (3, 4, 7), (C) DronaHQ and agents (5, 6, 8).

**Start with one category** (cafe or clothing) end to end, then add the other two by config. Because scoring is config-driven, the second and third categories mostly cost weight tuning and POI maps.

### 20.1 Definition of done for MVP

- Wizard, results map, zone detail and chat work for all three categories on one city.
- Clothing example behaves correctly (section 5.8).
- Tier change re-ranks zones.
- Back-test result and data-source caveats are on a slide.
- Demo runs from the snapshot with the network off.

---

## 21. Validation and back-testing

We cannot measure real footfall, so validate with independent proxies.

### 21.1 Known good / known bad test

1. Pick 10 places you know well: for example 4 busy cloth markets, 3 dense residential streets, 3 mixed areas.
2. Run clothing analysis. Check the markets rank above residential streets.
3. Repeat for cafe (near colleges and offices should rank high) and pharmacy (near hospitals and dense housing should rank high).
4. Store the cases in `data/backtest/` with expected order.

### 21.2 Popularity correlation

For each category, take existing shops in the city (from OSM plus Places or scraped review counts if available). Compute the model's score for the cell each shop sits in, excluding that shop from its own competition feature. Report the **Spearman correlation** between cell score and shop review count. It is imperfect (established shops sit where they do partly because it works) but a positive correlation is a useful sanity check.

### 21.3 Sensitivity and stability

- Perturb weights by plus or minus 20 percent and report how much the top 10 changes. A stable top 10 is more trustworthy.
- Change tier and confirm the ranking moves in the expected direction (premium moves toward high-affluence zones).
- Check that contributions sum to the score (unit test).

### 21.4 Metrics to show

Top-3 hit rate on the known-good list, Spearman correlation, average confidence of the top 10, and end-to-end latency.

### 21.5 Honest limitation statement (put on a slide)

"Scores are based on public data proxies for footfall and spending power. They rank areas for further on-site checks. They do not predict revenue."

---

## 22. Risks, legal and limitations

| Risk | Impact | Mitigation |
|---|---|---|
| Portal blocks or bans scraping, or terms forbid it | No rent or price data | Read terms first, test early, use snapshot data, fall back to locality-level pages or open data, ask the hackathon organisers about data rules |
| Anakin free credits run out | Cannot refresh | Budget plan (12.4), cache, batch requests, snapshot |
| OSM data gaps | Wrong POI counts | Confidence score, spot-check known areas, optional Places API |
| Asking prices are not transaction prices | Overstated affluence | Use percentile ranks, show the caveat |
| Listing noise and duplicates | Bad rent stats | Outlier rules, dedupe on URL and normalised address |
| Weights are heuristics | Questionable rankings | Back-test, sensitivity analysis, admit it openly |
| LLM hallucination in narratives | Wrong claims | LLM sees only structured JSON, must quote provided numbers, post-check numbers against payload |
| Nasiko version differences, agent format surprises | Lost time | Try a hello-world agent in phase 0 |
| DronaHQ cannot do a map or polling | UI limits | Leaflet embed fallback (14.6) |
| Public tunnel exposes the backend | Security | API key, rate limit, CORS, keep Nasiko private |
| Personal data in scraped pages | Privacy | Drop names and phone numbers at extraction, never store |
| Overclaiming | Trust | Position as decision support, show data notes in every report |
| Regulatory advice (pharmacy licensing) | Wrong guidance | Show only a generic checklist labelled "verify with local authority" |

---

## 23. Demo script (5 minutes)

1. **Problem (30 s).** "Wrong store location is the costliest mistake for a new shop, and most owners decide by gut."
2. **Wizard (45 s).** Cafe, premium tier, rent budget, 800 sq ft.
3. **Results (60 s).** Map heat, top zones, open the top one: landmarks (offices, colleges), affluence from property prices, no premium competitor nearby, listings available now.
4. **Category-awareness (60 s).** Switch to clothing: the ranking changes. Show the dense residential cell scoring low and the market scoring high, with the breakdown.
5. **Tier effect (30 s).** What-if: premium to regular, watch the ranking shift.
6. **Chat (30 s).** "Any new mall planned near this zone?" (Nasiko router picks market-intel, Anakin answers with sources.)
7. **Under the hood (45 s).** Nasiko dashboard with agent traces, Anakin job list and credits, DronaHQ admin dashboard.
8. **Honesty and roadmap (30 s).** Limitations slide, back-test numbers, next steps.

Backup: everything runs from the snapshot if the network fails.

---

## 24. Open questions to verify

- [ ] Hackathon rules: can we pre-build, is the theme fixed, what counts as "using" each platform, are API credits provided?
- [ ] Nasiko: exact agent template and `AgentCard.json` schema, auth on the gateway, whether a DronaHQ agent can be registered.
- [ ] DronaHQ: map component, REST connector auth options, polling or timer actions, PDF add-on, free plan limits, credits.
- [ ] Anakin: parameters for AI JSON extraction, whether property portals scrape reliably, actual free credits, any Wire endpoint useful for property or map data.
- [ ] Portal and geocoder terms of service.
- [ ] Which city has good OSM coverage and accessible listing pages.
- [ ] Which LLM provider and budget, and whether local models are acceptable for narratives.
- [ ] Two real conversations: one aspiring store owner and one broker or franchise person.

---

## 25. Roadmap (after the hackathon)

- More categories: gym, salon, restaurant, grocery, electronics, co-working.
- Multi-city rollout with automatic ingestion.
- Isochrone catchments and time-of-day heatmaps.
- Outcome feedback loop: owners report performance, weights are recalibrated per category and city.
- Real footfall data through partnerships.
- Broker and franchise dashboards (portfolio of candidate sites, pipeline tracking).
- WhatsApp delivery of shortlists and reports.
- Voice assistant for owners (earlier idea) and wholesaler price comparison (earlier idea) as separate modules.
- Monetisation options: pay-per-report, subscription for brokers and franchises, lender API. Validate with real buyers first.

---

## 26. Appendix

### A. OSM tag mapping (`config/osm_tags.yaml`)

| Internal category | OSM tags |
|---|---|
| school | `amenity=school` |
| college | `amenity=college` |
| university | `amenity=university` |
| mall | `shop=mall` |
| department_store | `shop=department_store` |
| supermarket | `shop=supermarket` |
| marketplace | `amenity=marketplace` |
| hospital | `amenity=hospital` |
| clinic | `amenity=clinic` |
| doctors | `amenity=doctors` |
| diagnostic_lab | `healthcare=laboratory` |
| pharmacy | `amenity=pharmacy` |
| cafe | `amenity=cafe` |
| restaurant | `amenity=restaurant` |
| clothes | `shop=clothes` |
| boutique | `shop=boutique` |
| shoes | `shop=shoes` |
| jewelry | `shop=jewelry` |
| tailor | `craft=tailor` |
| bank / atm | `amenity=bank`, `amenity=atm` |
| bus_stop | `highway=bus_stop` |
| rail_or_metro | `railway=station`, `public_transport=station` |
| place_of_worship | `amenity=place_of_worship` |
| cinema | `amenity=cinema` |
| gym | `leisure=fitness_centre` |
| park | `leisure=park` |
| coworking | `amenity=coworking_space`, `office=coworking` |
| office | `office=*` |
| parking | `amenity=parking` |
| car_showroom | `shop=car` |
| hotel | `tourism=hotel` (use `stars` tag for premium) |
| residential_building | `building=apartments`, `building=residential` |
| landuse | `landuse=residential`, `landuse=commercial`, `landuse=retail` |

### B. Category config example (`config/categories/cafe.yaml`)

```yaml
category: cafe
version: "2026-09-a"
h3_resolution: 9
catchment_k: 2
decay_lambda_m: 350

tier_targets: { budget: 0.30, mid: 0.55, premium: 0.80 }
tier_fit: { shortfall_penalty: 2.0, overshoot_penalty: 0.8 }

weights:
  F1_anchor_footfall: 0.28
  F2_affluence_fit: 0.20
  F3_residential_demand: 0.07
  F4_retail_cluster: 0.05
  F5_competition_inverted: 0.10
  F6_gap_opportunity: 0.10
  F7_accessibility: 0.08
  F8_rent_efficiency: 0.07
  F9_growth_momentum: 0.05

poi_weights:            # landmark type -> footfall weight for this category
  college: 1.0
  university: 1.0
  office: 0.9
  coworking: 0.9
  mall: 0.7
  rail_or_metro: 0.6
  cinema: 0.5
  park: 0.4
  gym: 0.4
  school: 0.2
  hospital: 0.2

competitor_categories: [cafe]
complementary_categories: [restaurant, bank]

answer_modifiers:
  target_customer.students: { college: 1.3 }
  target_customer.young_professionals: { office: 1.2, coworking: 1.2 }

hard_filters:
  rent_budget_multiplier: 1.2
  exclude_land_use: []
  min_confidence_ranked: 0.25
```

Landmark weight starting points for the other two categories:

| Landmark | Clothing | Pharmacy |
|---|---|---|
| mall | 1.0 | 0.2 |
| marketplace | 1.0 | 0.3 |
| college / university | 0.6 | 0.2 |
| rail_or_metro / bus_stop | 0.6 | 0.3 |
| cinema | 0.5 | 0.1 |
| place_of_worship | 0.4 | 0.2 |
| office | 0.3 | 0.2 |
| school | 0.2 | 0.2 |
| hospital | 0.1 | 1.0 |
| clinic / doctors / diagnostic_lab | 0.1 | 0.9 |
| supermarket | 0.3 | 0.4 |

### C. Overpass query template

```
[out:json][timeout:120];
(
  node["amenity"="college"]({{south}},{{west}},{{north}},{{east}});
  way["amenity"="college"]({{south}},{{west}},{{north}},{{east}});
  node["shop"="mall"]({{south}},{{west}},{{north}},{{east}});
  way["shop"="mall"]({{south}},{{west}},{{north}},{{east}});
);
out center tags;
```

Group several tags per call, cache responses, and respect the public server's usage limits. For larger areas, use a regional OSM extract loaded locally.

### D. H3 helpers

```python
import h3   # note: v4 API names shown; v3 used geo_to_h3 and k_ring

cell = h3.latlng_to_cell(lat, lon, 9)
neighbours = h3.grid_disk(cell, 2)      # cell plus rings up to k=2
centre_lat, centre_lon = h3.cell_to_latlng(cell)
```

### E. Scoring skeleton (`scoring/score.py`)

```python
import numpy as np
import pandas as pd

def pct(series: pd.Series) -> pd.Series:
    """Percentile rank 0..1 within the city."""
    return series.rank(pct=True)

def tier_fit(affluence: float, tier: str, cfg: dict) -> float:
    t = cfg["tier_targets"][tier]
    short = max(0.0, t - affluence)
    over = max(0.0, affluence - t)
    p = cfg["tier_fit"]
    return float(np.clip(1 - p["shortfall_penalty"] * short - p["overshoot_penalty"] * over, 0, 1))

def anchor_footfall(cell_pois: list[dict], poi_weights: dict, lam: float) -> float:
    return sum(
        poi_weights.get(p["category"], 0.0) * np.exp(-p["distance_m"] / lam)
        for p in cell_pois
    )

def score_cell(f: dict, weights: dict) -> tuple[float, dict]:
    """f holds normalised 0..1 values; F5 must already be inverted."""
    contributions = {k: 100 * weights[k] * f[k] for k in weights}
    return sum(contributions.values()), contributions

def confidence(poi_cov: float, listing_cov: float, recency: float, price_cov: float) -> float:
    return 0.4 * poi_cov + 0.3 * listing_cov + 0.2 * recency + 0.1 * price_cov
```

Tests to write: weights sum to 1.0 for every config; contributions sum to score; score stays in [0, 100]; premium tier lowers scores in low-affluence cells; the clothing worked example (5.8) stays within a tolerance of the documented numbers.

### F. Narrative prompt guardrails

- Input: the recommendation JSON only. No web access.
- Rule: "Use only numbers and facts present in the input. If something is missing, say it is not available."
- Output: 3 to 5 sentences, plain language, mention top 2 drivers and top 1 risk, end with one on-site check to do.
- Post-check: extract numbers from the text and confirm they appear in the input JSON. Regenerate once if not.

### G. Glossary

- **H3 cell:** hexagonal grid cell used as the candidate unit.
- **k-ring:** the cell plus its neighbours up to k steps.
- **Affluence index:** 0 to 1 proxy for local spending power.
- **Tier fit:** how well area affluence matches the store's premium level.
- **Gap opportunity:** demand relative to same-tier supply.
- **Confidence:** how much data supports a zone's score.
- **Wire:** Anakin's pre-built structured endpoints for specific sites.
- **AgentCard:** Nasiko's structured description of an agent's capabilities.
