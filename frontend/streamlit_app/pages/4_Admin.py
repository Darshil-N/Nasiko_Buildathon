"""Screen 4: Admin."""

import streamlit as st

from frontend.streamlit_app.theme import apply_apple_theme

st.set_page_config(page_title="Administration | SiteScout", layout="wide")
apply_apple_theme()

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<h1>System Telemetry.</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='margin-bottom: 3rem;'>Diagnostics and configuration algorithms.</p>",
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["Data Ingestion", "Configuration Weights", "Telemetry"])

with tab1:
    st.markdown("<div class='apple-card'>", unsafe_allow_html=True)
    st.markdown("<h3>Regional Data Ingestion</h3>", unsafe_allow_html=True)
    st.markdown("<p>City registry and ingestion pipeline schedules.</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("<div class='apple-card'>", unsafe_allow_html=True)
    st.markdown("<h3>Scoring Weights Configuration</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p>Algorithm weight editor with real-time normalization validation.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div class='apple-card'>", unsafe_allow_html=True)
    st.markdown("<h3>System Diagnostics</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p>Autonomous agent status, API latency, and computational error rates.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
