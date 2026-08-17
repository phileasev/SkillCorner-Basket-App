"""The league table: one table, players below the minimum greyed out at the bottom.

Enabling column selection on `st.dataframe` switches off the grid's own sorting,
which hands the row order back to us: a header click arrives as an event, we sort
on it, and the greyed players stay pinned under the measured ones whatever the
reader picks.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from pandas.io.formats.style import Styler

from src.core import catalogue, metrics, ranking, thresholds
from src.core.metrics import View
from src.core.ranking import ELIGIBLE
from src.data import glossary, schema
from src.ui import format as fmt
from src.ui import theme

PLAYER_LABEL: str = "Player"
TEAM_LABEL: str = "Team"
#: Named the way the glossary names it, since the shortlist filters on it under
#: that name. Player and team are identity, and are named nowhere else.
GAMES_LABEL: str = glossary.name(schema.GAMES_PLAYED)

PERCENTILE: str = "percentile"

ROW_HEIGHT: int = 32
HEADER_HEIGHT: int = 42
#: Rows shown before the table starts scrolling.
VISIBLE_ROWS: int = 18


def sample_label(column: str, view: View | None = None) -> str:
    """Header for a count column: the name the data dictionary gives it.

    Minus what the board on screen already says: a pick-and-roll table has the
    role in its lens selector, so repeating it seven times only pushes the last
    columns off the right edge.
    """
    name = glossary.name(column)
    return catalogue.short(view, name) if view is not None else name


def layout(view: View) -> list[tuple[str, str]]:
    """Every column the table shows, as `(header, frame column)`, in order.

    A count that a view already displays in its own right is not repeated as the
    sample size of a rate built on it: `attempts` is both the shot volume and the
    denominator of eFG%, and printing it twice under two spellings of "shots"
    reads as two different numbers.
    """
    shown = {column.key for column in view.columns}
    columns: list[tuple[str, str]] = []

    for column in view.columns:
        columns.append((catalogue.short(view, column.label), column.key))
        if column.sample is not None and column.sample not in shown:
            shown.add(column.sample)
            columns.append((sample_label(column.sample, view), column.sample))

    return columns


def build(
    frame: pd.DataFrame, view: View, as_percentiles: bool = False
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Assemble the display frame for a view.

    Values stay numeric so a header click still sorts sensibly; only the formatting
    is applied later, by the styler.

    Args:
        frame: the population, already flagged and ordered.
        view: the view on screen.
        as_percentiles: show each metric as the player's place in the eligible pool
            rather than its raw value. Counts are left as counts either way — a
            number of shots is a fact, not a standing.

    Returns:
        The display frame, and the format key to use for each of its columns.
    """
    display = pd.DataFrame(index=frame.index)
    formats: dict[str, str] = {}

    display[PLAYER_LABEL] = frame[schema.PLAYER_NAME]
    display[TEAM_LABEL] = frame[schema.TEAM_NAME]

    games_placed = ranking.percentile_of(schema.GAMES_PLAYED)
    if as_percentiles and games_placed in frame.columns:
        display[GAMES_LABEL] = frame[games_placed]
        formats[GAMES_LABEL] = PERCENTILE
    else:
        display[GAMES_LABEL] = frame[schema.GAMES_PLAYED]
        formats[GAMES_LABEL] = metrics.INT

    blanked = {
        column.key: column
        for column in view.columns
        if column.sample is not None and column.min_sample > 0
    }
    formats_by_key = {column.key: column.fmt for column in view.columns}

    for label, key in layout(view):
        # Counts are placed too. A number of shots is a fact, but where that fact
        # sits in the league is another one, and a reader who has switched the whole
        # table to standings did not ask for two readings at once. Switching back
        # is one click, and the values are what the table opens on.
        placed = ranking.percentile_of(key)
        use_percentile = as_percentiles and placed in frame.columns

        values = frame[placed] if use_percentile else frame[key]
        column = blanked.get(key)
        if column is not None:
            values = values.where(thresholds.sample_mask(frame, column.sample, column.min_sample))

        display[label] = values
        formats[label] = PERCENTILE if use_percentile else formats_by_key.get(key, metrics.INT)

    return display, formats


