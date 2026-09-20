# Handoff for Agent B (second Claude session)

You are **Agent B**. Another Claude session, **Agent A**, is working on the same project at the same time on this same machine and folder. This file tells you what the project is, the rules you must follow, which part of the work is yours, and how to avoid clashing with Agent A. Read it fully before doing anything.

## 0. Start here (2026-09-20 update — read this before section 5)

Section 5 below is the *original* track assignment from when this file was first written. Most of
it is already done (contracts, config layer, LLM client, scoring library, rent CSV logic, API
schemas — check `progress.md`'s summary table and Phase sections before redoing anything). The
owner has limited time and does not want either agent idle, so work straight through this list in
order without stopping to check in between items; only stop for a genuine owner-decision blocker,
which you log as a Handoffs row in `progress.md` (section 1) as usual, then move to the next item.

1. **Phase 6 Streamlit gaps** (`progress.md` "## Phase 6", currently 66% done), in `frontend/`
   only: 6.2.3 progress polling against `GET /v1/analyses/{id}` with a visible progress state and
   a clear failure state (including `NO_CANDIDATES`); 6.4.2/6.4.3 map overlay and interaction
   (check what's already working — 6.2.4 "map with hex overlay" is already ticked done, so this
   may be a stale duplicate entry rather than genuinely missing work); 6.6 UX edge-case states
   (city-not-ready, `NO_CANDIDATES`, low-confidence warning, tier-area mismatch, out-of-scope chat
   reply, upstream-failure-with-snapshot-date, data-source caveats, "rent data not available");
   6.7.1 a short README in `frontend/streamlit_app/` (skip screenshots, note them as pending).
2. **D-17: draft `config/brands_premium.yaml`** — premium brand lists per category (cafe,
   clothing, pharmacy) x tier (budget, mid, premium) for Bengaluru, replacing the current 4-brand
   placeholder (also fix the placeholder that lists a pharmacy chain as premium — that's wrong).
   Needs owner approval before use for real scoring: draft it, add a Handoffs row for the owner to
   review, and move on rather than blocking on the approval.
3. **Phase 7 validation** (`progress.md` "## Phase 7"): 7.2.2 run `scripts/backtest.py` for all
   three categories against the real Bengaluru database (it's loaded and the backend is live at
   `localhost:8000`) and record whether clothing ranks markets above residential, cafe ranks
   colleges/offices high, and pharmacy ranks hospitals/dense housing high; 7.4.1/7.4.2
   weight-perturbation sensitivity (±20%, top-10 change report) and tier-direction check (premium
   should move toward high-affluence zones); 7.6.1 record the pitch numbers (top-3 hit rate,
   average confidence of top 10, end-to-end latency).
4. **Phase 8 items that are yours per the work split** (`progress.md` "## Phase 8"): 8.1.1/8.1.2
   feature-completion checks (compare, what-if, chat work for all three categories; result under
   30s; tier change re-ranks); 8.4.1/8.4.2 README and runbook; 8.6.2 slide content
   (problem/solution, limitations, back-test numbers, roadmap — text content is enough, not an
   actual deck).

Agent A has already deployed the `sitescout-scoring` Nasiko agent and wired the backend to call it
(commit `556d33b`); see `progress.md` Handoffs row 15 for details if you need to know how scoring
now runs. Working rules below (git protocol, folder ownership, definition of done) still apply.

## 1. Read these first (in this order)

1. `plan.md`: the plan. Read sections 1 to 5 and **section 9 (parallel work split)**. Your phases and steps use IDs like `3.2.1`.
2. `progress.md`: the tracker, decision log, approval log, and handoffs.
3. `architecture-1.md`: the original design. It is the owner's file and **must not be edited**. Read sections 1, 5, 6, 7, 9.4, 10, 14 and Appendices B and E. Note that plan.md overrides it where they differ (the MVP is free; Anakin and DronaHQ are removed).

## 2. The project in one paragraph

SiteScout is an AI store-location advisor. A user picks a city (Bengaluru first), a category (cafe, clothing store or pharmacy) and a tier (lower class, medium class, niche; internally `budget`, `mid`, `premium`), and gets ranked zones with an explanation. Scoring is deterministic Python and category-aware; an LLM only writes narratives and chat answers. The MVP must be **free** to build and run. **Nasiko** (an agent platform, already running locally) is compulsory. The interface is a **Streamlit** app. Data comes from OpenStreetMap plus an optional rent CSV from the owner. The database is PostgreSQL + PostGIS in Docker, owned by Agent A.

## 3. Rules from the owner (follow all of them)

1. Without asking the owner first, **not even a single letter of existing content may be changed**. Never edit `architecture-1.md`, anything in `D:\Projects\Nasiko`, or a file owned by Agent A. Creating the new files your own steps call for is fine.
2. **No database changes**, ever, without asking the owner. You should not need a database at all: work on fixtures and in-memory data frames.
3. Keep `plan.md` and `progress.md` current. Tick your micro-tasks in `progress.md` as you finish them.
4. **Production-grade code quality**: standards are in `plan.md` section 4 (typing, ruff, mypy, pytest, error envelope, idempotency, config over code, no secrets, structured logging, free-only dependencies).
5. **Never push anything.** Local commits are fine.
6. **Assume nothing.** When something is unspecified or you are stuck, ask the owner in your own chat and record the question and answer in the Decision Log.

(The owner's numbering skipped 5 and 6 in their original message, so two rules may be missing; decision D-16 asks about it.)

Also: never print or copy secret values; every dependency must be free and open source; no paid APIs.

## 4. Your environment

- Repo root: `D:\Projects\Nasiko_Buildathon`. Git is initialised locally; there is no remote.
- Python 3.11.9 virtual environment at `.venv` (already created with the dependencies in `requirements/dev.txt`).
  - Windows Git Bash: `.venv/Scripts/python.exe -m pytest`
  - PowerShell: `.\.venv\Scripts\python.exe -m pytest`
- Checks you run before calling anything done: `ruff check .`, `ruff format --check .`, `mypy`, `pytest` (all via the venv).
- Local LLM for manual testing only: Ollama at `http://localhost:11434/v1`, model `qwen2.5:7b-instruct` (clean, 7.6B, supports tools) and `nomic-embed-text` for embeddings. **Do not use the models named `Antraa-*` or `fairsynth-*`**: they have unrelated system prompts and a dataset baked in (8,000+ tokens per request). Automated tests must mock the LLM.
- You do not start, stop or configure Docker or Nasiko. Agent A operates them.

## 5. Your track

**Your steps (IDs from plan.md):**

| Area | Steps |
|---|---|
| Config layer | 1.2.2, 1.2.3 (needs the owner), 1.2.4 |
| Shared LLM client | 1.7.1 to 1.7.4 |
| Scoring library | 3.1.x, 3.2.x, 3.3.1, 3.3.3, 3.4.1 to 3.4.3, 3.5.x, 3.7.1, 3.7.2, 3.7.4 to 3.7.6, 3.9.x |
| Rent CSV pure logic | 2.1.1 to 2.1.4, 2.2.1, 2.2.2, 2.3.x (in `pipelines/rent_data/`) |
| API schemas | 4.3.1, 4.3.2 (in `backend/app/schemas/`), and later 4.6.4 (PDF renderer) |
| Streamlit | 0.5.4 (map spike), then Phase 6 |
| Later | Phase 7 (validation), 8.1, 8.4, 8.6 |

**Do NOT implement yet (blocked on the owner):**
- 3.3.2, 3.4.4 no-rent fallback and 3.7.3: the "no rent data" formulas (decision D-22 is deferred). Implement only the original architecture formulas for the with-rent case and structure the code so a variant can be added later. Do not invent the variant.
- 3.6 accuracy boosters (D-18, D-19).
- 1.2.3 premium brand list content (D-17) and the Streamlit user roles (D-23): ask the owner when you reach them.

**Suggested order, because Agent A depends on the first items:**

1. **`shared/contracts.py`** (Pydantic models and column definitions): rows for cells, POIs (category, h3_index, lat/lon, name, brand, tier_guess), listings, market signals, and the `CellFeatures` output (F1 to F9 raw and normalised values, affluence, rent estimate and its `estimated` flag, confidence inputs). Base it on `architecture-1.md` section 8.2 and section 5. Tell Agent A when it is ready by adding a row to the Handoffs table in `progress.md`.
2. **Config layer**: `config/categories/{cafe,clothing,pharmacy}.yaml` (values exactly as in section 5.6 and Appendix B), the tier labels (`budget` shown as "Lower class", `mid` as "Medium class", `premium` as "Niche"), and `shared/config.py` (Pydantic loader and validator: weights sum to 1.0, known feature keys, tier targets within 0 and 1).
3. **Scoring library** in `scoring/`, following Appendix E, section 5 and the tests listed in plan step 3.9. Build it on synthetic fixtures in `tests/scoring/`. Include the worked example from section 5.8 as a test.
4. **LLM client** in `shared/llm/` (step 1.7): OpenAI-compatible, Ollama primary, OpenRouter free backup, strict JSON output helper with Pydantic validation, bounded retries, timeouts, automatic fallback. Mocked tests only.
5. **API schemas and error envelope** in `backend/app/schemas/` (step 4.3), from `architecture-1.md` sections 10.2 to 10.4.
6. **Streamlit**: the map spike (0.5.4), then a Phase 6 skeleton with a client interface that has two implementations, an HTTP one and a stub one returning fixture JSON, so you can build the screens before Agent A's backend exists.
7. **Rent CSV pure logic** (Phase 2 items listed above).

## 6. Folder ownership

You own: `scoring/`, `shared/`, `backend/app/schemas/`, `backend/app/services/report_pdf.py`, `pipelines/rent_data/`, `config/categories/`, `config/brands_premium.yaml`, `frontend/`, `tests/scoring/`, `tests/shared/`, `scripts/backtest.py`, `data/backtest/`.

Agent A owns everything else: `backend/` (rest), `agents/`, `pipelines/` (rest), `config/osm_tags.yaml`, `data/raw`, `data/snapshots`, `scripts/` (rest), Docker files, migrations, and the Nasiko stack. Do not edit those files. If you need a change there, add a row to the Handoffs table in `progress.md`.

Shared files (`plan.md`, `progress.md`, `pyproject.toml`, `requirements/*.txt`, `.gitignore`, `.env.example`, `.pre-commit-config.yaml`): make only small, targeted edits.

## 7. Working protocol

- **Progress:** tick your micro-tasks in `progress.md` with targeted edits (never rewrite the file). After a batch, run `python scripts/update_progress_summary.py` from the repo root to refresh the summary table.
- **Handoffs:** requests between agents go in the Handoffs table in `progress.md` (from, to, what, status).
- **Commits:** local only. Stage only your own paths (`git add scoring shared ...`, never `git add -A`), never amend or rewrite history, and start commit subjects with `[B]`. End commit messages with the attribution line your own environment gives you.
- **Dependencies:** add packages your area needs in a new `requirements/frontend.txt` (Streamlit, folium and so on) or in `requirements/base.txt` (announce this in Handoffs). Free and open source only.
- **Tests:** no network and no database in default runs. Mark anything that needs them `@pytest.mark.integration`.
- **Questions for the owner:** ask in your own chat, and record them in the Decision Log (`progress.md` section 2) with a new `D-nn` row.

## 8. Definition of done for each deliverable

Typed and documented (docstrings state units and ranges); ruff and mypy clean; tests written and passing; no secrets; no paid dependency; progress.md ticked; a Handoffs row added if Agent A must act.
