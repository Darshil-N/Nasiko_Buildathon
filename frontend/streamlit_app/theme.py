import streamlit as st


def apply_apple_theme():
    """Injects Apple-like minimalist CSS to override Streamlit defaults."""
    st.markdown(
        """
        <style>
            /* Base Reset & Fonts */
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

            html, body, [class*="css"] {
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", sans-serif;
                background-color: #ffffff;
                color: #1d1d1f;
            }

            /* Hide Streamlit Header & Footer */
            [data-testid="stHeader"] { visibility: hidden; height: 0; }
            footer { visibility: hidden; }

            /* Typography */
            h1 {
                font-size: 4rem !important;
                font-weight: 700 !important;
                letter-spacing: -0.04em !important;
                color: #1d1d1f !important;
                line-height: 1.1 !important;
                margin-bottom: 0.5rem !important;
            }
            h2 {
                font-size: 2.5rem !important;
                font-weight: 600 !important;
                letter-spacing: -0.03em !important;
                color: #1d1d1f !important;
            }
            h3 {
                font-size: 1.5rem !important;
                font-weight: 600 !important;
                letter-spacing: -0.02em !important;
                color: #1d1d1f !important;
            }
            p {
                font-size: 1.1rem;
                font-weight: 400;
                letter-spacing: -0.01em;
                color: #86868b;
                line-height: 1.5;
            }

            /* Buttons */
            .stButton > button {
                background-color: #000000 !important;
                color: #ffffff !important;
                border-radius: 980px !important;
                padding: 0.75rem 2rem !important;
                font-weight: 600 !important;
                font-size: 1rem !important;
                border: none !important;
                transition: transform 0.2s ease, opacity 0.2s ease !important;
                box-shadow: none !important;
            }
            .stButton > button:hover {
                transform: scale(1.02);
                opacity: 0.8;
                color: #ffffff !important;
            }
            .stButton > button:active {
                transform: scale(0.98);
            }

            /* Secondary Button */
            div:nth-of-type(2) > div.stButton > button {
                background-color: rgba(0,0,0,0.05) !important;
                color: #1d1d1f !important;
            }
            div:nth-of-type(2) > div.stButton > button:hover {
                background-color: rgba(0,0,0,0.1) !important;
                color: #1d1d1f !important;
            }

            /* Inputs & Selectboxes */
            .stSelectbox > div > div, .stNumberInput > div > div > input {
                background-color: #f5f5f7 !important;
                border: none !important;
                border-radius: 12px !important;
                font-size: 1.1rem !important;
                padding: 0.5rem 1rem !important;
                color: #1d1d1f !important;
                box-shadow: none !important;
            }
            .stSelectbox label, .stNumberInput label {
                font-weight: 600 !important;
                font-size: 0.9rem !important;
                color: #1d1d1f !important;
                letter-spacing: -0.01em !important;
            }

            /* Sidebar */
            [data-testid="stSidebar"] {
                background-color: #f5f5f7;
                border-right: none;
            }
            [data-testid="stSidebar"] p {
                color: #1d1d1f;
                font-weight: 500;
            }

            /* Cards / Containers */
            .apple-card {
                background-color: #f5f5f7;
                border-radius: 24px;
                padding: 2.5rem;
                margin-bottom: 2rem;
                border: none;
            }

            /* Dashboard Metrics */
            .metric-val {
                font-size: 3rem;
                font-weight: 700;
                letter-spacing: -0.04em;
                color: #1d1d1f;
                line-height: 1;
            }
            .metric-lbl {
                font-size: 0.85rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: #86868b;
                margin-top: 0.5rem;
            }

            /* Pills */
            .pill-pos {
                display: inline-block;
                background-color: #1d1d1f;
                color: #ffffff;
                padding: 4px 12px;
                border-radius: 980px;
                font-size: 0.85rem;
                font-weight: 500;
                margin: 4px 4px 4px 0;
            }
            .pill-neg {
                display: inline-block;
                background-color: #ff3b30;
                color: #ffffff;
                padding: 4px 12px;
                border-radius: 980px;
                font-size: 0.85rem;
                font-weight: 500;
                margin: 4px 4px 4px 0;
            }

            /* Tabs */
            .stTabs [data-baseweb="tab-list"] {
                gap: 1rem;
                background-color: #f5f5f7;
                padding: 0.5rem;
                border-radius: 980px;
            }
            .stTabs [data-baseweb="tab"] {
                height: 2.5rem;
                padding: 0 1.5rem;
                border-radius: 980px;
                color: #86868b;
                font-weight: 600;
                font-size: 0.95rem;
                border: none;
                background: transparent;
            }
            .stTabs [aria-selected="true"] {
                background-color: #ffffff !important;
                color: #1d1d1f !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
                border: none !important;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )


# ruff: noqa: W293, E501
