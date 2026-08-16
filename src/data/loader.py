"""Reading the season CSVs and joining them on `player_id`.

The two files carry different rosters (292 pick rows, 295 shot rows), so the
join is explicit and its provenance is kept in a column rather than assumed.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import aggregate
from src.data import schema

#: Marks which of the two files a player was found in after the outer join.
SOURCE: str = "source"
SOURCE_BOTH: str = "both"
SOURCE_SHOTS_ONLY: str = "shots only"
SOURCE_PICKS_ONLY: str = "picks only"


@st.cache_data(show_spinner=False)
def load_shots() -> pd.DataFrame:
    """Read the shooting dataset. Cached: reading and typing 228 columns is costly."""
    return pd.read_csv(schema.SHOTS_FILE)


@st.cache_data(show_spinner=False)
def load_picks() -> pd.DataFrame:
    """Read the pick-and-roll dataset. Cached: 599 columns, immutable on disk."""
    return pd.read_csv(schema.PICKS_FILE)


@st.cache_data(show_spinner=False)
def load_shot_profiles() -> pd.DataFrame:
    """Return one row per shooter, with pick volumes attached and extras derived.

    The shooting file drives the row set; the two pick-volume columns come along
    only so a player can be labelled ball handler or screener, the closest thing
    to a position this data offers.

    Returns:
        A shooting frame with `role` volumes, derived rates and a `source` column.
    """
    shots = load_shots()
    picks = load_picks()

    role_volumes = picks[[schema.PLAYER_ID, schema.HANDLER_PICKS, schema.SCREENER_PICKS]]
    merged = shots.merge(role_volumes, on=schema.PLAYER_ID, how="left", indicator=True)
    merged[SOURCE] = merged["_merge"].map({"both": SOURCE_BOTH, "left_only": SOURCE_SHOTS_ONLY})
    merged = merged.drop(columns=["_merge", *schema.REDUNDANT_IDENTIFIERS], errors="ignore")

    return aggregate.derive_shot_features(merged)


def teams(frame: pd.DataFrame) -> list[str]:
    """Return the sorted list of teams present in a frame."""
    return sorted(frame[schema.TEAM_NAME].dropna().unique().tolist())


def player_names(frame: pd.DataFrame) -> list[str]:
    """Return the sorted list of player names present in a frame."""
    return sorted(frame[schema.PLAYER_NAME].dropna().unique().tolist())
