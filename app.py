"""Entry point: page configuration and navigation. No data work happens here."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

#: Drawn in blue and grey only, so it reads on both the light and the dark sidebar.
LOGO = Path(__file__).parent / "assets" / "triple_threat.svg"

st.set_page_config(
    page_title="Triple Threat",
    page_icon=":material/sports_basketball:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.logo(str(LOGO), size="large")

# The shortlist opens the app: a scout arrives with a search, not with a board.
PAGES = [
    st.Page(
        "pages/3_shortlist.py",
        title="Shortlist",
        icon=":material/checklist:",
        default=True,
    ),
    st.Page(
        "pages/1_shot_quality.py",
        title="Shot quality",
        icon=":material/my_location:",
    ),
    st.Page(
        "pages/2_pick_and_roll.py",
        title="Pick & roll",
        icon=":material/group_work:",
    ),
]

st.navigation(PAGES).run()
