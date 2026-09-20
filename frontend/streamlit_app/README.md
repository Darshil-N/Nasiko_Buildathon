# SiteScout Streamlit App

This is the interactive frontend for the SiteScout AI site selection platform.

## Structure
- `app.py`: The main entry point and landing page.
- `pages/`:
  - `1_My_Analyses.py`: List of past runs.
  - `2_New_Analysis.py`: The wizard to define city, category, tier, and constraints.
  - `3_Results.py`: The main results dashboard (map overlay, comparisons, what-if).
  - `4_Admin.py`: Administrative controls for data refresh and weight editing.
- `client.py`: The typed HTTP client interfacing with the backend API.

## Pending items
- Screenshots of the working UI.
- Full integration with all endpoints as backend completes them.
