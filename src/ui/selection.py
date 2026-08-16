"""Which player is loaded, kept in one place.

Two rules make the selection feel immediate:

* the inputs are read from session state **before** anything is drawn, so the plot,
  the table and the card all render the same player on the very first click;
* an input is adopted only when its own value changed, so the plot replaying its
  last click cannot overwrite a fresh click in the table, or the reverse.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

SELECTED: str = "selected_player"
#: Bumped whenever something other than the table changes the selection, so the
#: table is rebuilt and can adopt it as a real row selection.
SYNC: str = "_table_sync"


def current() -> str | None:
    """The player currently loaded, or None."""
    return st.session_state.get(SELECTED)


def clear() -> None:
    """Unload the current player, and let the table drop its highlighted row."""
    st.session_state[SELECTED] = None
    st.session_state[SYNC] = table_generation() + 1


def table_generation() -> int:
    """How many times an outside input has moved the selection."""
    return int(st.session_state.get(SYNC, 0))


def _adopt(source: str, picked: str | None, *, from_table: bool) -> None:
    """Take up a player one input is pointing at, if that input just changed.

    Only a fresh, non-empty pick is acted on. An input reporting nothing is never
    read as "unload him": Streamlit drops the state of a widget it did not draw on
    the previous run, so a plot or a table coming back under a key used earlier —
    the reader returning to a filter setting he had already visited — reports
    exactly the same nothing as a widget the reader never touched. Unloading is an
    explicit act, and it has its own button on the card.
    """
    store = f"_last_pick_{source}"
    if picked == st.session_state.get(store):
        return

    st.session_state[store] = picked
    if picked is None:
        return

    if picked != current() and not from_table:
        st.session_state[SYNC] = table_generation() + 1
    st.session_state[SELECTED] = picked


def _state(key: str) -> Any:
    """The stored value of a widget, read before that widget is drawn again."""
    return st.session_state.get(key)


def _points(payload: Any) -> list[dict]:
    holder = _holder(payload)
    return list(holder.get("points", [])) if holder else []


def _holder(payload: Any) -> Any:
    if payload is None:
        return None
    return payload.get("selection") if isinstance(payload, dict) else getattr(payload, "selection", None)


def _clicked_row(payload: Any) -> int | None:
    """The row a cell click landed on.

    The table selects cells rather than rows, so a click anywhere on a line loads
    that player and no tick box is needed. Only the row half of the cell matters,
    and the shape Streamlit reports it in is read defensively.
    """
    holder = _holder(payload)
    cells = list(holder.get("cells", [])) if holder else []
    for cell in cells:
        if isinstance(cell, dict):
            row = cell.get("row", cell.get("row_index"))
        elif isinstance(cell, (list, tuple)) and cell:
            row = cell[0]
        else:
            row = cell
        try:
            return int(row)
        except (TypeError, ValueError):
            continue
    return None


def from_plotly(payload: Any) -> str | None:
    """The player a Plotly click landed on, or None when it landed on nothing."""
    for point in _points(payload):
        data = point.get("customdata")
        if data:
            return str(data[0] if isinstance(data, (list, tuple)) else data)
    return None


def columns_clicked(table_key: str) -> list[str]:
    """Header labels the table currently reports as selected."""
    holder = _holder(_state(table_key))
    return list(holder.get("columns", [])) if holder else []


def sync(*, chart_key: str, table_key: str, names: list[str], adopt_rows: bool = True) -> None:
    """Resolve the selection from the inputs' stored state, before drawing.

    Args:
        chart_key: widget key of the scatter plot.
        table_key: widget key of the league table.
        names: player names in the order the table listed them last.
        adopt_rows: False when the reader just re-sorted, since a stored row index
            then refers to the order the table had before the click.
    """
    if adopt_rows:
        row = _clicked_row(_state(table_key))
        picked_row = names[row] if row is not None and row < len(names) else None
        _adopt(table_key, picked_row, from_table=True)

    _adopt(chart_key, from_plotly(_state(chart_key)), from_table=False)


def is_loaded(name: str | None) -> bool:
    """Whether a given player is the one currently loaded."""
    return name is not None and name == current()
