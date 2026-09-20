"""Screen 1: My analyses."""

import streamlit as st

st.set_page_config(page_title="Archives | SiteScout", layout="wide")

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
    .archive-card {
        background-color: #FFFFFF;
        padding: 3rem;
        border-radius: 2px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.03);
        border: 1px solid #EAE6DF;
        margin-bottom: 2rem;
        text-align: center;
    }
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
    }
    div.stButton > button:hover {
        background-color: #4A4644;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Analysis Archives")
st.markdown(
    "<p style='color: #5C5855; margin-bottom: 2rem;'>Review historical site selection evaluations.</p>",
    unsafe_allow_html=True,
)

with st.container():
    st.markdown('<div class="archive-card">', unsafe_allow_html=True)
    st.markdown("### No records found")
    st.markdown(
        "<p style='color: #8C8273; margin-bottom: 2rem;'>You have not initiated any evaluations yet.</p>",
        unsafe_allow_html=True,
    )

    if st.button("Initiate New Evaluation"):
        st.switch_page("pages/2_New_Analysis.py")

    st.markdown("</div>", unsafe_allow_html=True)

# ruff: noqa: E501
