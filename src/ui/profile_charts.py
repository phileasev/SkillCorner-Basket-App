"""Figures for one player's profile: his standing on each axis, and his shot chart.

Kept apart from the board figures because they answer a different question — not
"where does he sit among everyone" but "what does this one player look like".
"""

from __future__ import annotations

import math
import textwrap

import pandas as pd
import plotly.graph_objects as go

from src.data import schema
from src.ui import theme
from src.ui import format as fmt
from src.ui.charts import _base_layout


#: Characters a spoke line may run to before it is folded.
_SPOKE_WIDTH: int = 18

#: The ring drawn under the shape, on the 0-100 percentile scale. Half the league
#: is inside it and half outside, which is the only reference a web needs.
MEDIAN_RING: float = 50.0


def _wrapped(label: str) -> str:
    """Fold a glossary name over a few lines, so ten spokes fit round one web.

    `Ball Handler - Assist Opportunity Rate` is thirty-seven characters, and end
    to end the spokes would run into each other. The name is never shortened —
    keeping the dictionary's own wording is the point — it is only broken, first
    where the dictionary itself puts a separator and then between words.
    """
    lines: list[str] = []
    for part in label.replace(" - ", " -\n").split("\n"):
        lines.extend(textwrap.wrap(part, _SPOKE_WIDTH) or [part])
    return "<br>".join(lines)


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
    placed["spoke"] = [_wrapped(label) for label in placed["label"]]

    # The name travels in the hover data rather than being read off the spoke:
    # the spoke is folded over several lines, and the tooltip wants it whole.
    hover = [
        [
            label,
            fmt.value(shape, value),
            fmt.ordinal(place) + " percentile" if not pd.isna(place) else "too few events",
        ]
        for label, shape, value, place in zip(
            placed["label"], placed["fmt"], placed["value"], placed["percentile"]
        )
    ]

    figure = go.Figure()
    # The halfway ring, drawn under him: a shape on a web says nothing without a
    # line to read it against, and the fiftieth percentile is the one every reader
    # already has in mind — inside it is below the league, outside it above.
    spokes = [*placed["spoke"], placed["spoke"].iloc[0]]
    figure.add_scatterpolar(
        r=[MEDIAN_RING] * len(spokes),
        theta=spokes,
        mode="lines",
        line={"color": palette.muted, "width": 1, "dash": "dot"},
        hoverinfo="skip",
        showlegend=False,
    )
    figure.add_scatterpolar(
        r=[*placed["plot"], placed["plot"].iloc[0]],
        theta=[*placed["spoke"], placed["spoke"].iloc[0]],
        mode="lines+markers",
        fill="toself",
        connectgaps=False,
        line={"color": palette.accent, "width": 2},
        marker={"size": 7, "color": palette.accent},
        fillcolor=palette.selected,
        name=name,
        customdata=[*hover, hover[0]],
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>"
        ),
    )

    figure.update_layout(**_base_layout(palette, 420))
    # The angular labels sit outside the plotting circle; the board margins are too
    # tight for them and the top spoke was being cut off. They now run to three
    # lines, so the room left for them is wider still.
    figure.update_layout(margin={"l": 96, "r": 96, "t": 58, "b": 54})
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

#: Which tone of the breakdown ramp each zone takes. The shot menu sits directly
#: under this chart on the same card, and both are ordered by distance from the
#: basket — so a zone is given the shade its distance already has down there: the
#: rim is the palest mark and the palest slice, the threes the deepest of each.
#: The menu's single three-point band splits in two here, corner and above the
#: break, which is what the fifth tone at the dark end of the ramp is for.
_ZONE_TONE: dict[str, int] = {
    zone.label: index for index, zone in enumerate(schema.NBA_ZONES)
}


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


