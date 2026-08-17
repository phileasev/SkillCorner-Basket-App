"""Reusable controls: the scope row and the minimum behind each number."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import catalogue, metrics, thresholds
from src.core.metrics import View
from src.data import glossary, loader, schema


#: Where the scope bar's answers live between pages. A widget's own state is
#: dropped the moment it is not drawn, and moving to another page is exactly that
#: for one run — so the choice is kept under keys of our own and the widgets are
#: seeded from them. Without it the bar would silently reset to fifteen games every
#: time the reader crossed from the shortlist to a board.
_STORE: str = "scope_choice"


def _remembered_scope() -> dict[str, object]:
    """The scope the reader last set, or the defaults on the very first run."""
    stored = st.session_state.get(_STORE)
    if isinstance(stored, dict):
        return stored
    return {
        "team": "All teams",
        "games": thresholds.DEFAULT_MIN_GAMES,
        "attempts": metrics.SEASON_MINIMUM,
        "query": "",
        "traded": False,
    }


def scope_row(frame: pd.DataFrame, league: pd.DataFrame | None = None) -> thresholds.PopulationFilter:
    """Render the scope bar and return the population it describes.

    This is the one control that reaches the whole app. It says who counts as a
    league player, so it decides the rows on every table, the dots on every plot,
    the median line under every bar and — above all — the pool every percentile in
    the app is measured against. It is identical on the three pages and keeps its
    answers when the reader moves between them.

    Args:
        frame: the page's own dataset, for the team list.
        league: the same file before any filtering, so the line underneath can say
            what the bar costs. Defaults to `frame`.
    """
    kept = _remembered_scope()
    team_col, games_col, shots_col, search_col, traded_col = st.columns(
        [1.4, 1, 1.1, 1.5, 1.3]
    )

    with team_col:
        teams = ["All teams", *loader.teams(frame)]
        team = st.selectbox(
            "Team", teams,
            index=teams.index(kept["team"]) if kept["team"] in teams else 0,
            key="scope_team",
        )

    with games_col:
        choices = list(thresholds.GAMES_CHOICES)
        games = st.selectbox(
            "Minimum games", choices,
            index=choices.index(kept["games"]) if kept["games"] in choices else 0,
            format_func=lambda value: "Any" if value == 0 else f"{value}+",
            help=glossary.definition(schema.GAMES_PLAYED),
            key="scope_games",
        )

    with shots_col:
        shots = list(thresholds.SHOT_CHOICES)
        attempts = st.selectbox(
            "Minimum shots", shots,
            index=shots.index(kept["attempts"]) if kept["attempts"] in shots else 0,
            format_func=lambda value: "Any" if value == 0 else f"{value}+",
            help=(
                "Shots taken all season. One a game over the 34-round regular season "
                "is 35, which is where this opens. " + glossary.definition(schema.ATTEMPTS)
            ),
            key="scope_attempts",
        )

    with search_col:
        query = st.text_input(
            "Find a player", value=str(kept["query"]), placeholder="Name…", key="scope_query"
        )

    with traded_col:
        st.write("")
        exclude_traded = st.checkbox(
            "Hide players who changed team",
            value=bool(kept["traded"]),
            help=glossary.definition(schema.IS_TRADED),
            key="scope_traded",
        )

    st.session_state[_STORE] = {
        "team": team, "games": int(games), "attempts": int(attempts),
        "query": query.strip(), "traded": bool(exclude_traded),
    }

    scope = thresholds.PopulationFilter(
        min_games=int(games),
        min_attempts=int(attempts),
        exclude_traded=exclude_traded,
        team=None if team == "All teams" else team,
        name_query=query.strip(),
    )
    st.caption(scope_reading(league if league is not None else frame, scope))
    return scope


def scope_reading(frame: pd.DataFrame, scope: thresholds.PopulationFilter) -> str:
    """What the bar costs, in players — so a default is never applied unseen.

    A reader who is shown 213 names has no way of knowing whether the file holds
    220 or 500, and the two answers make the same list mean different things.
    """
    total = len(frame)
    pool = int(thresholds.league_mask(frame, scope).sum())
    line = (
        f"**{pool}** of {total} players are the league here"
        f" — every percentile in the app is measured among them."
    )
    if pool < total:
        line += f" {total - pool} fall under the bars above."
    return line


def _remembered(view: View, high: int) -> int:
    """The minimum this view was last left on, or its default.

    Streamlit drops the state of a widget that was not drawn on the previous run,
    so a slider belonging to another view would reset on the way back. The choice
    is kept here instead, under a key of our own.
    """
    store = f"minimum_choice_{view.key}"
    if store not in st.session_state:
        st.session_state[store] = min(view.threshold.default, high)
    return min(int(st.session_state[store]), high)


def events_word(view: View) -> str:
    """"shots" or "picks", for the controls and messages that talk about the count.

    A pick-and-roll board asking for a minimum number of *shots* names the wrong
    thing, and the card points the reader back at this panel by its title.
    """
    return "picks" if "picks" in view.threshold.key else "shots"


def minimum_title(view: View) -> str:
    """The panel's own heading, quoted wherever the reader is sent back to it."""
    return f"Minimum {events_word(view)} behind each number"


