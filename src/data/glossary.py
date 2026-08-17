"""Access to `metric_glossary.csv`, the dictionary describing every raw column.

Display names, definitions and units are read from the glossary rather than
retyped, so the interface always agrees with the data dictionary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

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


#: Names for the columns the app computes itself, written the way the glossary
#: writes its own — `Split - Metric`, title case. Nothing else in the app names a
#: column: everywhere else the name comes straight out of `metric_glossary.csv`,
#: so the interface and the data dictionary cannot say two different things.
_COMPUTED_NAMES: dict[str, str] = {
    schema.CONTESTED_TWO_RATE: "Contested - 2PT Attempt Share",
    schema.CONTESTED_THREE_RATE: "Contested - 3PT Attempt Share",
    schema.ASSISTED_SHARE: "Assisted Share",
    schema.SHOT_DISTANCE_METRES: "Average Shot Distance (m)",
    schema.MIDRANGE_RATE: "Mid-Range - Attempt Share",
    schema.FOULED_RATE: "Fouled - Attempt Share",
    schema.PRIMARY_ROLE: "Primary Pick & Roll Role",
    schema.pick_column(schema.ROLE_HANDLER_PREFIX, "picks_per_game"): (
        "Ball Handler - Picks Per Game"
    ),
    schema.pick_column(schema.ROLE_SCREENER_PREFIX, "picks_per_game"): (
        "Screener - Picks Per Game"
    ),
}

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
    schema.pick_column(schema.ROLE_HANDLER_PREFIX, "picks_per_game"): (
        "On-ball screens the player used as the ball handler, per game with a tracked event."
    ),
    schema.pick_column(schema.ROLE_SCREENER_PREFIX, "picks_per_game"): (
        "On-ball screens the player set, per game with a tracked event."
    ),
    schema.FOULED_RATE: (
        "Share of the player's field goal attempts on which he was fouled. "
        "Computed as fouled_fga / attempts."
    ),
    schema.PRIMARY_ROLE: (
        "Whether the player was more often the ball handler or the screener in pick-and-roll. "
        "The dataset carries no position, so this is the closest available stand-in."
    ),
    **{
        schema.coverage_share(role, coverage.suffix): (
            f"Share of the player's screens in this role that the defence played {label}. "
            f"Computed as {schema.picks_vs(role, coverage.suffix)} / "
            f"{schema.total_picks(role)}."
        )
        for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX)
        for coverage, label in ((c, c.label.lower()) for c in schema.coverages_for(role))
    },
}


@cache
def _index(dataset: str) -> dict[str, MetricInfo]:
    """One dataset's rows, keyed by column. Memoised: the glossary never changes.

    Rebuilt on every call, this walked all 827 rows each time a tooltip was asked
    for — three times per column, a hundred columns per table, three hundred passes
    over the file for one draw of the shortlist. Callers read it, never mutate it.
    """
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


@cache
def derived_names() -> dict[str, str]:
    """Every computed column, named the way the dictionary names its own.

    The coverage shares are not listed above: each one is the pick count it
    divides, renamed. The glossary already writes `Ball Handler - Picks (vs Soft
    (Drop))`, and retyping ten split names here is exactly the drift this module
    exists to prevent. `lookup` is used rather than `name`, which would recurse.
    """
    names = dict(_COMPUTED_NAMES)
    for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX):
        for coverage in schema.coverages_for(role):
            counted = lookup(schema.picks_vs(role, coverage.suffix), schema.DATASET_PICKS)
            if counted is not None and counted.display_name:
                names[schema.coverage_share(role, coverage.suffix)] = (
                    counted.display_name.replace(" - Picks (", " - Pick Share (")
                )
    return names


@cache
def name(column: str, dataset: str = schema.DATASET_SHOTS) -> str:
    """The column's name, as the data dictionary writes it.

    Every header, tile, spoke and selector entry in the app comes through here.
    Retyping a shorter label somewhere would let the interface drift away from the
    file it describes, and leave a reader translating between the two.

    Falls back to the raw column name, which is wrong-looking enough to be caught
    rather than mistaken for a real one — a test asserts it never happens.
    """
    computed = derived_names()
    if column in computed:
        return computed[column]

    for source in (dataset, schema.DATASET_PICKS, schema.DATASET_SHOTS):
        info = lookup(column, source)
        if info is not None and info.display_name:
            return info.display_name
    return column


#: The coverage a pick column is restricted to, as the glossary appends it:
#: `Ball Handler - Points Per Pick (vs Over)`. Anchored at the end and matched
#: greedily, so `(vs Soft (Drop))` comes off whole.
_SPLIT_SUFFIX = re.compile(r"\s*\(vs .*\)$")


def without_split(display_name: str) -> str:
    """A display name with its trailing `(vs …)` removed."""
    return _SPLIT_SUFFIX.sub("", display_name)


@cache
def family(column: str, dataset: str = schema.DATASET_SHOTS) -> str:
    """The column's name with its defensive-coverage split taken off.

    `Ball Handler - Points Per Pick (vs Over)` and its four sibling coverages are
    one metric asked six ways, and the selector offers them as one line with the
    coverage chosen beside it. This is what groups them.
    """
    return without_split(name(column, dataset))


@cache
def definition(column: str, dataset: str = schema.DATASET_SHOTS) -> str:
    """Return the definition of a column, derived columns included.

    Falls back to an empty string for anything neither the glossary nor the app
    describes, so a missing definition never becomes a misleading one.
    """
    if column in DERIVED_DEFINITIONS:
        return DERIVED_DEFINITIONS[column]

    # Column names do not collide between the two files apart from the shared
    # identifiers, so a miss in one is worth trying in the other rather than
    # leaving a header with no tooltip.
    for source in (dataset, schema.DATASET_PICKS, schema.DATASET_SHOTS):
        info = lookup(column, source)
        if info is not None and info.definition:
            return info.definition
    return ""


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
