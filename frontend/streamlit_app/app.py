"""SiteScout Streamlit App Entry Point."""

import streamlit as st

st.set_page_config(
    page_title="SiteScout",
    page_icon="🗺️",
    layout="wide",
)

st.title("SiteScout")
st.markdown("Welcome to the AI-powered site selection tool.")
st.markdown("Please select a page from the sidebar to begin.")

# If navigating without specific page selected, show overview.
if st.button("Start New Analysis"):
    st.switch_page("pages/2_New_Analysis.py")
