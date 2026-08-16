"""Access to `metric_glossary.csv`, the dictionary describing every raw column.

Display names, definitions and units are read from the glossary rather than
retyped, so the interface always agrees with the data dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from src.data import schema


@dataclass(frozen=True)
class MetricInfo:
    """One glossary row, reduced to what the interface needs."""

    column: str
    display_name: str
    definition: str
    unit: str
    category: str


@st.cache_data(show_spinner=False)
def load_glossary() -> pd.DataFrame:
    """Read the glossary CSV. Cached: the file is small, immutable and parsed often."""
    frame = pd.read_csv(schema.GLOSSARY_FILE)
    return frame.fillna({"unit": "", "definition": "", "display_name": "", "category": ""})


#: Columns the app computes itself. The glossary cannot describe them, so their
#: wording lives here — next to the definitions it does provide.
DERIVED_DEFINITIONS: dict[str, str] = {
    schema.CONTESTED_TWO_RATE: (
        "Share of the player's two-point attempts taken with a defender contesting. "
        "Computed as contested_two_attempts / two_attempts."
    ),
    schema.CONTESTED_THREE_RATE: (
        "Share of the player's three-point attempts taken with a defender contesting. "
        "Computed as contested_three_attempts / three_attempts."
    ),
    schema.ASSISTED_SHARE: (
        "Share of the player's made field goals that came off a teammate's pass. "
        "Computed as assisted_shots / mades."
    ),
    schema.SHOT_DISTANCE_METRES: (
        "Average distance from the basket of the player's field goal attempts, in metres. "
        "The source column is labelled metres in the glossary but is stored in feet — its "
        "maximum, 22.11, converts to 6.74 m, the FIBA three-point line — so it is converted "
        "here before display."
    ),
    schema.MIDRANGE_RATE: (
        "Share of the player's field goal attempts taken from the mid-range, inside the "
        "arc and outside the restricted area. Computed as short_midrange_paint_attempt_rate "
        "+ long_midrange_attempt_rate."
    ),
    schema.PRIMARY_ROLE: (
        "Whether the player was more often the ball handler or the screener in pick-and-roll. "
        "The dataset carries no position, so this is the closest available stand-in."
    ),
}


def _index(dataset: str) -> dict[str, MetricInfo]:
    frame = load_glossary()
    rows = frame[frame["dataset"] == dataset].drop_duplicates(subset="column")
    return {
        row.column: MetricInfo(
            column=row.column,
            display_name=row.display_name,
            definition=row.definition,
            unit=row.unit,
            category=row.category,
        )
        for row in rows.itertuples()
    }


def lookup(column: str, dataset: str = schema.DATASET_SHOTS) -> MetricInfo | None:
    """Return the glossary entry for a column, or None when the column is derived."""
    return _index(dataset).get(column)


def definition(column: str, dataset: str = schema.DATASET_SHOTS) -> str:
    """Return the definition of a column, derived columns included.

    Falls back to an empty string for anything neither the glossary nor the app
    describes, so a missing definition never becomes a misleading one.
    """
    if column in DERIVED_DEFINITIONS:
        return DERIVED_DEFINITIONS[column]
    info = lookup(column, dataset)
    return info.definition if info else ""


def unit(column: str, dataset: str = schema.DATASET_SHOTS) -> str:
    """Return the glossary unit of a column, or an empty string if absent."""
    info = lookup(column, dataset)
    return info.unit if info else ""


def help_text(*columns: str, dataset: str = schema.DATASET_SHOTS) -> str:
    """Build a tooltip listing the definition of each column that has one.

    Args:
        columns: raw column names, in the order they should appear.
        dataset: which of the two datasets the columns belong to.

    Returns:
        Markdown suitable for a Streamlit `help=` argument. Empty when no column
        is described in the glossary.
    """
    lines = [f"**`{col}`** — {definition(col, dataset)}" for col in columns if definition(col, dataset)]
    return "\n\n".join(lines)
