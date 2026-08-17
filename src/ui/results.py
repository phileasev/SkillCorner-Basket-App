"""Rendering the shortlist table.

There is no panel of minimums here, unlike the boards. Every bar on this page is a
criterion the reader wrote, and the sample every number rests on is the scope bar
at the top of the page — the same one the boards answer to.

Column selection is enabled for the same reason it is on the boards: it switches
off the grid's built-in sorting and hands the row order back to us. The grid sorts
a column upwards by floating every empty cell to the top, and a blank is not a low
number — a player with no guarded threes has not shot the worst percentage on them.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui import columns
from src.ui import format as fmt
from src.ui import theme
from src.ui.columns import PERCENTILE, PLAYER


def render(
    frame: pd.DataFrame,
    opened: tuple[str, ...],
    *,
    key: str,
    selected: str | None,
    as_percentiles: bool = False,
    league: pd.DataFrame | None = None,
    sorted_label: str | None = None,
    marker: str = "",
) -> None:
    """Draw the shortlist."""
    display, formats = columns.build(frame, as_percentiles, league)
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

    styler = display.style.format(formatters, na_rep=fmt.BLANK).apply(row_style, axis=1)
    if sorted_label in display.columns:
        styler = styler.apply(
            lambda column: [f"background-color: {palette.highlight}"] * len(column),
            axis=0,
            subset=[sorted_label],
        )

    st.dataframe(
        styler,
        width="stretch",
        hide_index=True,
        row_height=32,
        height=42 + 32 * min(max(len(display), 1), 14),
        column_order=[header for header in opened if header in display.columns],
        column_config=columns.column_config(display, sorted_label, marker),
        on_select="rerun",
        selection_mode=["single-cell", "single-column"],
        key=key,
    )


def sort_targets(display_columns: list[str]) -> dict[str, str]:
    """Header label to the frame column clicking it orders the table on."""
    targets = dict(columns.frame_columns())
    return {header: column for header, column in targets.items() if header in display_columns}
