"""Figures for one player's profile: his standing on each axis, and his shot chart.

Kept apart from the board figures because they answer a different question — not
"where does he sit among everyone" but "what does this one player look like".
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go

from src.ui import theme
from src.ui import format as fmt
from src.ui.charts import STATIC, _base_layout  # noqa: F401  (STATIC is re-exported)

def radar(scores: pd.DataFrame, name: str) -> go.Figure:  # noqa: D401
    """One player's place on each spoke, as a percentile among that spoke's pool.

    Percentiles rather than raw values: points per pick and a three-point rate do
    not share a scale, and drawing them on one would say nothing. A spoke the
    player has too few events for is left empty rather than drawn at zero, which
    would read as a weakness he has not shown.
    """
    palette = theme.palette()
    placed = scores.copy()
    # A spoke he has too few events for is drawn at zero rather than left out: an
    # open web reads as a broken chart. The caption under it names the spokes that
    # were not measured, so nobody mistakes the shape for a weakness.
    placed["plot"] = [
        0.0 if pd.isna(value) else float(value) * 100 for value in placed["percentile"]
    ]

    hover = [
        [
            fmt.value(shape, value),
            fmt.ordinal(place) + " percentile" if not pd.isna(place) else "too few events",
        ]
        for shape, value, place in zip(placed["fmt"], placed["value"], placed["percentile"])
    ]

    figure = go.Figure()
    figure.add_scatterpolar(
        r=[*placed["plot"], placed["plot"].iloc[0]],
        theta=[*placed["label"], placed["label"].iloc[0]],
        mode="lines+markers",
        fill="toself",
        connectgaps=False,
        line={"color": palette.accent, "width": 2},
        marker={"size": 7, "color": palette.accent},
        fillcolor=palette.selected,
        name=name,
        customdata=[*hover, hover[0]],
        hovertemplate=(
            "<b>%{theta}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>"
        ),
    )

    figure.update_layout(**_base_layout(palette, 380))
    # The angular labels sit outside the plotting circle; the board margins are too
    # tight for them and the top spoke was being cut off.
    figure.update_layout(margin={"l": 70, "r": 70, "t": 46, "b": 40})
    figure.update_polars(
        bgcolor=theme.TRANSPARENT,
        radialaxis={
            "range": [0, 100],
            "showticklabels": False,
            "gridcolor": theme.GRID,
            "linecolor": theme.GRID,
            "ticks": "",
        },
        angularaxis={
            "gridcolor": theme.GRID,
            "linecolor": theme.GRID,
            "tickfont": {"size": 10.5, "color": palette.ink_soft},
        },
    )
    return figure


#: Half court in feet, the way the NBA zone columns describe it.
_COURT = {"width": 50.0, "length": 40.0, "basket": (25.0, 5.25), "arc": 23.75, "corner_x": 3.0}

#: Where each zone's marker sits. Corner threes are one number for both sides, so
#: the marker is placed on one and the label says so.
#:
#: The corner strip is three feet wide, which no readable marker fits inside, so
#: its marker is parked just outside the sideline rather than drawn over the
#: mid-range: sitting at x=6 it looked like a mid-range shot, and its circle spilled
#: over the line. The plot leaves room on both sides for it.
_ZONE_SPOTS: dict[str, tuple[float, float]] = {
    "Restricted area": (25.0, 5.5),
    "Paint (non-RA)": (25.0, 14.0),
    "Mid-range": (25.0, 23.5),
    "Corner 3": (-4.5, 7.0),
    "Above the break 3": (25.0, 33.5),
}

#: Marker diameters in pixels, from the rarest zone to the busiest.
_SMALLEST: float = 15.0
_LARGEST: float = 42.0


def _court_lines() -> list[go.Scatter]:
    """The few lines that make the markers read as a basketball floor."""
    basket_x, basket_y = _COURT["basket"]
    lines = []

    def line(xs, ys, width=1.0):
        return go.Scatter(
            x=xs, y=ys, mode="lines", hoverinfo="skip", showlegend=False,
            line={"color": theme.GRID, "width": width},
        )

    lines.append(line([0, 0, 50, 50, 0], [0, 40, 40, 0, 0]))
    lines.append(line([17, 17, 33, 33], [0, 19, 19, 0]))
    lines.append(line([22, 28], [4, 4], 1.6))

    corner = _COURT["corner_x"]
    angles = [math.radians(a) for a in range(0, 181)]
    arc_x = [basket_x + _COURT["arc"] * math.cos(a) for a in angles]
    arc_y = [basket_y + _COURT["arc"] * math.sin(a) for a in angles]
    inside = [(x, y) for x, y in zip(arc_x, arc_y) if corner <= x <= 50 - corner]
    lines.append(line([corner, inside[-1][0]], [0, inside[-1][1]]))
    lines.append(line([50 - corner, inside[0][0]], [0, inside[0][1]]))
    lines.append(line([x for x, _ in inside], [y for _, y in inside]))

    rim = [math.radians(a) for a in range(0, 361)]
    lines.append(line([basket_x + 0.75 * math.cos(a) for a in rim],
                      [basket_y + 0.75 * math.sin(a) for a in rim], 1.4))
    return lines


def shot_chart(zones: pd.DataFrame, minimum: int) -> go.Figure:
    """Accuracy per zone on a half court, sized by how often he shoots there."""
    palette = theme.palette()
    figure = go.Figure()
    for trace in _court_lines():
        figure.add_trace(trace)

    enough = zones["attempts"].fillna(0) >= minimum
    biggest = max(float(zones["attempts"].fillna(0).max()), 1.0)

    figure.add_scatter(
        x=[-1.5, 1.5], y=[7.0, 7.0], mode="lines", hoverinfo="skip", showlegend=False,
        line={"color": theme.GRID, "width": 1},
    )
    figure.add_scatter(
        x=[_ZONE_SPOTS[zone][0] for zone in zones["zone"]],
        y=[_ZONE_SPOTS[zone][1] for zone in zones["zone"]],
        mode="markers+text",
        marker={
            "size": [
                _SMALLEST + (_LARGEST - _SMALLEST) * (float(a or 0) / biggest) ** 0.5
                for a in zones["attempts"]
            ],
            "color": [
                palette.accent if ok else palette.muted for ok in enough
            ],
            "opacity": 0.85,
            "line": {"width": 2, "color": palette.surface},
        },
        text=[
            fmt.value("pct0", accuracy) if ok else fmt.BLANK
            for accuracy, ok in zip(zones["accuracy"], enough)
        ],
        textposition="middle center",
        textfont={"color": palette.surface, "size": 11, "family": "system-ui"},
        customdata=[
            [zone, fmt.count(attempts), fmt.value("pct1", accuracy)]
            for zone, attempts, accuracy in zip(
                zones["zone"], zones["attempts"], zones["accuracy"]
            )
        ],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} shots<br>%{customdata[2]}<extra></extra>",
        showlegend=False,
    )

    figure.update_layout(**_base_layout(palette, 330))
    # Room on both sides for the corner marker, and above the arc for its label.
    figure.update_xaxes(visible=False, range=[-9, 59], fixedrange=True)
    figure.update_yaxes(
        visible=False, range=[-2, 42], fixedrange=True, scaleanchor="x", scaleratio=1
    )
    return figure
