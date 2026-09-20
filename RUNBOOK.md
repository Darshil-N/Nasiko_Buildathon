# SiteScout Runbook

This document describes how to build, run, and test the SiteScout platform locally.

## Architecture Prerequisites
- Python 3.11.9 (minimum 3.10)
- PostgreSQL with PostGIS extension (provided via Docker)
- Nasiko Agent Engine

## Setup Instructions

1. **Environment Setup:**
   Copy `.env.example` to `.env` and fill in your API keys (e.g., `OPENAI_API_KEY`, `BACKEND_API_KEY`).

2. **Virtual Environment:**
   ```bash
   python -m venv .venv
   source .venv/Scripts/activate  # Windows: .\.venv\Scripts\Activate.ps1
   pip install -r requirements/dev.txt
   pip install -r requirements/frontend.txt
   ```

3. **Infrastructure (Database & Backend):**
   ```bash
   docker-compose up -d db
   alembic upgrade head
   fastapi run backend/app/main.py --port 8000
   ```

4. **Nasiko Engine:**
   Run the Nasiko API gateway according to Nasiko-Labs instructions on port 9100.
   Deploy agents: `nasiko agent upload-directory agents/scoring`

5. **Streamlit Frontend:**
   ```bash
   streamlit run frontend/streamlit_app/app.py
   ```
   Access the app at `http://localhost:8501`.

## Refresh Procedures
- **OSM Data:** Periodically re-run the `geo-data-agent` pipelines or snapshot extraction script (`scripts/seed_demo.py`) to pull fresh geometries for new bounds.
- **Rent CSV Import:** Use `python pipelines/rent_data/importer.py path/to/rent.csv` to upsert latest rental listings and compute IDW k-ring estimations.
- **Brand Rules:** Edit `config/brands_premium.yaml` and restart the backend to apply changes in classification logic.

## Testing & Validation
- **Unit & Property Tests:**
  `pytest tests/`
  Validates strict schemas, monotonic scoring constraints, and math correctness.
- **Evaluation Back-Test:**
  `python scripts/backtest.py`
  Runs end-to-end benchmarking against the live backend to calculate average latency, top-10 confidence, and expected heuristic hits.
