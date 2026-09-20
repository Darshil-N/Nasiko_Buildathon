"""Screen 2: Wizard to create a new analysis."""

import streamlit as st

from frontend.streamlit_app.client import APIError, client
from frontend.streamlit_app.theme import apply_apple_theme

st.set_page_config(page_title="Configure | SiteScout", layout="wide")
apply_apple_theme()

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<h1>Define your market.</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='margin-bottom: 3rem;'>Set absolute constraints. The agents handle the rest.</p>",
    unsafe_allow_html=True,
)

try:
    cities = client.get_cities()
    categories = client.get_categories()
except Exception as e:
    st.error(f"Failed to load form data: {e}")
    st.stop()

city_options: dict[str, str] = {
    str(c["key"]): str(c["name"]) for c in cities["cities"] if c["status"] == "ready"
}
category_options: dict[str, str] = {
    str(c["key"]): str(c.get("label", c["key"])) for c in categories["categories"]
}

with st.container():
    st.markdown('<div class="apple-card">', unsafe_allow_html=True)

    with st.form("new_analysis_form", border=False):
        col1, spacer, col2 = st.columns([10, 1, 10])

        with col1:
            st.markdown("<h3>Market Parameters</h3><br>", unsafe_allow_html=True)
            city = st.selectbox(
                "Target City",
                options=list(city_options.keys()),
                format_func=lambda k: city_options[k],
            )

            category = st.selectbox(
                "Category",
                options=list(category_options.keys()),
                format_func=lambda k: category_options[k],
            )

            selected_cat_obj = next(
                (c for c in categories["categories"] if c["key"] == category),
                categories["categories"][0],
            )
            tier_options: dict[str, str] = {t["id"]: t["label"] for t in selected_cat_obj["tiers"]}

            tier = st.selectbox(
                "Target Tier",
                options=list(tier_options.keys()),
                format_func=lambda k: tier_options[k],
            )

        with col2:
            st.markdown("<h3>Financial Boundaries</h3><br>", unsafe_allow_html=True)

            budget = st.number_input(
                "Maximum Monthly Rent (INR)", min_value=0, value=150000, step=10000, format="%d"
            )

            size = st.number_input(
                "Expected Floor Space (Sq. Ft.)", min_value=0, value=800, step=100
            )

            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "Start Evaluation", type="primary", use_container_width=True
            )

    st.markdown("</div>", unsafe_allow_html=True)

if submitted:
    payload = {
        "city": city,
        "category": category,
        "tier": tier,
        "constraints": {"monthly_rent_budget_inr": budget, "shop_size_sqft": size},
        "top_n": 50,
    }

    st.markdown("---")
    status_container = st.empty()

    with status_container.container():
        st.info("Submitting instructions to the network...")

    try:
        response = client.create_analysis(payload)
        st.session_state["analysis_id"] = response["analysis_id"]

        status_container.empty()
        st.success("Task assigned. Redirecting to intelligence output...")
        st.switch_page("pages/3_Results.py")
    except APIError as e:
        status_container.empty()
        if e.code == "CITY_NOT_READY":
            st.error(
                "The selected city is not yet ready for analysis. Please select a supported region."
            )
        else:
            st.error(f"System Error: {e.message}")
