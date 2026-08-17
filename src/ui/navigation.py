"""Where the pages are, and how one of them sends the reader to another.

The loaded player lives in `src.ui.selection`, which is session state and not
page state, so switching pages carries him across untouched: the board he lands
on opens on his card. Nothing has to be handed over.
"""

from __future__ import annotations

import streamlit as st

SHORTLIST: str = "pages/3_shortlist.py"
SHOT_QUALITY: str = "pages/1_shot_quality.py"
PICK_AND_ROLL: str = "pages/2_pick_and_roll.py"
ADMIN: str = "pages/4_admin.py"


def board_button(
    label: str, page: str, *, icon: str, help_text: str, key: str, disabled: bool = False
) -> None:
    """A button that leaves this page for a board, keeping the player loaded."""
    if st.button(
        label, icon=icon, key=key, width="stretch", help=help_text, disabled=disabled
    ):
        st.switch_page(page)
