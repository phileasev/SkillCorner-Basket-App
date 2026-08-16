"""Reusable controls: the scope row and the minimum behind each number."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import catalogue, thresholds
from src.core.metrics import View
from src.data import glossary, loader, schema


def scope_row(frame: pd.DataFrame) -> thresholds.PopulationFilter:
    """Render the scope controls and return the population filter they describe."""
    team_col, games_col, search_col, traded_col = st.columns([1.4, 1, 1.6, 1.4])

    with team_col:
        teams = ["All teams", *loader.teams(frame)]
        team = st.selectbox("Team", teams, index=0, key="scope_team")

    with games_col:
        choices = list(thresholds.GAMES_CHOICES)
        games = st.selectbox(
            "Minimum games",
            choices,
            index=choices.index(thresholds.DEFAULT_MIN_GAMES),
            format_func=lambda value: "Any" if value == 0 else f"{value}+",
            help=glossary.definition(schema.GAMES_PLAYED),
            key="scope_games",
        )

    with search_col:
        query = st.text_input("Find a player", placeholder="Name…", key="scope_query")

    with traded_col:
        st.write("")
        exclude_traded = st.checkbox(
            "Hide players who changed team",
            help=glossary.definition(schema.IS_TRADED),
            key="scope_traded",
        )

    return thresholds.PopulationFilter(
        min_games=int(games),
        team=None if team == "All teams" else team,
        exclude_traded=exclude_traded,
        name_query=query.strip(),
    )


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


def minimum_expander(frame: pd.DataFrame, view: View) -> tuple[int, bool]:
    """Render the collapsed minimum-shots control for a view.

    Returns:
        The minimum the reader chose, and whether players below it stay visible.
    """
    low, high = thresholds.slider_bounds(frame, view)
    high = max(high, 1)

    with st.expander("Minimum shots behind each number", expanded=False):
        slider_col, toggle_col = st.columns([2, 1.4])
        with slider_col:
            minimum = st.slider(
                view.threshold.label,
                min_value=low,
                max_value=high,
                value=_remembered(view, high),
                step=5,
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


def value_mode() -> bool:
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
        key="value_mode",
    )
    return chosen == "Percentiles"


def lens_picker() -> catalogue.Lens:
    """Render the lens selector and return the chosen lens."""
    labels = {lens.label: lens for lens in catalogue.LENSES}
    chosen = st.segmented_control(
        "Lens", list(labels), default=list(labels)[0], label_visibility="collapsed"
    )
    return labels.get(chosen or list(labels)[0])


def view_picker(lens: catalogue.Lens) -> View:
    """Render the shot-type selector inside a lens, when it has more than one view."""
    if len(lens.views) == 1:
        return lens.views[0]
    labels = {view.label: view for view in lens.views}
    chosen = st.segmented_control(
        "Shot type",
        list(labels),
        default=list(labels)[0],
        label_visibility="collapsed",
        key=f"view_{lens.key}",
    )
    return labels.get(chosen or list(labels)[0])
