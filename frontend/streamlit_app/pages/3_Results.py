"""Screen 3: Results Dashboard (6.2.3, 6.4, 6.6)."""
# ruff: noqa: E501

import time

import folium
import h3
import streamlit as st
from streamlit_folium import st_folium  # type: ignore[import-untyped]

from frontend.streamlit_app.client import APIError, client
from frontend.streamlit_app.theme import apply_apple_theme

st.set_page_config(
    page_title="Results | SiteScout", layout="wide", initial_sidebar_state="collapsed"
)
apply_apple_theme()

if "analysis_id" not in st.session_state:
    st.warning("No active analysis. Please configure a new evaluation.")
    if st.button("Configure Analysis"):
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
                st.error("Evaluation failed during agent processing.")
                st.stop()
            else:
                with placeholder.container():
                    st.info(f"Evaluation in progress ({status}). The agents are computing.")
                    st.progress(50)
                time.sleep(2.0)
        except APIError as e:
            placeholder.empty()
            if e.code == "NO_CANDIDATES":
                st.error(
                    "No zones matched your financial constraints. Please relax parameters and retry."
                )
            elif e.code == "CITY_NOT_READY":
                st.error("The selected city is not yet ready for analysis.")
            else:
                st.error(f"Error fetching data: {e.message}")
            if e.details and isinstance(e.details, str):
                st.write(f"Details: {e.details}")
            st.stop()
        except Exception as e:
            placeholder.empty()
            st.error(f"System Error: {e}")
            st.stop()


resp = poll_analysis(analysis_id)
recs = resp.get("recommendations", [])

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<h1>Intelligence.</h1>", unsafe_allow_html=True)
st.markdown(f"<p>Analysis ID: {analysis_id}</p>", unsafe_allow_html=True)

data_notes = resp.get("data_notes", [])
if data_notes:
    with st.expander("Data Integrity Notices", expanded=True):
        for note in data_notes:
            st.warning(note)

if not recs:
    st.warning("Evaluation completed. No viable recommendations found.")
    st.stop()

st.markdown("<br>", unsafe_allow_html=True)

# Metrics
col_m1, col_m2, col_m3, col_m4 = st.columns(4)
avg_conf = sum(r.get("confidence", 1.0) for r in recs) / len(recs)
top_score = recs[0].get("score", 0)

with col_m1:
    st.markdown(
        f'<div class="metric-val">{len(recs)}</div><div class="metric-lbl">Viable Candidates</div>',
        unsafe_allow_html=True,
    )
with col_m2:
    st.markdown(
        f'<div class="metric-val">{top_score:.1f}</div><div class="metric-lbl">Highest Score</div>',
        unsafe_allow_html=True,
    )
with col_m3:
    st.markdown(
        f'<div class="metric-val">{avg_conf * 100:.0f}%</div><div class="metric-lbl">Data Confidence</div>',
        unsafe_allow_html=True,
    )
with col_m4:
    st.markdown(
        '<div class="metric-val">OK</div><div class="metric-lbl">Model Status</div>',
        unsafe_allow_html=True,
    )

st.markdown("<br><br>", unsafe_allow_html=True)

if avg_conf < 0.5:
    st.warning("Precision notice: Local data density is sparse. Approximations applied.")

tab_map, tab_leaderboard, tab_compare = st.tabs(["Interactive Map", "Leaderboard", "Compare"])

with tab_map:
    col_map, col_details = st.columns([7, 3])

    with col_map:
        center_lat, center_lon = 12.9716, 77.5946
        if recs:
            first_h3 = recs[0].get("h3_index")
            if first_h3:
                center_lat, center_lon = h3.cell_to_latlng(first_h3)

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            tiles="CartoDB positron",
            attr="SiteScout Intelligence",
        )

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
                    "id": r.get("rank"),
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {
                        "zone_name": r.get("zone_name", "Unknown"),
                        "score": score,
                        "rank": r.get("rank", 999),
                        "confidence": r.get("confidence", 0),
                    },
                }
            )

        geojson_data = {"type": "FeatureCollection", "features": features}

        folium.GeoJson(
            geojson_data,
            style_function=lambda f: {
                "fillColor": "#000000"
                if f["properties"]["score"] > 80
                else "#86868b"
                if f["properties"]["score"] > 60
                else "#e5e5ea",
                "color": "#1d1d1f",
                "weight": 1,
                "fillOpacity": 0.8,
            },
            highlight_function=lambda f: {"weight": 2, "fillOpacity": 0.95, "color": "#000000"},
            tooltip=folium.GeoJsonTooltip(
                fields=["rank", "zone_name", "score"],
                aliases=["Rank", "Zone", "Score"],
                style="font-family: -apple-system, sans-serif; font-size: 13px; font-weight: 600; border-radius: 8px;",
            ),
        ).add_to(m)

        st_data = st_folium(m, width="100%", height=700, returned_objects=["last_active_drawing"])

    with col_details:
        st.markdown("<div class='apple-card'>", unsafe_allow_html=True)

        selected_rank = None
        if st_data and st_data.get("last_active_drawing"):
            selected_rank = st_data["last_active_drawing"]["properties"]["rank"]

        if selected_rank:
            rec = next((r for r in recs if r.get("rank") == selected_rank), None)
            if rec:
                st.markdown(f"<h3>{rec['zone_name']}</h3>", unsafe_allow_html=True)
                st.markdown(
                    f"<p style='font-size: 1rem; color: #1d1d1f; font-weight: 600;'>Rank {rec['rank']} &nbsp;|&nbsp; Score {rec['score']:.1f}/100 &nbsp;|&nbsp; Confidence {rec['confidence'] * 100:.0f}%</p>",
                    unsafe_allow_html=True,
                )

                st.markdown(
                    "<br><p style='font-weight: 600; margin-bottom: 0.5rem;'>Primary Catalysts</p>",
                    unsafe_allow_html=True,
                )
                for driver in rec.get("top_drivers", []):
                    st.markdown(f'<div class="pill-pos">{driver}</div>', unsafe_allow_html=True)

                st.markdown(
                    "<br><p style='font-weight: 600; margin-bottom: 0.5rem; margin-top: 1rem;'>Risk Profile</p>",
                    unsafe_allow_html=True,
                )
                for risk in rec.get("top_risks", []):
                    st.markdown(f'<div class="pill-neg">{risk}</div>', unsafe_allow_html=True)

                st.markdown("<br><hr>", unsafe_allow_html=True)
                if "narrative" in rec:
                    st.markdown(
                        "<p style='font-weight: 600; margin-bottom: 0.5rem;'>Analyst Briefing</p>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f"<p style='font-size: 0.95rem; color: #1d1d1f;'>{rec['narrative']}</p>",
                        unsafe_allow_html=True,
                    )
        else:
            st.markdown(
                "<p>Select a zone on the map to review the detailed intelligence briefing.</p>",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

with tab_leaderboard:
    st.markdown("<div class='apple-card'>", unsafe_allow_html=True)
    for r in recs[:10]:
        st.markdown(f"<h3>{r['rank']}. {r['zone_name']}</h3>", unsafe_allow_html=True)
        st.markdown(
            f"<p style='font-weight: 600;'>Score: {r['score']:.1f}</p>", unsafe_allow_html=True
        )
        st.markdown(
            f"<p>Drivers: {', '.join(r.get('top_drivers', []))}</p>", unsafe_allow_html=True
        )
        st.divider()
    st.markdown("</div>", unsafe_allow_html=True)

with tab_compare:
    st.info("Comparison module pending integration.")
