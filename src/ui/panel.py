"""The player card: three headline numbers, a plain sentence, and the shot menu."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import aggregate
from src.core.metrics import View
from src.core import ranking
from src.core.ranking import ELIGIBLE
from src.data import schema
from src.ui import charts, selection, theme
from src.ui import format as fmt


def card(row: pd.Series, view: View, population: pd.DataFrame) -> None:
    """Render the selected player's card for the view on screen."""
    heading, close = st.columns([5, 1], vertical_alignment="center")
    with heading:
        st.subheader(row[schema.PLAYER_NAME], anchor=False)
    with close:
        if st.button("Clear", width="stretch", help="Unload this player"):
            selection.clear()
            st.rerun()

    st.caption(
        f"{row[schema.TEAM_NAME]} · {int(row[schema.GAMES_PLAYED])} games · "
        f"{fmt.count(row[schema.ATTEMPTS])} field goal attempts · "
        f"mostly {row[schema.PRIMARY_ROLE]} in pick-and-roll"
    )

    if not row[ELIGIBLE]:
        taken = row[view.threshold.key]
        label = view.threshold.label.lower()
        st.warning(
            f"He took no {label} all season — nothing to judge here."
            if not taken or fmt.is_missing(taken)
            else f"Only {fmt.count(taken)} {label} all season — too few to judge him here.",
            icon=":material/info:",
        )

    sentence = fmt.summary(view.summary, row)
    if sentence:
        st.markdown(f"**{sentence}**")

    _headline(row, view, population)

    st.divider()
    st.markdown("**Shot menu**")
    st.caption("How his attempts break down, from the rim outwards")
    st.plotly_chart(charts.shot_menu(row), width="stretch", config=charts.STATIC)
    _menu_legend(row)

    st.divider()
    st.markdown("**Accuracy by zone**")
    st.caption("Bars run to 100%; the vertical line marks the league median for that zone")
    medians = aggregate.zone_medians(population[population[ELIGIBLE]])
    st.plotly_chart(charts.zone_accuracy(row, medians), width="stretch", config=charts.STATIC)


def _menu_legend(row: pd.Series) -> None:
    """Name the colours of the shot menu, with the count behind each slice.

    A swatch per zone: the bar above is a ramp running from the rim outwards, and
    without the key its shades name nothing.
    """
    from src.core import metrics

    palette = theme.palette()
    entries = []
    for zone, colour in zip(schema.SHOT_ZONES, palette.zones):
        share = row.get(zone.attempt_rate)
        if pd.isna(share) or share <= 0:
            continue
        entries.append(
            '<span style="display:inline-flex;align-items:center;gap:6px;'
            'margin:0 14px 4px 0;white-space:nowrap">'
            f'<span style="width:10px;height:10px;border-radius:2px;'
            f'background:{colour};flex:none"></span>'
            f"{zone.label} {fmt.value(metrics.PCT0, share)} "
            f"({fmt.count(row.get(zone.attempts))} shots)</span>"
        )

    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;font-size:0.82rem;opacity:0.75;'
        f'line-height:1.5">{"".join(entries)}</div>',
        unsafe_allow_html=True,
    )


def _headline(row: pd.Series, view: View, population: pd.DataFrame) -> None:
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
                lines.append(f"{fmt.count(row[column.sample])} shots")
            if not fmt.is_missing(place):
                lines.append(f"{fmt.ordinal(place)} percentile")
            st.caption(" · ".join(lines) if lines else " ")


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
Click a dot on the plot, or a row in the table, to load a player.

- **{eligible_count}** of {len(population)} players have enough shots for this view.
- Positions come from those {eligible_count} only — nobody is placed against a
  number that was never measured.
- The shot menu on every card breaks down his own attempts, so it holds for every
  player in the file whatever the minimum.
"""
    )
