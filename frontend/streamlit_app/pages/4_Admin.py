"""Screen 4: Admin."""

import streamlit as st

st.set_page_config(page_title="Administration | SiteScout", layout="wide")

st.markdown(
    """
<style>
    .stApp {
        background-color: #FAF8F5;
        color: #2C2A29;
    }
    h1, h2, h3 {
        font-family: 'Georgia', serif;
        color: #1A1A1A;
        font-weight: normal;
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

st.title("Administration & Diagnostics")
st.markdown(
    "<p style='color: #5C5855;'>System health, configuration, and data ingestion management.</p><br>",
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["Data Ingestion", "Configuration Weights", "System Telemetry"])

with tab1:
    st.markdown("### Regional Data Ingestion")
    st.info("City registry and ingestion pipeline schedules.")

with tab2:
    st.markdown("### Scoring Weights Configuration")
    st.info("Algorithm weight editor with real-time normalization validation.")

with tab3:
    st.markdown("### System Telemetry")
    st.info("Autonomous agent status, API latency, and computational error rates.")

# ruff: noqa: E501