#: Where each screen spot sits on the same half court the shot chart uses. Wings
#: and step-ups are one figure for both sides of the floor in this data, so both
#: sides are drawn and both carry that figure — colouring one side only would read
#: as a player who never screens on the left.
_SPOT_BOXES: dict[str, tuple[tuple[float, float, float, float], ...]] = {
    "Middle": ((18.0, 28.5, 32.0, 39.0),),
    "Wing": ((2.5, 23.0, 16.5, 35.5), (33.5, 23.0, 47.5, 35.5)),
    "Step-up": ((0.5, 8.5, 12.0, 21.0), (38.0, 8.5, 49.5, 21.0)),
}


def pick_court(spots: pd.DataFrame) -> go.Figure:
    """Where his screens are set and what each spot returns, on one floor plan.

    Fill says how much of his pick load a spot carries, the figure on it says what
    that load produced. A spot too thin to judge is greyed and its number withheld,
    the same language the rest of the app uses for a sample it will not print.
    """
    palette = theme.palette()
    figure = go.Figure()
    for trace in _court_lines():
        figure.add_trace(trace)

    busiest = max(float(spots["share"].fillna(0).max()), 0.01)

    for entry in spots.itertuples():
        share = 0.0 if pd.isna(entry.share) else float(entry.share)
        # Read against his own busiest spot rather than an absolute scale: three
        # zones splitting one player's picks never reach the top of a 0-100 ramp,
        # and the question is which of the three he uses, not how big the share is.
        fill = 0.16 + 0.62 * (share / busiest)
        text = (
            f"<b>{fmt.value('dec2', entry.ppp) if entry.enough else fmt.BLANK}</b><br>"
            f"<span style='font-size:9.5px'>{fmt.value('pct0', entry.share)} · "
            f"{fmt.count(entry.picks)} picks</span>"
        )
        for x0, y0, x1, y1 in _SPOT_BOXES.get(entry.spot, ()):
            figure.add_shape(
                type="rect", x0=x0, y0=y0, x1=x1, y1=y1, layer="below",
                fillcolor=palette.accent if entry.enough else palette.muted,
                opacity=fill, line={"width": 0},
            )
            figure.add_annotation(
                x=(x0 + x1) / 2, y=(y0 + y1) / 2, text=text, showarrow=False,
                font={"color": palette.ink, "size": 13}, align="center",
            )

    figure.update_layout(**_base_layout(palette, 250))
    figure.update_layout(margin={"l": 2, "r": 2, "t": 2, "b": 2})
    figure.update_xaxes(visible=False, range=[-1, 51], fixedrange=True)
    figure.update_yaxes(
        visible=False, range=[-1, 41], fixedrange=True, scaleanchor="x", scaleratio=1
    )
    return figure


def shot_chart(zones: pd.DataFrame, minimum: int) -> go.Figure:
    """Accuracy per zone on a half court, sized by how often he shoots there.

    Each mark carries the shade the shot menu below gives the same distance, so a
    reader moving between the two figures does not have to re-learn the colours.
    A zone with too few shots keeps the muted grey the rest of the app uses for a
    sample it will not print, which stays the one thing colour says here.
    """
    palette = theme.palette()
    figure = go.Figure()
    for trace in _court_lines():
        figure.add_trace(trace)

    enough = zones["attempts"].fillna(0) >= minimum
    biggest = max(float(zones["attempts"].fillna(0).max()), 1.0)

    fills = [
        palette.zones[_ZONE_TONE.get(zone, 0) % len(palette.zones)] if ok else palette.muted
        for zone, ok in zip(zones["zone"], enough)
    ]

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
            "color": fills,
            # Drawn at full strength: a mark softened to 85% is no longer the tone
            # the menu prints for that zone, which is the whole point of the ramp.
            "line": {"width": 2, "color": palette.surface},
        },
        text=[
            fmt.value("pct0", accuracy) if ok else fmt.BLANK
            for accuracy, ok in zip(zones["accuracy"], enough)
        ],
        textposition="middle center",
        # The label sits on the mark, so it is read against the fill rather than
        # against the page: one ink for the pale rim tone and the deep three tone
        # would leave one of the two unreadable.
        textfont={
            "color": [theme.ink_on(fill) for fill in fills],
            "size": 11,
            "family": "system-ui",
        },
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
