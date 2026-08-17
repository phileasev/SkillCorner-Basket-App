"""The shortlist builder: stackable criteria, and the table they produce.

A bar can be set two ways — as a value, or as a place in the league — because a
scout thinks in both. They are the same number seen from two sides, so whichever
he sets, the line under the row states the other.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import metrics, shortlist
from src.core.shortlist import Criterion, Filterable
from src.ui import format as fmt

#: How many criteria the reader can stack. Past this the list stops being a list.
MAX_CRITERIA: int = 5

_STORE: str = "criteria_count"

#: The criteria the rows last produced. The rows redraw on their own, so the page
#: reads them from here rather than from the fragment's return value, which a
#: fragment-only rerun never delivers.
_BUILT: str = "criteria_built"

#: Ways of setting a bar, in the order the selector offers them.
_MODES: tuple[str, ...] = ("Percentile", "Value")


#: Rows the page opens with. The perimeter every page starts from — a rotation
#: player who actually shoots — is the scope bar above, not a criterion here, so
#: this row opens empty and the reader writes the first bar himself.
_OPENING_ROWS: int = 1


def _stack(step: int) -> None:
    """Add or drop a row, on the click itself rather than on the run after it.

    Setting the count from a callback means the script body reads the final number
    on its single pass. Doing it inline and calling `st.rerun()` would cut the page
    off at the button row, tearing down the table below for a frame before the
    second pass paints it back — the flicker the reader sees as a jump.
    """
    count = int(st.session_state.get(_STORE, _OPENING_ROWS))
    st.session_state[_STORE] = min(max(count + step, 1), MAX_CRITERIA)


def _is_share(option: Filterable) -> bool:
    """Whether the metric is a 0-1 ratio the reader thinks of in percent."""
    return option.fmt in (metrics.PCT0, metrics.PCT1)


def _mode_index(option: Filterable) -> int:
    """How the bar opens: a rate as a place in the league, a total as a number.

    "The top 20%" is the question a scout arrives with, but nobody asks for a
    player in the top 20% of games played — a count is asked for as a count.
    """
    return _MODES.index("Value" if option.fmt == metrics.INT else "Percentile")


def _split_picker(option: Filterable, index: int, column) -> str:
    """Which split of a metric the criterion is about, when it has more than one.

    A pick metric exists once per coverage and a contested one once per shot type.
    Choosing the split next to the metric keeps one line per idea in the selector
    instead of one per combination.
    """
    with column:
        if len(option.variants) <= 1:
            st.caption(" ")
            return option.variants[0][1] if option.variants else option.key

        names = [split for split, _ in option.variants]
        chosen = st.selectbox(
            (option.split_label or "Split") if index == 0 else " ",
            names,
            key=f"criterion_split_{index}_{option.label}_{option.group}",
        )
    return dict(option.variants)[chosen]


def _value_input(
    frame: pd.DataFrame,
    option: Filterable,
    index: int,
    by_percentile: bool,
) -> float | None:
    """The bar itself, set either as a value or as a place in the league.

    Percentages are entered as percentages: a reader asked for eFG% types 55, not
    0.55, and certainly not the 0.00 a raw ratio input would open on. The value
    box opens on the median of the pool rather than at zero, so the control starts
    somewhere meaningful.
    """
    if by_percentile:
        place = st.slider(
            "Percentile" if index == 0 else " ",
            min_value=0, max_value=100, value=50, step=1,
            key=f"criterion_pct_{index}_{option.key}",
            help="Where the bar sits among the players the scope bar above leaves standing.",
        )
        return shortlist.value_at_percentile(frame, option.key, place / 100)

    median = shortlist.value_at_percentile(frame, option.key, 0.5)
    if median is None:
        return None

    values = frame.loc[shortlist.pool(frame, option.key), option.key].dropna()
    high = float(values.max())

    if option.fmt == metrics.INT:
        return float(
            st.number_input(
                "Value" if index == 0 else " ",
                min_value=0, max_value=int(high), value=int(median), step=1,
                key=f"criterion_value_{index}_{option.key}",
            )
        )

    if _is_share(option):
        entered = st.number_input(
            "Value (%)" if index == 0 else " ",
            min_value=0.0, max_value=round(high * 100 + 0.5, 1),
            value=round(median * 100, 1), step=0.1, format="%.1f",
            key=f"criterion_value_{index}_{option.key}",
        )
        return float(entered) / 100

    return float(
        st.number_input(
            "Value" if index == 0 else " ",
            min_value=0.0, max_value=round(high + 0.05, 2), value=round(median, 2),
            step=0.01, format="%.2f",
            key=f"criterion_value_{index}_{option.key}",
        )
    )


def _reading(frame: pd.DataFrame, option: Filterable, criterion: Criterion) -> None:
    """State the bar both ways: what it is worth, and what share of the league it keeps."""
    place = shortlist.percentile_of_value(frame, option.key, criterion.value)
    if place is None:
        st.caption("Nobody in the league above has this number — widen the scope bar.")
        return

    counted = int(shortlist.pool(frame, option.key).sum())
    kept = (1 - place) if criterion.at_least else place
    st.caption(
        f"**{option.label}** {'at least' if criterion.at_least else 'at most'} "
        f"**{fmt.value(option.fmt, criterion.value)}** — {fmt.ordinal(place)} percentile, "
        f"keeping the {'top' if criterion.at_least else 'bottom'} {kept:.0%} of the "
        f"{counted} players who have this number."
    )


def builder(frame: pd.DataFrame) -> tuple[Criterion, ...]:
    """Render the criteria rows and return the ones the reader filled in."""
    _rows(frame)
    return st.session_state.get(_BUILT, ())


@st.fragment
def _rows(frame: pd.DataFrame) -> None:
    """The rows themselves, redrawn on their own until a bar actually moves.

    Stacking a row, or opening the metric selector, changes nothing about who is on
    the list — yet each of those clicks used to redraw the page: the table, the
    export, and every figure of an opened profile. The block is a fragment, so that
    work waits for the moment a criterion really changes, and is asked for then.
    """
    by_title = {option.title: option for option in shortlist.options()}
    # The season totals head the list: a search starts with how much a player
    # played, and the boards' metrics are what narrows it afterwards. The rest run
    # alphabetically, which gathers each family the glossary names — every `Ball
    # Handler -` together, every `Contested -` together. Case is ignored, or eFG%
    # would sort behind every capital letter in the list.
    titles = sorted(
        by_title,
        key=lambda title: (by_title[title].group != shortlist.GENERAL_GROUP, title.lower()),
    )

    count = int(st.session_state.get(_STORE, _OPENING_ROWS))
    built: list[Criterion] = []

    for index in range(count):
        metric_col, split_col, bar_col, mode_col, value_col = st.columns(
            [2.6, 1.4, 1.1, 1.2, 1.4]
        )
        with metric_col:
            title = st.selectbox(
                "Metric" if index == 0 else " ",
                ["—", *titles],
                key=f"criterion_metric_{index}",
                help=None if index else "Every metric the boards display can be filtered on here.",
            )
        if title == "—":
            continue

        option = by_title[title]
        metric = _split_picker(option, index, split_col)
        described = shortlist.describe(metric)
        with bar_col:
            at_least = st.selectbox(
                "Bar" if index == 0 else " ", ["at least", "at most"],
                key=f"criterion_dir_{index}",
            ) == "at least"
        with mode_col:
            by_percentile = st.selectbox(
                "Set by" if index == 0 else " ", list(_MODES),
                index=_mode_index(described),
                key=f"criterion_mode_{index}",
            ) == "Percentile"
        with value_col:
            value = _value_input(frame, described, index, by_percentile)

        if value is None:
            st.caption("Nobody in the league above has this number — widen the scope bar.")
            continue

        criterion = Criterion(metric, at_least, float(value))
        _reading(frame, described, criterion)
        built.append(criterion)

    # Both buttons are always drawn and greyed out at the bounds: hiding one of them
    # would take a column out of the row and shift the other under the reader's cursor.
    add, remove, _ = st.columns([1, 1, 4])
    with add:
        st.button(
            "Add a criterion", key="criteria_add", width="stretch",
            disabled=count >= MAX_CRITERIA, on_click=_stack, args=(1,),
        )
    with remove:
        st.button(
            "Remove the last", key="criteria_remove", width="stretch",
            disabled=count <= 1, on_click=_stack, args=(-1,),
        )

    # A criterion compares by value, so this is "did any bar move", not "was
    # anything clicked". On the very first run there is nothing to compare against
    # and the page is still on its way down — storing is enough.
    criteria = tuple(built)
    previous = st.session_state.get(_BUILT)
    st.session_state[_BUILT] = criteria
    if previous is not None and previous != criteria:
        st.rerun(scope="app")


def summary(criteria: tuple[Criterion, ...]) -> str:
    """The shortlist written out as a sentence, for the reader to check."""
    if not criteria:
        return "No criterion yet — the whole league is listed."

    parts = []
    for criterion in criteria:
        # The exact column, not the metric it was folded under: the glossary name
        # carries the coverage, so the sentence says "(vs Ice)" where it applies.
        option = shortlist.describe(criterion.metric)
        bar = "at least" if criterion.at_least else "at most"
        parts.append(f"**{option.label}** {bar} {fmt.value(option.fmt, criterion.value)}")
    return " · ".join(parts)
