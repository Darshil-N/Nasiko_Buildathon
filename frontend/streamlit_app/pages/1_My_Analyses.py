"""Screen 1: My analyses."""

import streamlit as st

from frontend.streamlit_app.theme import apply_apple_theme

st.set_page_config(page_title="Archives | SiteScout", layout="wide")
apply_apple_theme()

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<h1>Archives.</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='margin-bottom: 3rem;'>Historical intelligence reports.</p>", unsafe_allow_html=True
)

with st.container():
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)
    st.markdown("<h3>No records found.</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='margin-bottom: 2rem;'>You have not initiated any evaluations.</p>",
        unsafe_allow_html=True,
    )

    if st.button("Start Evaluation"):
        st.switch_page("pages/2_New_Analysis.py")

    st.markdown("</div>", unsafe_allow_html=True)
