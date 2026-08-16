"""The player card: headline figures, a plain sentence, and the lens profile.

The card is written against a lens's `Profile`, not against a particular file, so
the shooting page and the pick-and-roll page share it unchanged.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import aggregate, ranking
from src.core.metrics import PCT0, Lens, Profile, Segment, View
from src.core.ranking import ELIGIBLE
from src.data import schema
from src.ui import charts, selection, theme
from src.ui import format as fmt

#: Top of the scale the comparison bars are read against, per format.
_CEILINGS: dict[str, float] = {"pct1": 1.0, "pct0": 1.0, "dec2": 1.5, "dec1": 1.5}


def card(row: pd.Series, view: View, lens: Lens, population: pd.DataFrame) -> None:
    """Render the loaded player's card for the view on screen."""
    heading, close = st.columns([5, 1], vertical_alignment="center")
    with heading:
        st.subheader(row[schema.PLAYER_NAME], anchor=False)
    with close:
        if st.button("Clear", width="stretch", help="Unload this player"):
            selection.clear()
            st.rerun()

    st.caption(
        f"{row[schema.TEAM_NAME]} · {int(row[schema.GAMES_PLAYED])} games · "
        f"{fmt.count(row[view.threshold.key])} {view.threshold.label.lower()}"
    )

    if not row[ELIGIBLE]:
        taken = row[view.threshold.key]
        label = view.threshold.label.lower()
        st.warning(
            f"He saw no {label} all season — nothing to judge here."
            if not taken or fmt.is_missing(taken)
            else f"Only {fmt.count(taken)} {label} all season — too few to judge him here.",
            icon=":material/info:",
        )

    sentence = fmt.summary(view.summary, row)
    if sentence:
        st.markdown(f"**{sentence}**")

    _headline(row, view)

    if lens.profile is not None:
        _profile(row, lens.profile, population)


def _headline(row: pd.Series, view: View) -> None:
    """The view's headline figures, each with its sample size and its standing.

    The percentile is written the way a scouting report writes it. How many players
    it was measured against is stated once, above the table, rather than repeated
    on every tile.
    """
    columns = view.tile_columns

    for tile, column in zip(st.columns(len(columns)), columns):
        with tile:
            st.metric(column.label, fmt.value(column.fmt, row[column.key]))
            place = row.get(ranking.percentile_of(column.key))
            lines = []
            if column.sample:
                lines.append(f"{fmt.count(row[column.sample])} events")
            if not fmt.is_missing(place):
                lines.append(f"{fmt.ordinal(place)} percentile")
            st.caption(" · ".join(lines) if lines else " ")


def _profile(row: pd.Series, profile: Profile, population: pd.DataFrame) -> None:
    """The two figures every card carries: how he splits, and how he does per slice."""
    st.divider()
    st.markdown(f"**{profile.breakdown_title}**")
    st.caption(profile.breakdown_caption)
    st.plotly_chart(
        charts.breakdown_bar(row, profile.breakdown), width="stretch", config=charts.STATIC
    )
    _legend(row, profile.breakdown)

    st.divider()
    st.markdown(f"**{profile.comparison_title}**")
    st.caption(profile.comparison_caption)
    medians = aggregate.segment_medians(population[population[ELIGIBLE]], profile.comparison)
    st.plotly_chart(
        charts.comparison_bars(
            row,
            profile.comparison,
            medians,
            profile.comparison_fmt,
            _CEILINGS.get(profile.comparison_fmt, 1.0),
        ),
        width="stretch",
        config=charts.STATIC,
    )


def _legend(row: pd.Series, segments: tuple[Segment, ...]) -> None:
    """Name the colours of the breakdown, with the count behind each slice.

    A swatch per segment: the bar above is a ramp, and without the key its shades
    name nothing.
    """
    palette = theme.palette()
    entries = []
    for segment, colour in zip(segments, palette.zones):
        share = row.get(segment.value)
        if pd.isna(share) or share <= 0:
            continue
        entries.append(
            '<span style="display:inline-flex;align-items:center;gap:6px;'
            'margin:0 14px 4px 0;white-space:nowrap">'
            f'<span style="width:10px;height:10px;border-radius:2px;'
            f'background:{colour};flex:none"></span>'
            f"{segment.label} {fmt.value(PCT0, share)} "
            f"({fmt.count(row.get(segment.count))})</span>"
        )

    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;font-size:0.82rem;opacity:0.75;'
        f'line-height:1.5">{"".join(entries)}</div>',
        unsafe_allow_html=True,
    )


def empty_state(population: pd.DataFrame, view: View, out_of_scope: str | None = None) -> None:
    """What the panel shows when no player is loaded.

    Args:
        population: the players currently on screen.
        view: the view on screen.
        out_of_scope: a player who is still selected but whom the filters have
            pushed out of view, so his card vanishing is explained rather than
            silent. He comes back as soon as the filters let him through.
    """
    eligible_count = int(population[ELIGIBLE].sum())
    st.subheader("Reading this board", anchor=False)
    if out_of_scope:
        st.info(
            f"**{out_of_scope}** is still loaded, but the filters above leave him out. "
            "Widen them and his card comes back.",
            icon=":material/filter_alt:",
        )
    st.markdown(
        f"""
Click a dot on the plot, or any line in the table, to load a player.

- **{eligible_count}** of {len(population)} players clear the minimum on this view.
- Percentiles come from those {eligible_count} only — nobody is placed against a
  number that was never measured.
- The breakdown on every card is a share of his own events, so it holds for every
  player in the file whatever the minimum.
"""
    )