def style(
    display: pd.DataFrame,
    formats: dict[str, str],
    eligible: pd.Series,
    sorted_label: str | None = None,
    selected: str | None = None,
) -> Styler:
    """Format the frame, grey players below the minimum, mark the order and the pick.

    Both highlights are painted here rather than left to the grid's own selection:
    that selection is how a click reaches us, and doing the marking ourselves keeps
    the two jobs apart. The loaded player's row is drawn last so it wins over the
    sorted column where the two cross.
    """
    palette = theme.palette()
    flags = eligible.reindex(display.index).fillna(False)

    formatters = {
        label: (
            fmt.percentile
            if key == PERCENTILE
            else (lambda value, key=key: fmt.value(key, value))
        )
        for label, key in formats.items()
    }
    def row_style(row: pd.Series) -> list[str]:
        greyed = not bool(flags.loc[row.name])
        return [f"color: {palette.muted}" if greyed else ""] * len(row)

    styler = display.style.format(formatters, na_rep=fmt.BLANK).apply(row_style, axis=1)

    if sorted_label in display.columns:
        styler = styler.apply(
            lambda column: [f"background-color: {palette.highlight}"] * len(column),
            axis=0,
            subset=[sorted_label],
        )

    if selected is not None and (display[PLAYER_LABEL] == selected).any():
        picked = display.index[display[PLAYER_LABEL] == selected]
        styler = styler.apply(
            lambda row: [f"background-color: {palette.selected}; font-weight: 600"] * len(row),
            axis=1,
            subset=(picked, display.columns),
        )
    return styler


def column_config(view: View, sorted_label: str | None, marker: str) -> dict[str, object]:
    """Column headers carrying the glossary definition, and the sort marker."""
    tips: dict[str, str] = {
        GAMES_LABEL: glossary.definition(schema.GAMES_PLAYED),
        TEAM_LABEL: "Club the player finished the season with.",
    }
    counts = {column.sample for column in view.columns if column.sample is not None}
    for label, key in layout(view):
        tips[label] = glossary.definition(key)
        if key in counts and key not in {c.key for c in view.columns}:
            tips[label] = "How many shots the number beside it is built on. " + tips[label]

    return {
        label: st.column_config.Column(
            label=f"{label} {marker}" if label == sorted_label else label,
            help=text or None,
        )
        for label, text in tips.items()
    }


def sort_targets(view: View) -> dict[str, str]:
    """Header label to the frame column clicking it orders the table on."""
    targets: dict[str, str] = {
        PLAYER_LABEL: schema.PLAYER_NAME,
        TEAM_LABEL: schema.TEAM_NAME,
        GAMES_LABEL: schema.GAMES_PLAYED,
    }
    targets.update({label: key for label, key in layout(view)})
    return targets


def render(
    frame: pd.DataFrame,
    view: View,
    *,
    key: str,
    sorted_label: str | None = None,
    marker: str = "",
    selected: str | None = None,
    as_percentiles: bool = False,
) -> None:
    """Draw the table.

    Cells and columns are selectable, rows are not: clicking anywhere on a line
    loads that player, so the grid shows no tick boxes. Enabling column selection
    is also what switches off the grid's own sorting, which is how the greyed
    players stay at the bottom whatever the order.
    """
    display, formats = build(frame, view, as_percentiles)

    st.dataframe(
        style(display, formats, frame[ELIGIBLE], sorted_label, selected),
        width="stretch",
        hide_index=True,
        row_height=ROW_HEIGHT,
        height=HEADER_HEIGHT + ROW_HEIGHT * min(max(len(display), 1), VISIBLE_ROWS),
        column_config=column_config(view, sorted_label, marker),
        on_select="rerun",
        selection_mode=["single-cell", "single-column"],
        key=key,
    )
