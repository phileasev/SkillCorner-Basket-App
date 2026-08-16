"""Which column the table is ordered on, driven by clicks on its own headers.

Enabling column selection on `st.dataframe` turns off its built-in sorting, which
hands the row order back to us. A header click arrives as an event instead of
reordering the grid behind our back, so players below the minimum can be held at
the bottom whatever the reader sorts on.

Nothing is sorted to begin with: the board opens on the view's own metric, which
is the order the page is about, and no header is marked until the reader picks one.
"""

from __future__ import annotations

import streamlit as st

from src.core.metrics import View
from src.data import schema

#: Columns where the reader expects A before Z rather than best first.
_TEXT_COLUMNS: frozenset[str] = frozenset({schema.PLAYER_NAME, schema.TEAM_NAME})

#: Appended to the header of the column the table is ordered on.
ARROW_DESCENDING: str = "▼"
ARROW_ASCENDING: str = "▲"


def arrow(ascending: bool) -> str:
    """The marker shown on the sorted column's header."""
    return ARROW_ASCENDING if ascending else ARROW_DESCENDING


def plain_label(label: str) -> str:
    """A header label with its sort marker removed.

    The grid reports the header as the reader sees it, marker included, so the
    marker is stripped before the label is matched back to a column.
    """
    return label.removesuffix(ARROW_DESCENDING).removesuffix(ARROW_ASCENDING).strip()


def _column_store(view: View) -> str:
    return f"sort_column_{view.key}"


def _ascending_store(view: View) -> str:
    return f"sort_ascending_{view.key}"


def _click_store(table_key: str) -> str:
    # Scoped to the table's own key: re-ordering rebuilds the table, and a click on
    # the same header must read as a new click rather than as the old one echoing.
    return f"sort_last_click_{table_key}"


def chosen(view: View) -> tuple[str | None, bool]:
    """The column the reader picked, or None while he has picked none."""
    column = st.session_state.get(_column_store(view))
    ascending = bool(st.session_state.get(_ascending_store(view), False))
    return (str(column) if column else None), ascending


def order_by(view: View) -> tuple[str, bool]:
    """The column the table is actually ordered on, chosen or not.

    Falling back to the view's own metric means the board opens on the ranking it
    exists to show, without claiming the reader asked for it.
    """
    column, ascending = chosen(view)
    return (column, ascending) if column else (view.rank_column.key, False)


def default_direction(column: str) -> bool:
    """Whether a column should open ascending: names read A to Z, numbers best first."""
    return column in _TEXT_COLUMNS


def apply_header_click(
    view: View, clicked: list[str], targets: dict[str, str], table_key: str
) -> bool:
    """Update the ordering from a header click, if that click is a new one.

    Args:
        view: the view on screen.
        clicked: header labels the table reports as selected.
        targets: header label to the frame column it orders on.
        table_key: key of the table those labels came from.

    Returns:
        True when this click changed the ordering.
    """
    label = plain_label(clicked[0]) if clicked else None
    store = _click_store(table_key)
    if label == st.session_state.get(store):
        return False
    st.session_state[store] = label

    column = targets.get(label) if label else None
    if column is None:
        return False

    active, ascending = chosen(view)
    st.session_state[_column_store(view)] = column
    st.session_state[_ascending_store(view)] = (
        not ascending if column == active else default_direction(column)
    )
    return True


def label_of(column: str | None, targets: dict[str, str]) -> str | None:
    """The header showing a given frame column, for marking it as sorted."""
    if column is None:
        return None
    return next((label for label, key in targets.items() if key == column), None)


def reverse(view: View) -> None:
    """Flip the current ordering, adopting the default column if none was picked."""
    column, ascending = order_by(view)
    st.session_state[_column_store(view)] = column
    st.session_state[_ascending_store(view)] = not ascending


def caption(view: View, targets: dict[str, str]) -> str:
    """One line telling the reader how the table is ordered and how to change it."""
    column, ascending = chosen(view)
    if column is None:
        return (
            f"Ordered by **{view.rank_column.label}**, the metric this view is about — "
            "click any column header to sort by it."
        )

    label = label_of(column, targets) or column
    if column in _TEXT_COLUMNS:
        order = "A to Z" if ascending else "Z to A"
    else:
        order = "lowest first" if ascending else "highest first"
    return (
        f"Sorted by **{label}** {arrow(ascending)}, {order} — "
        "click any column header to sort by it, click it again to reverse."
    )
