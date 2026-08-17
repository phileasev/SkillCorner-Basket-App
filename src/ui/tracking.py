"""What the app tells the journal, and the one identifier it keeps.

Session state lives here rather than in `src.data.usage`, which stays a pure
module over a frame plus one append. The identifier is a random string drawn once
per browser session: no name, no address, no account, nothing that outlives the
tab.
"""

from __future__ import annotations

import uuid

import streamlit as st

from src.core.metrics import View
from src.core.thresholds import PopulationFilter
from src.data import usage

_SESSION: str = "usage_session_id"
_LAST: str = "usage_last_signature"

#: Turning the journal off is a checkbox on the admin page, kept in session state
#: so it is obvious and reversible rather than a constant somebody has to edit.
_ENABLED: str = "usage_enabled"


def session_id() -> str:
    """The random identifier for this browser session, drawn on first use."""
    if _SESSION not in st.session_state:
        st.session_state[_SESSION] = uuid.uuid4().hex[:12]
    return str(st.session_state[_SESSION])


def enabled() -> bool:
    """Whether the journal is being written. On unless the reader says otherwise."""
    return bool(st.session_state.get(_ENABLED, True))


def set_enabled(value: bool) -> None:
    """Turn the journal on or off for this session."""
    st.session_state[_ENABLED] = bool(value)


def record(
    page: str,
    scope: PopulationFilter,
    *,
    lens: str | None = None,
    view: View | None = None,
    minimum: int | None = None,
    sort: str | None = None,
    percentiles: bool = False,
    player: str | None = None,
) -> None:
    """Note the state the app is currently in, if it is not the state already noted.

    Called at the end of a page's body, once the reader's choices are all known.
    Nothing here can raise: the journal is a convenience and must never be the
    reason a page fails to draw.
    """
    if not enabled():
        return

    st.session_state[_LAST] = usage.append(
        {
            "session": session_id(),
            "page": page,
            "lens": lens,
            "view": view.key if view is not None else None,
            "minimum": minimum,
            "minimum_default": view.threshold.default if view is not None else None,
            "games": scope.min_games,
            "attempts": scope.min_attempts,
            "team": scope.team,
            "traded": scope.exclude_traded,
            # The query itself is never written down — only whether there was one.
            # What a scout typed is the one thing on this screen worth calling private.
            "searched": bool(scope.name_query),
            "sort": sort,
            "mode": "percentiles" if percentiles else "values",
            "player": player,
        },
        st.session_state.get(_LAST),
    )
