"""Screen 3: Results."""

import streamlit as st

st.set_page_config(page_title="Results - SiteScout", layout="wide")

st.title("Analysis Results")

if "analysis_id" not in st.session_state:
    st.warning("No active analysis. Please start a new one.")
    if st.button("Go to New Analysis"):
        st.switch_page("pages/2_New_Analysis.py")
    st.stop()

analysis_id = st.session_state["analysis_id"]
st.write(f"Showing results for: **{analysis_id}**")

tab1, tab2, tab3 = st.tabs(["Map View", "Compare", "What-if"])

with tab1:
    st.info("Map with hex overlay goes here (similar to the map spike).")

with tab2:
    st.info("Compare zones side-by-side.")

with tab3:
    st.info("What-if panel to adjust tier or budget and re-score.")
