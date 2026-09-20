"""Screen 1: My analyses."""

import streamlit as st

st.set_page_config(page_title="My Analyses - SiteScout", layout="wide")

st.title("My Analyses")

# TODO: Fetch from backend once endpoint exists or use local storage stub
st.info("No past analyses found. Start a new one!")

if st.button("New Analysis", type="primary"):
    st.switch_page("pages/2_New_Analysis.py")
