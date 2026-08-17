"""Entry point: page configuration and navigation. No data work happens here."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.ui import navigation

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
# The paths come from `src.ui.navigation`, which is also where a player card
# reads them to send the reader from his profile to the matching board.
PAGES = [
    st.Page(
        navigation.SHORTLIST,
        title="Shortlist",
        icon=":material/checklist:",
        default=True,
    ),
    st.Page(
        navigation.SHOT_QUALITY,
        title="Shot quality",
        icon=":material/my_location:",
    ),
    st.Page(
        navigation.PICK_AND_ROLL,
        title="Pick & roll",
        icon=":material/group_work:",
    ),
]

st.navigation(PAGES).run()
