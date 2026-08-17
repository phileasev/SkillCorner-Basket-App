"""Pick & Roll Board — what a player generates out of an on-ball screen.

Two lenses, one per role: only four players out of 292 record fifty picks in both,
so ball handler and screener are read as two populations rather than one.

⚠️ Points per pick counts what a teammate scored off the player's pass as well as
his own basket. It measures the offence generated per screen, not his shooting.
"""

from __future__ import annotations

import streamlit as st

from src.core.pick_views import PICK_LENSES
from src.data import loader, schema
from src.ui import board

st.title("Pick & Roll Board")

board.render(
    frames={schema.DATASET_PICKS: loader.load_pick_profiles()},
    lenses=PICK_LENSES,
    caption=(
        "A screen either creates an advantage or it does not. This board separates "
        "how often a player creates one from what he does with it."
    ),
    page="Pick & roll",
)
