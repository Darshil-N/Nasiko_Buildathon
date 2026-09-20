"""SiteScout Streamlit App Entry Point."""

import streamlit as st

st.set_page_config(
    page_title="SiteScout | Smart Site Selection",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for global styling
st.markdown(
    """
<style>
    /* Main background and font styling */
    .main {
        background-color: #F8F9FA;
        font-family: 'Inter', sans-serif;
    }
    /* Hero section styling */
    .hero {
        padding: 3rem 0;
        text-align: center;
        background: linear-gradient(135deg, #0b1a2e 0%, #1a365d 100%);
        color: white;
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .hero h1 {
        font-weight: 800;
        font-size: 3rem;
        margin-bottom: 0.5rem;
        color: #ffffff;
    }
    .hero p {
        font-size: 1.2rem;
        opacity: 0.9;
        margin-bottom: 2rem;
    }
    /* Button styling override */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 2rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
    <h1>SiteScout</h1>
    <p>AI-Powered Geospatial Site Selection for Retail Brands</p>
</div>
""",
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown("""
    ### 🎯 Stop guessing. Start knowing.
    SiteScout uses an autonomous AI team to evaluate thousands of geographic zones (H3 grid) across the city based on:
    * **Footfall Anchors:** Proximity to offices, malls, and colleges.
    * **Affluence Matching:** Matching local spending power to your brand tier.
    * **Competitor Pressure:** Market clustering vs. saturation.
    * **Real-time Rent:** Ensuring the unit economics actually work.
    """)
    st.write("")

    if st.button("🚀 Start a New Analysis", type="primary", use_container_width=True):
        st.switch_page("pages/2_New_Analysis.py")

    st.write("")
    if st.button("📊 View Past Analyses", use_container_width=True):
        st.switch_page("pages/1_My_Analyses.py")

# ruff: noqa: E501
