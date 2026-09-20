"""Screen 3: Results (6.2.3, 6.4, 6.6)."""

import time

import folium
import h3
import streamlit as st
from streamlit_folium import st_folium  # type: ignore[import-untyped]

from frontend.streamlit_app.client import APIError, client

st.set_page_config(page_title="Results - SiteScout", layout="wide")

st.title("Analysis Results")

if "analysis_id" not in st.session_state:
    st.warning("No active analysis. Please start a new one.")
    if st.button("Go to New Analysis"):
        st.switch_page("pages/2_New_Analysis.py")
    st.stop()

analysis_id = st.session_state["analysis_id"]


def poll_analysis(analysis_id: str) -> dict:
    placeholder = st.empty()
    while True:
        try:
            resp = client.get_analysis(analysis_id)
            status = resp.get("status", "unknown")
            if status == "done":
                placeholder.empty()
                return resp
            elif status == "failed":
                placeholder.empty()
                st.error("Analysis failed processing on the server.")
                st.stop()
            else:
                with placeholder.container():
                    st.info(f"Analysis is currently: **{status}**... please wait.")
                time.sleep(2.0)
        except APIError as e:
            placeholder.empty()
            if e.code == "NO_CANDIDATES":
                st.error(
                    "No zones matched your strict constraints (NO_CANDIDATES). "
                    "Try relaxing budget or size."
                )
            elif e.code == "CITY_NOT_READY":
                st.error("The selected city is not yet ready for analysis (CITY_NOT_READY).")
            else:
                st.error(f"Failed to fetch analysis: {e.message}")
            if e.details and isinstance(e.details, str):
                st.write(f"Details: {e.details}")
            st.stop()
        except Exception as e:
            placeholder.empty()
            st.error(f"Unexpected error: {e}")
            st.stop()


# Actually fetch it
resp = poll_analysis(analysis_id)

st.success("Analysis complete!")

# 6.6 Edge cases display (caveats)
data_notes = resp.get("data_notes", [])
if data_notes:
    with st.expander("Data Caveats & Notices", expanded=True):
        for note in data_notes:
            st.warning(note)

if not resp.get("recommendations"):
    st.warning("Analysis completed, but no recommendations were returned.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["Map View", "Compare", "What-if"])

with tab1:
    recs = resp["recommendations"]

    # Check low confidence warning
    avg_conf = sum(r.get("confidence", 1.0) for r in recs) / len(recs) if recs else 0
    if avg_conf < 0.5:
        st.warning("Low confidence warning: The data used for this analysis is sparse or outdated.")

    # Render Map (6.4.2)
    m = folium.Map(location=[18.5204, 73.8567], zoom_start=12, tiles="CartoDB positron")

    features = []
    for r in recs:
        h3_idx = r.get("h3_index")
        if not h3_idx:
            continue

        boundary = h3.cell_to_boundary(h3_idx)
        coords = [[lon, lat] for lat, lon in boundary]
        coords.append(coords[0])

        score = r.get("score", 0)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "zone_name": r.get("zone_name", "Unknown"),
                    "score": score,
                    "rank": r.get("rank", 999),
                },
            }
        )

    geojson_data = {"type": "FeatureCollection", "features": features}

    folium.GeoJson(
        geojson_data,
        style_function=lambda f: {
            "fillColor": (
                "green"
                if f["properties"]["score"] > 80
                else "orange"
                if f["properties"]["score"] > 50
                else "red"
            ),
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.5,
        },
        highlight_function=lambda f: {"weight": 3, "fillOpacity": 0.7},
        tooltip=folium.GeoJsonTooltip(
            fields=["rank", "zone_name", "score"],
            aliases=["Rank:", "Zone:", "Score:"],
        ),
    ).add_to(m)

    col_map, col_details = st.columns([2, 1])
    with col_map:
        st_data = st_folium(m, width="100%", height=600, returned_objects=["last_active_drawing"])

    with col_details:
        st.subheader("Selected Zone Details")
        if st_data and st_data.get("last_active_drawing"):
            props = st_data["last_active_drawing"]["properties"]
            st.write(f"**Rank:** {props['rank']}")
            st.write(f"**Zone:** {props['zone_name']}")
            st.write(f"**Score:** {props['score']:.1f}")
            # Could look up full recommendation here to show narrative etc.
        else:
            st.info("Click a hexagon to see details.")

with tab2:
    st.info("Compare zones side-by-side.")

with tab3:
    st.info("What-if panel to adjust tier or budget and re-score.")
