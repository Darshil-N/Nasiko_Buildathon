"""Screen 2: Wizard to create a new analysis."""

import streamlit as st

from frontend.streamlit_app.client import APIError, client

st.set_page_config(page_title="Configure Analysis | SiteScout", layout="wide")

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
    .wizard-card {
        background-color: #FFFFFF;
        padding: 3rem;
        border-radius: 2px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.03);
        border: 1px solid #EAE6DF;
        margin-bottom: 2rem;
    }
    .wizard-title {
        color: #1A1A1A;
        font-family: 'Georgia', serif;
        font-size: 1.5rem;
        margin-bottom: 2rem;
        border-bottom: 1px solid #EAE6DF;
        padding-bottom: 0.5rem;
    }
    .header-section {
        margin-bottom: 3rem;
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
        margin-top: 1rem;
    }
    div.stButton > button:hover {
        background-color: #4A4644;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="header-section"><h1>Configure Analysis</h1><p style="color: #5C5855;">Define your market parameters and financial constraints to initiate the evaluation process.</p></div>',
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
    st.markdown('<div class="wizard-card">', unsafe_allow_html=True)

    with st.form("new_analysis_form", border=False):
        col1, spacer, col2 = st.columns([10, 1, 10])

        with col1:
            st.markdown(
                '<div class="wizard-title">Market & Brand Definition</div>', unsafe_allow_html=True
            )
            city = st.selectbox(
                "Target City",
                options=list(city_options.keys()),
                format_func=lambda k: city_options[k],
            )

            category = st.selectbox(
                "Business Category",
                options=list(category_options.keys()),
                format_func=lambda k: category_options[k],
            )

            selected_cat_obj = next(
                (c for c in categories["categories"] if c["key"] == category),
                categories["categories"][0],
            )
            tier_options: dict[str, str] = {t["id"]: t["label"] for t in selected_cat_obj["tiers"]}

            tier = st.selectbox(
                "Target Market Tier",
                options=list(tier_options.keys()),
                format_func=lambda k: tier_options[k],
            )

        with col2:
            st.markdown(
                '<div class="wizard-title">Financial Constraints</div>', unsafe_allow_html=True
            )

            budget = st.number_input(
                "Maximum Monthly Rent (INR)", min_value=0, value=150000, step=10000, format="%d"
            )

            size = st.number_input(
                "Required Floor Space (Sq. Ft.)", min_value=0, value=800, step=100
            )

            st.markdown("<br><br>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "Initiate Evaluation", type="primary", use_container_width=True
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
        st.info("Submitting parameters to the Agent Control Plane...")

    try:
        response = client.create_analysis(payload)
        st.session_state["analysis_id"] = response["analysis_id"]

        status_container.empty()
        st.success("Analysis queued successfully. Redirecting to intelligence dashboard...")
        st.switch_page("pages/3_Results.py")
    except APIError as e:
        status_container.empty()
        if e.code == "CITY_NOT_READY":
            st.error(
                "The selected city is not yet ready for analysis. Please select a supported region."
            )
        else:
            st.error(f"System Error: {e.message}")

# ruff: noqa: E501
