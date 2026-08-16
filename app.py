"""Entry point: page configuration and navigation. No data work happens here."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="ACB Offense Explorer",
    page_icon=":material/sports_basketball:",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = [
    st.Page(
        "pages/1_shot_quality.py",
        title="Shot quality",
        icon=":material/my_location:",
        default=True,
    ),
]

st.navigation(PAGES).run()
