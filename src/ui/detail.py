"""The "see more" block: one player's whole offensive profile, opened in place.

Everything the two files hold about a player, on one screen and under his own row
— there is not enough on any single player to justify a page of his own.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import profile as player_profile
from src.core.pick_views import HANDLER, SCREENER
from src.core.shot_views import SHOT_PROFILE
from src.data import schema
from src.ui import charts, facets, navigation, profile_charts
from src.ui import format as fmt

#: Shots a zone needs before its accuracy is printed on the court. The same floor
#: the boards apply to their own zone figures, taken from one place so the two
#: cards cannot start disagreeing about what counts as enough.
ZONE_MINIMUM: int = schema.ZONE_MIN_ATTEMPTS


def block(row: pd.Series, population: pd.DataFrame) -> None:
    """Render the full profile of one player, in a panel he can fold away.

    The panel is the card's own heading, so there is no Close button: folding it
    shut is the way out. Nothing is unloaded by folding, so his row stays marked in
    the table.

    The key carries the player's name, which is what makes the panel reopen on the
    next man: a fold is remembered per widget, so under one shared key a reader who
    had shut it would click a new player and watch nothing happen.
    """
    with st.expander(_heading(row), expanded=True, key=f"profile_{row[schema.PLAYER_NAME]}"):
        _shooting(row, population)
        st.divider()
        _picking(row, population)


def _heading(row: pd.Series) -> str:
    """Who he is and how much of him there is, on the panel's own bar."""
    role = row[schema.PRIMARY_ROLE]
    return (
        f"{row[schema.PLAYER_NAME]}  ·  {row[schema.TEAM_NAME]}  ·  "
        f"{int(row[schema.GAMES_PLAYED])} games  ·  "
        f"{fmt.count(row[schema.ATTEMPTS])} shots  ·  "
        f"{fmt.count(row[schema.total_picks(_prefix(role))])} picks as {role}"
    )


def _section(title: str, caption: str, label: str, page: str, icon: str, key: str,
             name: str) -> None:
    """A section heading with the board that goes deeper on it, on the same line.

    The card answers "what is he", a board answers "where does he stand". Each
    button therefore sits directly above the figures it continues, rather than in a
    row of its own at the top where neither one belonged to anything.
    """
    heading, link = st.columns([3, 1.3], vertical_alignment="center")
    with heading:
        st.markdown(f"**{title}**")
        st.caption(caption)
    with link:
        navigation.board_button(
            label,
            page,
            icon=icon,
            help_text=f"Open the {title.lower()} board with {name} loaded, "
            "to see where he stands among everyone else.",
            key=key,
        )


def _shooting(row: pd.Series, population: pd.DataFrame) -> None:
    """Everything the shooting file says about him, under its own board's button.

    The radar rides in this storey rather than standing alone above both. Half its
    spokes are pick-and-roll, so it belongs to neither strictly — but it reads as a
    profile, which is what the shooting side of the card is about, and giving it a
    storey of its own left the panel three deep for one figure.
    """
    _section(
        "Shot quality",
        "What kind of shooter he is, and how many of them go in.",
        "Shot quality board",
        navigation.SHOT_QUALITY,
        ":material/my_location:",
        "open_shot_board",
        row[schema.PLAYER_NAME],
    )

    radar, shooting = st.columns(2, gap="medium")
    with radar:
        _radar(row, population)
    with shooting:
        _shot_chart(row)
        st.markdown("**Shot menu**")
        st.caption("Share of his attempts, from the rim outwards")
        st.plotly_chart(
            charts.breakdown_bar(row, SHOT_PROFILE.breakdown),
            width="stretch",
            config=charts.STATIC,
        )
        facets.legend(row, SHOT_PROFILE.breakdown)


