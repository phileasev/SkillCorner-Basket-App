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
from src.data import glossary
from src.ui import format as fmt

#: How many criteria the reader can stack. Past this the list stops being a list.
MAX_CRITERIA: int = 5

_STORE: str = "criteria_count"

def _is_share(option: Filterable) -> bool:
    """Whether the metric is a 0-1 ratio the reader thinks of in percent."""
    return option.fmt in (metrics.PCT0, metrics.PCT1)


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


def _minimum_input(frame: pd.DataFrame, option: Filterable, index: int) -> int:
    """How many events the bar has to rest on."""
    if option.denominator is None:
        st.caption(" ")
        return 0
    return int(
        st.number_input(
            "On at least" if index == 0 else " ",
            min_value=0,
            max_value=int(frame[option.denominator].fillna(0).max()),
            value=shortlist.default_minimum(option.denominator),
            step=5,
            key=f"criterion_min_{index}_{option.key}",
            help="Events the value has to rest on. " + glossary.definition(option.denominator),
        )
    )


def _value_input(
    frame: pd.DataFrame, option: Filterable, minimum: int, index: int, by_percentile: bool
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
            help="Where the bar sits among the players who clear the events required.",
        )
        return shortlist.value_at_percentile(frame, option.key, minimum, place / 100)

    median = shortlist.value_at_percentile(frame, option.key, minimum, 0.5)
    if median is None:
        return None

    values = frame.loc[shortlist.pool(frame, option.key, minimum), option.key].dropna()
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
    place = shortlist.percentile_of_value(frame, option.key, criterion.minimum, criterion.value)
    if place is None:
        st.caption("Nobody clears the events required — lower them.")
        return

    counted = int(shortlist.pool(frame, option.key, criterion.minimum).sum())
    kept = (1 - place) if criterion.at_least else place
    st.caption(
        f"**{option.label}** {'at least' if criterion.at_least else 'at most'} "
        f"**{fmt.value(option.fmt, criterion.value)}** — {fmt.ordinal(place)} percentile, "
        f"keeping the {'top' if criterion.at_least else 'bottom'} {kept:.0%} of the "
        f"{counted} players with enough events."
    )


def builder(frame: pd.DataFrame) -> tuple[Criterion, ...]:
    """Render the criteria rows and return the ones the reader filled in."""
    by_title = {option.title: option for option in shortlist.options()}
    titles = sorted(by_title)

    count = int(st.session_state.get(_STORE, 1))
    built: list[Criterion] = []

    for index in range(count):
        metric_col, split_col, bar_col, mode_col, value_col, sample_col = st.columns(
            [2.4, 1.3, 1.0, 1.1, 1.3, 1.1]
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
        with bar_col:
            at_least = st.selectbox(
                "Bar" if index == 0 else " ", ["at least", "at most"],
                key=f"criterion_dir_{index}",
            ) == "at least"
        with sample_col:
            minimum = _minimum_input(frame, shortlist.describe(metric), index)
        with mode_col:
            # Percentile first: "the top 20% of the league" is the question a scout
            # arrives with, and the exact number is what he tunes afterwards.
            by_percentile = st.selectbox(
                "Set by" if index == 0 else " ", ["Percentile", "Value"],
                key=f"criterion_mode_{index}",
            ) == "Percentile"
        with value_col:
            value = _value_input(frame, shortlist.describe(metric), minimum, index, by_percentile)

        if value is None:
            st.caption("Nobody clears the events required — lower them.")
            continue

        criterion = Criterion(metric, at_least, float(value), int(minimum))
        _reading(frame, shortlist.describe(metric), criterion)
        built.append(criterion)

    add, remove, _ = st.columns([1, 1, 4])
    with add:
        if count < MAX_CRITERIA and st.button("Add a criterion", width="stretch"):
            st.session_state[_STORE] = count + 1
            st.rerun()
    with remove:
        if count > 1 and st.button("Remove the last", width="stretch"):
            st.session_state[_STORE] = count - 1
            st.rerun()

    return tuple(built)


def summary(criteria: tuple[Criterion, ...]) -> str:
    """The shortlist written out as a sentence, for the reader to check."""
    if not criteria:
        return "No criterion yet — the whole league is listed."

    parts = []
    for criterion in criteria:
        option = shortlist.option_by_key(criterion.metric)
        bar = "at least" if criterion.at_least else "at most"
        text = f"**{option.label}** {bar} {fmt.value(option.fmt, criterion.value)}"
        if criterion.minimum:
            text += f" on {criterion.minimum}+ {_events(option)}"
        parts.append(text)
    return " · ".join(parts)


def _events(option: Filterable) -> str:
    """What the count behind a metric is called, in the reader's words."""
    if option.denominator is None:
        return "events"
    return "picks" if "picks" in option.denominator else "shots"
