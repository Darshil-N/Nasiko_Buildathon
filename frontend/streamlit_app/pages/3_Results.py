"""Screen 3: Results Dashboard (6.2.3, 6.4, 6.6)."""

import time

import folium
import h3
import streamlit as st
from streamlit_folium import st_folium  # type: ignore[import-untyped]

from frontend.streamlit_app.client import APIError, client

st.set_page_config(
    page_title="Intelligence Dashboard | SiteScout",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp {
        background-color: #FAF8F5;
        color: #2C2A29;
    }
    h1, h2, h3, h4 {
        font-family: 'Georgia', serif;
        color: #1A1A1A;
        font-weight: normal;
    }
    .metric-card {
        background-color: #FFFFFF;
        padding: 2rem 1.5rem;
        border-radius: 2px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02);
        border: 1px solid #EAE6DF;
        text-align: center;
    }
    .metric-value {
        font-size: 2.5rem;
        font-family: 'Georgia', serif;
        color: #2C2A29;
        margin-bottom: 0.5rem;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #8C8273;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .driver-pill {
        display: inline-block;
        background-color: #F0F4F1;
        color: #2F4F38;
        padding: 6px 14px;
        border-radius: 2px;
        font-size: 0.75rem;
        margin: 4px 4px 4px 0;
        border: 1px solid #D6E0D9;
        letter-spacing: 0.03em;
    }
    .risk-pill {
        display: inline-block;
        background-color: #FBF0F0;
        color: #6B2C2C;
        padding: 6px 14px;
        border-radius: 2px;
        font-size: 0.75rem;
        margin: 4px 4px 4px 0;
        border: 1px solid #EAD5D5;
        letter-spacing: 0.03em;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 3rem;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 0;
        color: #5C5855;
        font-size: 1rem;
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        color: #1A1A1A;
        border-bottom: 2px solid #2C2A29 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

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
                st.error("Analysis failed processing on the server.")
                st.stop()
            else:
                with placeholder.container():
                    st.info(
                        f"Analysis in progress (Status: {status}). Please wait while the agents evaluate the data."
                    )
                    st.progress(50)
                time.sleep(2.0)
        except APIError as e:
            placeholder.empty()
            if e.code == "NO_CANDIDATES":
                st.error(
                    "No Zones Found: No zones matched your strict constraints. Please relax your financial parameters."
                )
            elif e.code == "CITY_NOT_READY":
                st.error("The selected city is not yet ready for analysis.")
            else:
                st.error(f"Failed to fetch analysis: {e.message}")
            if e.details and isinstance(e.details, str):
                st.write(f"Details: {e.details}")
            st.stop()
        except Exception as e:
            placeholder.empty()
            st.error(f"System Error: {e}")
            st.stop()


resp = poll_analysis(analysis_id)
recs = resp.get("recommendations", [])

st.title("Intelligence Dashboard")
st.markdown(
    f"<span style='color: #8C8273;'>Analysis Reference: {analysis_id}</span>",
    unsafe_allow_html=True,
)
st.markdown("<br>", unsafe_allow_html=True)

data_notes = resp.get("data_notes", [])
if data_notes:
    with st.expander("Data Integrity Notices", expanded=True):
        for note in data_notes:
            st.warning(note)

if not recs:
    st.warning("Evaluation completed, but no viable recommendations were returned.")
    st.stop()

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
avg_conf = sum(r.get("confidence", 1.0) for r in recs) / len(recs)
top_score = recs[0].get("score", 0)

with col_m1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-value">{len(recs)}</div><div class="metric-label">Viable Candidates</div></div>',
        unsafe_allow_html=True,
    )
with col_m2:
    st.markdown(
        f'<div class="metric-card"><div class="metric-value">{top_score:.1f}/100</div><div class="metric-label">Highest Score</div></div>',
        unsafe_allow_html=True,
    )
with col_m3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-value">{avg_conf * 100:.1f}%</div><div class="metric-label">Data Confidence</div></div>',
        unsafe_allow_html=True,
    )
with col_m4:
    st.markdown(
        '<div class="metric-card"><div class="metric-value">Active</div><div class="metric-label">Model Status</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("<br><br>", unsafe_allow_html=True)

if avg_conf < 0.5:
    st.warning(
        "Data precision notice: Information density in this region is currently sparse. Estimations are applied."
    )

tab_map, tab_leaderboard, tab_compare = st.tabs(["Interactive Map", "Leaderboard", "Compare Zones"])

with tab_map:
    col_map, col_details = st.columns([7, 3])

    with col_map:
        center_lat, center_lon = 12.9716, 77.5946
        if recs:
            first_h3 = recs[0].get("h3_index")
            if first_h3:
                center_lat, center_lon = h3.cell_to_latlng(first_h3)

        m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")

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
                "fillColor": "#3E5748"
                if f["properties"]["score"] > 80
                else "#B89C72"
                if f["properties"]["score"] > 60
                else "#8C8273",
                "color": "#1A1A1A",
                "weight": 1,
                "fillOpacity": 0.7,
            },
            highlight_function=lambda f: {"weight": 2, "fillOpacity": 0.9, "color": "#1A1A1A"},
            tooltip=folium.GeoJsonTooltip(
                fields=["rank", "zone_name", "score"],
                aliases=["Rank:", "Zone:", "Score:"],
                style="font-family: 'Inter', sans-serif; font-size: 13px;",
            ),
        ).add_to(m)

        st_data = st_folium(m, width="100%", height=700, returned_objects=["last_active_drawing"])

    with col_details:
        st.markdown("<h3 style='margin-top:0;'>Zone Analysis</h3>", unsafe_allow_html=True)

        selected_rank = None
        if st_data and st_data.get("last_active_drawing"):
            selected_rank = st_data["last_active_drawing"]["properties"]["rank"]

        if selected_rank:
            rec = next((r for r in recs if r.get("rank") == selected_rank), None)
            if rec:
                st.markdown(f"**Rank {rec['rank']} &mdash; {rec['zone_name']}**")
                st.progress(rec["score"] / 100.0)
                st.markdown(
                    f"<span style='color:#5C5855; font-size: 0.9rem;'>Score: {rec['score']:.1f}/100 | Confidence: {rec['confidence'] * 100:.0f}%</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)

                st.markdown("#### Growth Catalysts")
                for driver in rec.get("top_drivers", []):
                    st.markdown(f'<div class="driver-pill">{driver}</div>', unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("#### Risk Factors")
                for risk in rec.get("top_risks", []):
                    st.markdown(f'<div class="risk-pill">{risk}</div>', unsafe_allow_html=True)

                st.markdown("<br><hr>", unsafe_allow_html=True)
                if "narrative" in rec:
                    st.markdown("#### Executive Summary")
                    st.markdown(
                        f"<div style='color: #2C2A29; line-height: 1.6; font-size: 0.95rem;'>{rec['narrative']}</div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.info(
                "Select a designated zone on the map to review detailed demographics, catalysts, and risk factors."
            )

with tab_leaderboard:
    st.markdown("### Top Tier Recommendations")
    for r in recs[:10]:
        with st.container():
            st.markdown(f"**{r['rank']}. {r['zone_name']}** &mdash; Score: {r['score']:.1f}")
            st.markdown(
                f"<span style='color: #8C8273; font-size: 0.9rem;'>Drivers: {', '.join(r.get('top_drivers', []))}</span>",
                unsafe_allow_html=True,
            )
            st.divider()

with tab_compare:
    st.info("Comparison module pending integration with backend evaluation layers.")

# ruff: noqa: E501
