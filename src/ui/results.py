"""Rendering the shortlist: the panel of minimums, and the table itself."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import shortlist
from src.data import glossary
from src.ui import columns
from src.ui import format as fmt
from src.ui import theme
from src.ui.columns import PERCENTILE, PLAYER


def minimums(frame: pd.DataFrame, counts: tuple[str, ...]) -> dict[str, int]:
    """One minimum per count the table rests on, all defaulted and all movable.

    The boards gate one metric at a time because a board is about one metric. The
    shortlist shows everything at once, so it gates the counts the boards
    themselves gate on, each defaulted to the same value they use.
    """
    chosen: dict[str, int] = {}
    slots = st.columns(3)

    for index, denominator in enumerate(counts):
        if denominator not in frame.columns:
            continue
        highest = int(frame[denominator].fillna(0).max())
        if highest <= 0:
            continue
        with slots[index % 3]:
            chosen[denominator] = int(
                st.slider(
                    columns.count_name(denominator),
                    min_value=0,
                    max_value=highest,
                    value=min(shortlist.default_minimum(denominator), highest),
                    step=1,
                    key=f"floor_{denominator}",
                    help=glossary.definition(denominator) or None,
                )
            )
    return chosen


def render(
    frame: pd.DataFrame,
    floors: dict[str, int],
    opened: tuple[str, ...],
    *,
    key: str,
    selected: str | None,
    as_percentiles: bool = False,
    league: pd.DataFrame | None = None,
) -> None:
    """Draw the shortlist."""
    display, formats = columns.build(frame, floors, as_percentiles, league)
    palette = theme.palette()

    formatters = {
        header: (
            fmt.percentile
            if kind == PERCENTILE
            else (lambda value, kind=kind: fmt.value(kind, value))
        )
        for header, kind in formats.items()
    }

    def row_style(row: pd.Series) -> list[str]:
        if selected is not None and row[PLAYER] == selected:
            return [f"background-color: {palette.selected}; font-weight: 600"] * len(row)
        return [""] * len(row)

    st.dataframe(
        display.style.format(formatters, na_rep=fmt.BLANK).apply(row_style, axis=1),
        width="stretch",
        hide_index=True,
        row_height=32,
        height=42 + 32 * min(max(len(display), 1), 14),
        column_order=[header for header in opened if header in display.columns],
        column_config=columns.column_config(display),
        on_select="rerun",
        selection_mode="single-cell",
        key=key,
    )
