"""Shot Quality Board — what shots a player takes, and how well he takes them.

Interface only: this file names the page and hands the board its lenses. Every
filter, ratio and ordering lives in `src.core`, every widget in `src.ui`.
"""

from __future__ import annotations

import streamlit as st

from src.core.shot_views import SHOT_LENSES
from src.data import loader, schema
from src.ui import board

st.title("Shot Quality Board")

board.render(
    frames={schema.DATASET_SHOTS: loader.load_shot_profiles()},
    lenses=SHOT_LENSES,
    caption=(
        "Every shooter takes a different menu of shots. This board separates what he "
        "takes from how well he takes it."
    ),
)
