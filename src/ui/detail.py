"""The "see more" block: one player's whole offensive profile, opened in place.

Everything the two files hold about a player, on one screen and under his own row
— there is not enough on any single player to justify a page of his own.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import profile as player_profile
from src.core.metrics import DEC2, PCT0
from src.core.pick_views import HANDLER, SCREENER
from src.core.shot_views import SHOT_PROFILE
from src.data import schema
from src.ui import charts, profile_charts, selection
from src.ui import format as fmt

#: Shots a zone needs before its accuracy is printed on the court.
ZONE_MINIMUM: int = 20


def block(row: pd.Series, population: pd.DataFrame) -> None:
    """Render the full profile of one player."""
    heading, close = st.columns([5, 1], vertical_alignment="center")
    with heading:
        st.subheader(row[schema.PLAYER_NAME], anchor=False)
    with close:
        if st.button("Close", width="stretch", help="Close this profile"):
            selection.clear()
            st.rerun()

    role = row[schema.PRIMARY_ROLE]
    st.caption(
        f"{row[schema.TEAM_NAME]} · {int(row[schema.GAMES_PLAYED])} games · "
        f"{fmt.count(row[schema.ATTEMPTS])} shots · "
        f"{fmt.count(row[schema.total_picks(_prefix(role))])} picks as {role}"
    )

    left, right = st.columns(2, gap="medium")
    with left:
        _radar(row, population)
    with right:
        _shot_chart(row)

    st.divider()
    menus = st.columns(3, gap="medium")
    with menus[0]:
        st.markdown("**Shot menu**")
        st.caption("Share of his attempts, from the rim outwards")
        st.plotly_chart(
            charts.breakdown_bar(row, SHOT_PROFILE.breakdown),
            width="stretch",
            config=charts.STATIC,
        )
        _legend(row, SHOT_PROFILE.breakdown, PCT0)

    # Both roles are shown, not only his main one: a handful of picks in the other
    # role is itself worth seeing, and hiding it makes the card look incomplete.
    for column, lens, prefix in (
        (menus[1], HANDLER, schema.ROLE_HANDLER_PREFIX),
        (menus[2], SCREENER, schema.ROLE_SCREENER_PREFIX),
    ):
        with column:
            _spots(row, lens, prefix)


def _spots(row: pd.Series, lens, prefix: str) -> None:
    """Where one role's screens are set, or a line saying he played none."""
    picks = row.get(schema.total_picks(prefix))
    st.markdown(f"**Screens as {lens.label.lower()}**")
    if not picks or pd.isna(picks):
        st.caption("He was never involved in a screen in this role.")
        return

    st.caption(f"{fmt.count(picks)} picks, by spot on the floor")
    st.plotly_chart(
        charts.breakdown_bar(row, lens.profile.breakdown), width="stretch", config=charts.STATIC
    )
    _legend(row, lens.profile.breakdown, PCT0)


def _prefix(role: str) -> str:
    return (
        schema.ROLE_HANDLER_PREFIX if role == schema.ROLE_HANDLER else schema.ROLE_SCREENER_PREFIX
    )


def _radar(row: pd.Series, population: pd.DataFrame) -> None:
    """His standing on each axis, measured within that axis's own population."""
    st.markdown("**Offensive profile**")
    st.caption(
        "The web is drawn in percentiles: the outer ring is the best in the league, "
        "the centre the worst. Hover a spoke for his own figure. Both pick-and-roll "
        "roles are shown — a player who does a bit of each is not reduced to one."
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
        "Accuracy by zone, sized by how often he shoots there. The corner marker "
        "sits outside the floor because the corner strip is three feet wide, and it "
        "is one figure for both corners in this data."
    )
    zones = player_profile.zone_accuracy(row)
    st.plotly_chart(profile_charts.shot_chart(zones, ZONE_MINIMUM), width="stretch", config=charts.STATIC)

    thin = zones.loc[zones["attempts"].fillna(0) < ZONE_MINIMUM, "zone"].tolist()
    if thin:
        st.caption("Fewer than 20 shots, so no percentage shown: " + ", ".join(thin) + ".")


def _legend(row: pd.Series, segments: tuple, value_fmt: str) -> None:
    """Name the colours of a breakdown bar, with the count behind each slice."""
    from src.ui import theme

    palette = theme.palette()
    entries = []
    for segment, colour in zip(segments, palette.zones):
        share = row.get(segment.value)
        if pd.isna(share) or share <= 0:
            continue
        entries.append(
            '<span style="display:inline-flex;align-items:center;gap:6px;'
            'margin:0 12px 4px 0;white-space:nowrap">'
            f'<span style="width:10px;height:10px;border-radius:2px;'
            f'background:{colour};flex:none"></span>'
            f"{segment.label} {fmt.value(value_fmt, share)} "
            f"({fmt.count(row.get(segment.count))})</span>"
        )
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;font-size:0.8rem;opacity:0.75;'
        f'line-height:1.5">{"".join(entries)}</div>',
        unsafe_allow_html=True,
    )


def empty_state(shortlisted: int) -> None:
    """What the profile area shows before a player has been opened."""
    st.subheader("Open a player", anchor=False)
    st.markdown(
        f"""
Click any line in the shortlist below to open his profile here, without leaving the page.

- **{shortlisted}** players match the criteria above.
- The profile crosses both files: what he shoots, and what he generates on a screen.
- Every spoke of the profile is measured among the players who have enough events
  on that metric, so a small sample never inflates anybody's standing.
"""
    )
