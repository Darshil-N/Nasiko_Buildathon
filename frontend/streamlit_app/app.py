"""SiteScout Streamlit App Entry Point."""

import streamlit as st

st.set_page_config(
    page_title="SiteScout | Intelligence", layout="wide", initial_sidebar_state="collapsed"
)

st.markdown(
    """
<style>
    /* Global Cream Theme */
    .stApp {
        background-color: #FAF8F5;
        color: #2C2A29;
    }

    /* Typography */
    h1, h2, h3 {
        font-family: 'Georgia', serif;
        color: #1A1A1A;
        font-weight: normal;
    }
    p, span, div {
        font-family: 'Inter', 'Helvetica Neue', sans-serif;
    }

    /* Hero Section */
    .hero-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 6rem 2rem;
        text-align: center;
        border-bottom: 1px solid #EAE6DF;
        margin-bottom: 3rem;
    }
    .hero-title {
        font-size: 3.5rem;
        letter-spacing: -0.02em;
        margin-bottom: 1rem;
    }
    .hero-subtitle {
        font-size: 1.25rem;
        color: #5C5855;
        max-width: 600px;
        line-height: 1.6;
        margin-bottom: 3rem;
    }

    /* Custom Buttons */
    div.stButton > button {
        background-color: #2C2A29;
        color: #FFFFFF;
        border: none;
        border-radius: 4px;
        padding: 0.75rem 2.5rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        font-size: 0.85rem;
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        background-color: #4A4644;
        color: #FFFFFF;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Secondary Button */
    div:nth-of-type(2) > div.stButton > button {
        background-color: transparent;
        color: #2C2A29;
        border: 1px solid #2C2A29;
    }
    div:nth-of-type(2) > div.stButton > button:hover {
        background-color: #F0EBE1;
        color: #2C2A29;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero-container">
    <h1 class="hero-title">SiteScout</h1>
    <p class="hero-subtitle">
        Institutional-grade site selection. We deploy autonomous agents across geospatial networks,
        footfall metrics, and real estate data to identify the optimal location for your next expansion.
    </p>
</div>
""",
    unsafe_allow_html=True,
)

col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 2, 1])

with col3:
    if st.button("Configure Analysis", use_container_width=True):
        st.switch_page("pages/2_New_Analysis.py")

with col4:
    if st.button("View Archives", use_container_width=True):
        st.switch_page("pages/1_My_Analyses.py")

st.markdown("<br><br><br>", unsafe_allow_html=True)

# Three pillars section
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### Deterministic Scoring")
    st.markdown(
        "<p style='color: #5C5855;'>Evaluate thousands of geographic zones based on footfall anchors, affluence matching, and competitor pressure.</p>",
        unsafe_allow_html=True,
    )
with c2:
    st.markdown("### Financial Validation")
    st.markdown(
        "<p style='color: #5C5855;'>Integrate real-time rental listings to ensure your unit economics remain viable in premium markets.</p>",
        unsafe_allow_html=True,
    )
with c3:
    st.markdown("### Autonomous Insights")
    st.markdown(
        "<p style='color: #5C5855;'>Leverage AI agents to generate detailed narratives, highlighting growth drivers and hidden market risks.</p>",
        unsafe_allow_html=True,
    )

# ruff: noqa: E501
