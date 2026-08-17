"""Rendering the shortlist table.

There is no panel of minimums here, unlike the boards. Every bar on this page is a
criterion the reader wrote, and the sample every number rests on is the scope bar
at the top of the page — the same one the boards answer to.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui import columns, tables
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

    styler = tables.tint_percentiles(
        display.style.format(formatters, na_rep=fmt.BLANK), display, formats, palette
    ).apply(row_style, axis=1)

    if as_percentiles:
        tables.percentile_key()

    st.dataframe(
        styler,
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