def minimum_expander(frame: pd.DataFrame, view: View) -> tuple[int, bool]:
    """Render the collapsed minimum-shots control for a view.

    Returns:
        The minimum the reader chose, and whether players below it stay visible.
    """
    low, high = thresholds.slider_bounds(frame, view)
    high = max(high, 1)

    with st.expander(minimum_title(view), expanded=False):
        slider_col, toggle_col = st.columns([2, 1.4])
        with slider_col:
            minimum = st.slider(
                catalogue.short(view, view.threshold.label),
                min_value=low,
                max_value=high,
                value=_remembered(view, high),
                step=metrics.MINIMUM_STEP,
                help=glossary.definition(view.threshold.key),
                key=f"minimum_widget_{view.key}",
            )
            st.caption(f"League high for this count: {high}")
        with toggle_col:
            st.write("")
            show_ineligible = st.checkbox(
                "Show players below the minimum",
                value=st.session_state.get("show_ineligible_choice", True),
                key="show_ineligible_widget",
            )

    st.session_state[f"minimum_choice_{view.key}"] = int(minimum)
    st.session_state["show_ineligible_choice"] = bool(show_ineligible)
    return int(minimum), bool(show_ineligible)


def value_mode(scope: object) -> bool:
    """Whether the table shows standings rather than raw numbers.

    Both readings order the players identically — a percentile is the raw value
    re-expressed against the same pool — so this changes what is printed, never
    who comes first.
    """
    chosen = st.segmented_control(
        "Show",
        ["Values", "Percentiles"],
        default="Values",
        label_visibility="collapsed",
        key=f"value_mode_{getattr(scope, 'key', 'shortlist')}",
    )
    return chosen == "Percentiles"


def lens_picker(lenses: tuple[catalogue.Lens, ...]) -> catalogue.Lens:
    """Render the lens selector for one page and return the chosen lens."""
    labels = {lens.label: lens for lens in lenses}
    chosen = st.segmented_control(
        "Lens",
        list(labels),
        default=list(labels)[0],
        label_visibility="collapsed",
        key=f"lens_{lenses[0].key}",
    )
    return labels.get(chosen or list(labels)[0])


def view_picker(lens: catalogue.Lens) -> View:
    """Render the shot-type selector inside a lens, when it has more than one view."""
    if len(lens.views) == 1:
        return lens.views[0]
    labels = {view.label: view for view in lens.views}
    chosen = st.segmented_control(
        lens.view_label,
        list(labels),
        default=list(labels)[0],
        label_visibility="collapsed",
        key=f"view_{lens.key}",
    )
    return labels.get(chosen or list(labels)[0])
