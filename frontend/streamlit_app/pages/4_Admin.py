"""Screen 4: Admin."""

import streamlit as st

st.set_page_config(page_title="Admin - SiteScout", layout="wide")

st.title("Admin & Data Jobs")

tab1, tab2, tab3 = st.tabs(["Data & Jobs", "Weights Editor", "System Health"])

with tab1:
    st.subheader("Cities & Ingestion")
    st.info("City table and ingestion jobs view.")

with tab2:
    st.subheader("Weights Editor")
    st.info("Editable weights with live sum check.")

with tab3:
    st.subheader("System Health")
    st.info("Agent status, latency, and error rate.")
