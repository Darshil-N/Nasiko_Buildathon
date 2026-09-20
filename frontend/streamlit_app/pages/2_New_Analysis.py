"""Screen 2: Wizard to create a new analysis."""

import streamlit as st

from frontend.streamlit_app.client import APIError, client

st.set_page_config(page_title="New Analysis - SiteScout", layout="wide")

st.title("New Analysis")

try:
    cities = client.get_cities()
    categories = client.get_categories()
except Exception as e:
    st.error(f"Failed to load form data: {e}")
    st.stop()

city_options: dict[str, str] = {
    str(c["key"]): str(c["name"]) for c in cities["cities"] if c["status"] == "ready"
}
category_options: dict[str, str] = {str(c["key"]): str(c["name"]) for c in categories["categories"]}

with st.form("new_analysis_form"):
    st.subheader("Step 1: Location & Category")
    city = st.selectbox(
        "City", options=list(city_options.keys()), format_func=lambda k: city_options[k]
    )
    category = st.selectbox(
        "Category",
        options=list(category_options.keys()),
        format_func=lambda k: category_options[k],
    )

    st.subheader("Step 2: Tier")
    tier_options: dict[str, str] = categories["categories"][0]["tiers"]  # type: ignore[assignment]
    tier = st.selectbox(
        "Tier", options=list(tier_options.keys()), format_func=lambda k: tier_options[k]
    )

    st.subheader("Step 3: Constraints")
    budget = st.number_input("Monthly Rent Budget (INR)", min_value=0, value=120000)
    size = st.number_input("Shop Size (sq ft)", min_value=0, value=800)

    submitted = st.form_submit_button("Run Analysis", type="primary")

if submitted:
    payload = {
        "city": city,
        "category": category,
        "tier": tier,
        "constraints": {"monthly_rent_budget_inr": budget, "shop_size_sqft": size},
    }

    with st.spinner("Starting analysis..."):
        try:
            response = client.create_analysis(payload)
            st.session_state["analysis_id"] = response["analysis_id"]
            st.success("Analysis started!")
            st.switch_page("pages/3_Results.py")
        except APIError as e:
            st.error(f"Error: {e.message}")
