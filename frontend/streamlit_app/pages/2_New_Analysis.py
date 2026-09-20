"""Screen 2: Wizard to create a new analysis."""

import streamlit as st

from frontend.streamlit_app.client import APIError, client

st.set_page_config(page_title="New Analysis - SiteScout", layout="wide")

st.markdown(
    """
<style>
    .wizard-card {
        background-color: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
        margin-bottom: 2rem;
    }
    .wizard-title {
        color: #1a365d;
        font-weight: 700;
        margin-bottom: 1.5rem;
    }
    .stNumberInput, .stSelectbox {
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🎯 Configure New Analysis")
st.markdown("Set up your constraints and let our AI agents find the optimal locations.")

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
    st.markdown('<div class="wizard-card">', unsafe_allow_html=True)

    with st.form("new_analysis_form", border=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('<h3 class="wizard-title">1. Market & Brand</h3>', unsafe_allow_html=True)
            city = st.selectbox(
                "Target City",
                options=list(city_options.keys()),
                format_func=lambda k: city_options[k],
                help="Only cities with fully processed data are available.",
            )

            category = st.selectbox(
                "Business Category",
                options=list(category_options.keys()),
                format_func=lambda k: category_options[k],
                help="The model uses category-specific logic (e.g. Cafe seeks offices, Pharmacy seeks residential).",
            )

            selected_cat_obj = next(
                (c for c in categories["categories"] if c["key"] == category),
                categories["categories"][0],
            )
            tier_options: dict[str, str] = {t["id"]: t["label"] for t in selected_cat_obj["tiers"]}

            tier = st.selectbox(
                "Target Tier / Price Segment",
                options=list(tier_options.keys()),
                format_func=lambda k: tier_options[k],
                help="Guides the algorithm to match local affluence and competitor segments.",
            )

        with col2:
            st.markdown(
                '<h3 class="wizard-title">2. Financial Constraints</h3>', unsafe_allow_html=True
            )

            budget = st.number_input(
                "Max Monthly Rent Budget (INR)",
                min_value=0,
                value=150000,
                step=10000,
                format="%d",
                help="Zones with average rents exceeding this budget by 20% will be filtered out.",
            )

            size = st.number_input(
                "Expected Shop Size (Sq. Ft.)",
                min_value=0,
                value=800,
                step=100,
                help="Used alongside the budget to calculate the allowed rent per square foot.",
            )

            st.markdown("<br><br>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "🚀 Launch AI Analysis", type="primary", use_container_width=True
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
        st.info("🧠 Submitting parameters to the Agent Control Plane...")

    try:
        response = client.create_analysis(payload)
        st.session_state["analysis_id"] = response["analysis_id"]

        status_container.empty()
        st.success("✅ Analysis queued successfully! Redirecting to live dashboard...")
        st.switch_page("pages/3_Results.py")
    except APIError as e:
        status_container.empty()
        if e.code == "CITY_NOT_READY":
            st.error("⚠️ The selected city is not yet ready for analysis. Try another city.")
        else:
            st.error(f"❌ Error: {e.message}")

# ruff: noqa: E501
