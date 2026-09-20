"""SiteScout Streamlit App Entry Point."""
# ruff: noqa: E501

import streamlit as st

from frontend.streamlit_app.theme import apply_apple_theme

st.set_page_config(page_title="SiteScout", layout="wide", initial_sidebar_state="collapsed")
apply_apple_theme()

st.markdown("<br><br><br><br>", unsafe_allow_html=True)
st.markdown(
    "<h1 style='text-align: center;'>Intelligence.<br>Amplified.</h1>", unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align: center; font-size: 1.5rem; max-width: 600px; margin: 0 auto 3rem auto;'>Deploy autonomous agents to process geospatial footprints, live real estate data, and market saturation to uncover the ultimate location for your expansion.</p>",
    unsafe_allow_html=True,
)

col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 2, 1])

with col3:
    if st.button("Start Analysis", use_container_width=True):
        st.switch_page("pages/2_New_Analysis.py")

with col4:
    if st.button("View Archives", use_container_width=True):
        st.switch_page("pages/1_My_Analyses.py")

st.markdown("<br><br><br><br>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        "<h3>Pro metrics.</h3><p>Deterministic scoring against massive arrays of footfall constraints and competition layers.</p>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        "<h3>Real financials.</h3><p>Live integrations with rental markets ensure your operational unit economics remain strictly viable.</p>",
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        "<h3>Autonomous logic.</h3><p>Agents process the raw metrics into actionable narratives, defining clear catalysts and risk profiles.</p>",
        unsafe_allow_html=True,
    )
