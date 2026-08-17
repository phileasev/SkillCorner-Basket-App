"""The player card: headline figures, a plain sentence, and the lens profile.

The card is written against a lens's `Profile`, not against a particular file, so
the shooting page and the pick-and-roll page share it unchanged.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import streamlit as st

from src.core import aggregate, catalogue, ranking
from src.core.metrics import Lens, Profile, Segment, View
from src.core.ranking import ELIGIBLE
from src.data import schema
from src.ui import charts, facets, filters, selection
from src.ui import format as fmt

#: Top of the scale the comparison bars are read against, per format.
_CEILINGS: dict[str, float] = {"pct1": 1.0, "pct0": 1.0, "dec2": 1.5, "dec1": 1.5}


def card(
    row: pd.Series, view: View, lens: Lens, population: pd.DataFrame, minimum: int
) -> None:
    """Render the loaded player's card for the view on screen.

    Args:
        row: the loaded player.
        view: the view on screen.
        lens: the lens that view belongs to, for its profile figures.
        population: the scope bar's league, for the median lines. The same pool the
            percentiles are read against, so the card's two references agree.
        minimum: the count the reader set in the panel. The per-slice figures are
            held to it as well, so the card carries one number rather than its own.
    """
    heading, close = st.columns([5, 1], vertical_alignment="center")
    with heading:
        st.subheader(row[schema.PLAYER_NAME], anchor=False)
    with close:
        if st.button("Clear", width="stretch", help="Unload this player"):
            selection.clear()
            st.rerun()

    st.caption(
        f"{row[schema.TEAM_NAME]} · {int(row[schema.GAMES_PLAYED])} games · "
        f"{fmt.count(row[view.threshold.key])} {view.threshold.events}"
    )

    if not row[ELIGIBLE]:
        taken = row[view.threshold.key]
        events = view.threshold.events
        # Saying only "too few" leaves the reader thinking the app has decided
        # against the player. It is his own bar that put him there, so the way back
        # is named — and named as the panel is titled, so it can be found.
        st.warning(
            f"He saw no {events} all season — nothing to judge here."
            if not taken or fmt.is_missing(taken)
            else (
                f"Only {fmt.count(taken)} {events} all season — too few to judge him "
                f"at the bar you set. Lower it under **{filters.minimum_title(view)}** "
                "above and he is measured with everyone else."
            ),
            icon=":material/info:",
        )

    sentence = fmt.summary(view.summary, row)
    if sentence:
        st.markdown(f"**{sentence}**")

    _headline(row, view)

    if lens.profile is not None:
        _profile(row, lens.profile, population, minimum)


def _headline(row: pd.Series, view: View) -> None:
    """The view's headline figures, each with its sample size and its standing.

    The percentile is written the way a scouting report writes it. How many players
    it was measured against is stated once, above the table, rather than repeated
    on every tile.
    """
    columns = view.tile_columns

    # Two abreast, not four. The card is the narrow side of the board and the
    # glossary names are long: `Ball Handler - Assist Opportunity Rate` in a quarter
    # of that column wrapped onto five lines, and four of those filled the screen
    # before a single figure had been drawn.
    for start in range(0, len(columns), 2):
        for tile, column in zip(st.columns(2), columns[start : start + 2]):
            with tile:
                st.metric(
                    catalogue.short(view, column.label),
                    fmt.value(column.fmt, row[column.key]),
                )
                place = row.get(ranking.percentile_of(column.key))
                lines = []
                if column.sample:
                    # The sample size carries its own standing. Six hundred picks
                    # means nothing on its own — that it is more than all but four
                    # per cent of the league is the fact a scout wanted.
                    volume = row.get(ranking.percentile_of(column.sample))
                    events = f"{fmt.count(row[column.sample])} events"
                    if not fmt.is_missing(volume):
                        events += f" ({fmt.ordinal(volume)})"
                    lines.append(events)
                if not fmt.is_missing(place):
                    lines.append(f"{fmt.ordinal(place)} percentile")
                st.caption(" · ".join(lines) if lines else " ")


def _profile(
    row: pd.Series, profile: Profile, population: pd.DataFrame, minimum: int
) -> None:
    """The two figures every card carries: how he splits, and how he does per slice.

    The per-slice figures are held to the minimum the reader set in the panel, not
    to a floor of their own. Two numbers on one screen — a panel asking for 35 shots
    above a chart quietly asking for 20 — is a question the reader cannot answer,
    and the one he set is the one he means. Never below one attempt, or a zone he
    never shot in would be printed as a percentage of nothing.
    """
    floor = max(int(minimum), 1)
    profile = replace(
        profile,
        comparison=tuple(
            replace(segment, min_count=floor) for segment in profile.comparison
        ),
    )

    st.divider()
    # Spots on the floor collapse onto one plan of it. Stacked, the where and the
    # what-it-returned ran to two figures and four captions on a card that then had
    # a third block under it — the pick-and-roll card no longer fitted a screen.
    if profile.on_court:
        facets.spots_block(row, profile)
    else:
        _split_figures(row, profile, population)

    if profile.coverage is not None:
        st.divider()
        facets.coverage_block(row, profile.coverage, population)


def _split_figures(row: pd.Series, profile: Profile, population: pd.DataFrame) -> None:
    """How his events split, then what each slice returned — one figure each."""
    st.markdown(f"**{profile.breakdown_title}**")
    st.caption(profile.breakdown_caption)
    st.plotly_chart(
        charts.breakdown_bar(row, profile.breakdown), width="stretch", config=charts.STATIC
    )
    facets.legend(row, profile.breakdown)

    st.divider()
    st.markdown(f"**{profile.comparison_title}**")
    st.caption(profile.comparison_caption)
    medians = aggregate.segment_medians(population, profile.comparison)
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
    _thin_segments(row, profile.comparison)


def _thin_segments(row: pd.Series, segments: tuple[Segment, ...]) -> None:
    """Say which slices were left blank, and how many events it would have taken.

    The figure greys a bar it cannot support without saying so, which left the
    reader guessing whether a missing number meant "not measured" or "zero". The
    floor is stated whether or not he falls under it, so it is knowable from the
    card rather than only when he happens to fail it — and named as the reader's
    own choice, since that is where it now comes from.
    """
    gated = [segment for segment in segments if segment.min_count > 0]
    if not gated:
        return

    floor = gated[0].min_count
    thin = [
        segment.label
        for segment in gated
        if not (pd.notna(row.get(segment.count)) and row.get(segment.count) >= floor)
    ]

    events = "pick" if "picks" in gated[0].count else "shot"
    line = f"Measured from {floor} {events}{'' if floor == 1 else 's'} upwards, as set above."
    if thin:
        line += " Too few, so nothing is shown for: " + ", ".join(thin) + "."
    st.caption(line)


def empty_state(
    population: pd.DataFrame,
    pool: pd.DataFrame,
    view: View,
    out_of_scope: str | None = None,
) -> None:
    """What the panel shows when no player is loaded.

    Args:
        population: the players currently on screen.
        pool: the scope bar's league, which every percentile is read against.
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
  Below it a player keeps his numbers and his standing; his row is greyed and held
  at the bottom, which is what says the sample is thin.
- Percentiles come from the **{len(pool)}** players the bar at the top of the page
  leaves standing — the same pool on every page, so a standing means the same thing
  wherever it is read.
- The breakdown on every card is a share of his own events, so it holds for every
  player in the file whatever the minimum.
"""
    )
