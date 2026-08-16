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

#: Suffix given to the picks copy of a column both files carry. Deliberately not
#: `_picks`, which is how real columns such as `handler_total_picks` end.
DUPLICATE: str = "__from_picks"


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


@st.cache_data(show_spinner=False)
def load_pick_profiles() -> pd.DataFrame:
    """Return one row per player of the pick-and-roll file, extras derived.

    The picks file stands on its own here: the lens already says which role is
    being looked at, so nothing from the shooting file is needed to read it.
    """
    return aggregate.derive_pick_features(
        load_picks().drop(columns=list(schema.REDUNDANT_IDENTIFIERS), errors="ignore")
    )


@st.cache_data(show_spinner=False)
def load_all_profiles() -> pd.DataFrame:
    """Both files on one row per player, joined on `player_id`.

    The join is outer and its provenance kept: 288 players appear in both files,
    4 only in the picks file and 7 only in the shooting one. Dropping either side
    silently would quietly narrow the search the shortlist runs.
    """
    shots, picks = load_shots(), load_picks()

    # The two files are joined first and the derived columns computed after: some
    # of them read across the join, such as the role a player mostly plays.
    merged = shots.merge(
        picks, on=schema.PLAYER_ID, how="outer", suffixes=("", DUPLICATE), indicator=True
    )

    # A player present only in the picks file would otherwise carry no name: the
    # identifiers exist on both sides, so the picks copy fills the gap. Note that
    # `games_played` counts games with a tracked event *in that file*, so the
    # shooting count is kept when both exist rather than mixing the two.
    for column in schema.SHARED_IDENTIFIERS:
        twin = column + DUPLICATE
        if twin in merged.columns:
            merged[column] = merged[column].fillna(merged[twin]).infer_objects(copy=False)
    merged = merged.drop(columns=[c for c in merged.columns if c.endswith(DUPLICATE)])
    merged[SOURCE] = merged["_merge"].map(
        {"both": SOURCE_BOTH, "left_only": SOURCE_SHOTS_ONLY, "right_only": SOURCE_PICKS_ONLY}
    )
    merged = merged.drop(columns=["_merge", *schema.REDUNDANT_IDENTIFIERS], errors="ignore")

    return aggregate.derive_pick_features(aggregate.derive_shot_features(merged))


def teams(frame: pd.DataFrame) -> list[str]:
    """Return the sorted list of teams present in a frame."""
    return sorted(frame[schema.TEAM_NAME].dropna().unique().tolist())


def player_names(frame: pd.DataFrame) -> list[str]:
    """Return the sorted list of player names present in a frame."""
    return sorted(frame[schema.PLAYER_NAME].dropna().unique().tolist())
