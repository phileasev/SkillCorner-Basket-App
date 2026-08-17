"""Figures a card carries in more than one place, drawn once here.

The board card and the shortlist card show the same things about a player, and
were drifting apart one small edit at a time — two copies of the same legend
already. Whatever both draw lives here.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import aggregate
from src.core import profile as player_profile
from src.core.metrics import PCT0, Facet, Profile, Segment
from src.ui import charts, profile_charts, theme
from src.ui import format as fmt


def legend(row: pd.Series, segments: tuple[Segment, ...], value_fmt: str = PCT0) -> None:
    """Name the colours of a breakdown bar, with the count behind each slice.

    A swatch per segment: the bar above is a ramp, and without the key its shades
    name nothing. A slice he never had is left out rather than printed at zero.
    """
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


def spots_block(row: pd.Series, profile: Profile) -> None:
    """Where his screens are set and what each spot returns, on a floor plan.

    One figure where the card used to stack two — a hundred-percent bar of where,
    then bars of what each returned. They are one question asked twice, and asking
    it twice is most of why the card would not fit on a screen.
    """
    st.markdown(f"**{profile.breakdown_title}**")
    st.caption("Fill is his share of picks there, the figure on it his points per pick")
    st.plotly_chart(
        profile_charts.pick_court(player_profile.spot_returns(row, profile)),
        width="stretch",
        config=charts.STATIC,
    )
    _floors(row, profile.comparison, "spot")
    st.caption("Wings and step-ups are one figure for both sides of the floor.")


def coverage_block(row: pd.Series, facet: Facet, population: pd.DataFrame) -> None:
    """What the defence played against him, and what he returned against each.

    Two figures, because they answer two questions a scout asks together: the
    hundred-percent bar says what he is actually asked to solve, the bars under it
    say which of those he punishes. Reading either alone misleads — a fine number
    against the blitz is worth little if he sees the blitz twice a season, and the
    volume bar is what makes that visible without opening a second view.

    The two share one ramp and one order, so the shades key them to each other.
    Between them sits the key, which carries **the picks behind each coverage** —
    the same thing the shot menu prints under its own bar, and the reason nothing
    on this figure has to be withheld: a reader who can see that a coverage came up
    four times does not need to be protected from the number beside it.
    """
    st.markdown(f"**{facet.title}**")
    st.caption(facet.caption)

    if not _has_picks(row, facet):
        st.caption("He was never involved in a screen in this role.")
        return

    st.plotly_chart(
        charts.breakdown_bar(row, facet.breakdown), width="stretch", config=charts.STATIC
    )
    legend(row, facet.breakdown)
    st.caption("Points per pick against each below — the line is the league median")
    medians = aggregate.segment_medians(population, facet.comparison)
    st.plotly_chart(
        charts.comparison_bars(
            row, facet.comparison, medians, facet.comparison_fmt,
            facet.comparison_ceiling, ramp=True,
        ),
        width="stretch",
        config=charts.STATIC,
    )
    _floors(row, facet.comparison, "coverage")


def _has_picks(row: pd.Series, facet: Facet) -> bool:
    """Whether he ran a single screen in this role, whatever the coverage."""
    return any(
        pd.notna(row.get(segment.count)) and row.get(segment.count) > 0
        for segment in facet.comparison
    )


def _floors(row: pd.Series, segments: tuple[Segment, ...], slice_word: str) -> None:
    """State what each slice needed, and name the ones that fell short.

    A greyed bar says a number was withheld but not what it would have taken, so
    the figure is left explaining itself. Where the floor is one pick — the card's
    coverage figure, which withholds nothing — there is no bar to state, only the
    ones he never faced.
    """
    gated = [segment for segment in segments if segment.min_count > 0]
    if not gated:
        return

    floors = sorted({segment.min_count for segment in gated})
    common = max(floors)
    thin = [
        segment.label
        for segment in gated
        if not (
            pd.notna(row.get(segment.count)) and row.get(segment.count) >= segment.min_count
        )
    ]

    if common <= 1:
        st.caption(
            "He never faced: " + ", ".join(thin) + "."
            if thin
            else "Every one he faced is shown, however few times."
        )
        return

    line = f"Shown from {common} picks in that {slice_word} upwards"
    rare = [segment.label.lower() for segment in gated if segment.min_count < common]
    if rare:
        line += f", or {min(floors)} for {' and '.join(rare)}, rarely played in Spain"
    line += "." if not thin else ". Too few, so nothing is shown for: " + ", ".join(thin) + "."
    st.caption(line)