def _picking(row: pd.Series, population: pd.DataFrame) -> None:
    """Everything the pick file says about him, one column per role.

    Both roles, not only his main one: a handful of picks in the other is itself
    worth seeing, and the two face different coverages — folding them together
    would mean choosing which set of five to show and dropping the other.
    """
    _section(
        "Pick & roll",
        "What the defence throws at him, and where his screens are set.",
        "Pick & roll board",
        navigation.PICK_AND_ROLL,
        ":material/group_work:",
        "open_pick_board",
        row[schema.PLAYER_NAME],
    )

    for column, lens, prefix in zip(
        st.columns(2, gap="medium"),
        (HANDLER, SCREENER),
        (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX),
    ):
        with column:
            _role(row, lens, prefix, population)


def _role(row: pd.Series, lens, prefix: str, population: pd.DataFrame) -> None:
    """One role in full: where his screens are set, and what the defence did."""
    counted = schema.total_picks(prefix)
    picks = row.get(counted)
    st.markdown(f"**As {lens.label.lower()}**")
    if not picks or pd.isna(picks):
        st.caption("He was never involved in a screen in this role.")
        return

    # The count and where it sits. A volume with no scale behind it is the one
    # number on this card a reader cannot do anything with.
    place = player_profile.standing(population, counted, row[schema.PLAYER_NAME])
    st.caption(
        f"{fmt.count(picks)} picks"
        + ("" if place is None else f" · {fmt.ordinal(place)} in the league")
    )
    facets.spots_block(row, lens.profile)
    facets.coverage_block(row, lens.profile.coverage, population)


def _prefix(role: str) -> str:
    return (
        schema.ROLE_HANDLER_PREFIX if role == schema.ROLE_HANDLER else schema.ROLE_SCREENER_PREFIX
    )


def _radar(row: pd.Series, population: pd.DataFrame) -> None:
    """His standing on each axis, measured within that axis's own population."""
    st.markdown("**Offensive profile**")
    st.caption(
        "Percentiles: the outer ring is the best in the league, the centre the "
        "worst, and the dotted ring is the middle of it — outside is above average. "
        "Hover a spoke for his own figure. Both pick-and-roll roles are shown — a "
        "player who does a bit of each is not reduced to one."
    )
    scores = player_profile.radar_scores(population, row[schema.PLAYER_NAME])
    st.plotly_chart(
        profile_charts.radar(scores, row[schema.PLAYER_NAME]),
        width="stretch",
        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False},
    )

    missing = scores.loc[~scores["enough"], "label"].tolist()
    if missing:
        st.caption("Too few events to place him on: " + ", ".join(missing) + ".")


def _shot_chart(row: pd.Series) -> None:
    """Where his shots come from, and how many of them go in."""
    st.markdown("**Shot chart**")
    st.caption(
        f"Accuracy by zone from {ZONE_MINIMUM} shots in that zone upwards, sized by "
        "how often he shoots there and shaded like the shot menu below, from the rim "
        "outwards. The corner marker sits outside the floor because the corner strip "
        "is three feet wide, and it is one figure for both corners in this data."
    )
    zones = player_profile.zone_accuracy(row)
    st.plotly_chart(
        profile_charts.shot_chart(zones, ZONE_MINIMUM), width="stretch", config=charts.STATIC
    )

    thin = zones.loc[zones["attempts"].fillna(0) < ZONE_MINIMUM, "zone"].tolist()
    if thin:
        st.caption(
            f"Fewer than {ZONE_MINIMUM} shots, so no percentage shown: " + ", ".join(thin) + "."
        )


def empty_state(shortlisted: int, pool: int) -> None:
    """What the profile area shows before a player has been opened."""
    st.subheader("Open a player", anchor=False)
    st.markdown(
        f"""
Click any line in the shortlist below to open his profile here, without leaving the page.

- **{shortlisted}** players match the criteria above.
- The profile crosses both files: what he shoots, and what he generates on a screen.
- Each half carries a button through to the board that ranks the league on it.
- Every standing on it is read against the **{pool}** players the scope bar at the
  top of the page leaves standing — the same pool the boards use.
"""
    )
