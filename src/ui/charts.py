"""Plotly figure factories. Layout and colour only — no filtering, no maths.

Every figure is fixed: no zoom, no pan, no drag. A scout reads these, he does not
navigate them, and a chart that moves under the cursor reads as unfinished.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.core import metrics
from src.core.metrics import View
from src.core.ranking import ELIGIBLE
from src.data import schema
from src.ui import format as fmt
from src.ui import theme

_AXIS_TICK = {"pct1": ".0%", "pct0": ".0%", "int": ",d", "dec1": ".1f", "dec2": ".2f"}

#: Passed to `st.plotly_chart` for the charts that carry no click behaviour.
STATIC: dict[str, object] = {"staticPlot": True, "displayModeBar": False}

#: Passed to the scatter, which stays clickable but never zooms or pans.
CLICKABLE: dict[str, object] = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
}


def _base_layout(palette: theme.Palette, height: int) -> dict:
    return {
        "height": height,
        "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
        "paper_bgcolor": theme.TRANSPARENT,
        "plot_bgcolor": theme.TRANSPARENT,
        "font": {"color": palette.ink_soft, "size": 11},
        "hoverlabel": {"bgcolor": palette.surface, "font": {"color": palette.ink, "size": 12}},
        "showlegend": False,
        "dragmode": False,
    }


def _hover_lines(rows: pd.DataFrame, view: View) -> list[str]:
    return [
        f"<b>{row[schema.PLAYER_NAME]}</b><br>{row[schema.TEAM_NAME]}"
        f" · {int(row[schema.GAMES_PLAYED])} games<br>"
        f"{view.x.label}: {fmt.value(view.x.fmt, row[view.x.key])}<br>"
        f"{view.y.label}: {fmt.value(view.y.fmt, row[view.y.key])}<br>"
        f"{view.threshold.label}: {fmt.count(row[view.threshold.key])}"
        for _, row in rows.iterrows()
    ]


def scatter(frame: pd.DataFrame, view: View, selected: str | None) -> go.Figure:
    """Plot the view's two axes, splitting players by whether they clear the minimum.

    Median crosshairs are drawn from the eligible players only, so the reference
    lines are not dragged around by small-sample noise.
    """
    palette = theme.palette()
    figure = go.Figure()

    eligible = frame[frame[ELIGIBLE]]
    ineligible = frame[~frame[ELIGIBLE]]

    if not ineligible.empty:
        figure.add_scatter(
            x=ineligible[view.x.key],
            y=ineligible[view.y.key],
            mode="markers",
            marker={"size": 6, "color": palette.muted, "opacity": 0.5},
            text=_hover_lines(ineligible, view),
            customdata=ineligible[[schema.PLAYER_NAME]].values,
            hovertemplate="%{text}<extra>Below the minimum</extra>",
            name="Below the minimum",
        )

    if not eligible.empty:
        figure.add_scatter(
            x=eligible[view.x.key],
            y=eligible[view.y.key],
            mode="markers",
            marker={
                "size": 9,
                "color": palette.accent,
                "opacity": 0.78,
                "line": {"width": 1.5, "color": palette.surface},
            },
            text=_hover_lines(eligible, view),
            customdata=eligible[[schema.PLAYER_NAME]].values,
            hovertemplate="%{text}<extra></extra>",
            name="Enough shots to judge",
        )

        for value, axis in (
            (eligible[view.x.key].median(), "x"),
            (eligible[view.y.key].median(), "y"),
        ):
            if pd.notna(value):
                line = {"color": palette.rule, "width": 1}
                figure.add_vline(x=value, line=line) if axis == "x" else figure.add_hline(
                    y=value, line=line
                )

        for text, x_pos, anchor in (
            (view.quadrants[0], 0.995, "right"),
            (view.quadrants[1], 0.005, "left"),
        ):
            figure.add_annotation(
                xref="paper", yref="paper", x=x_pos, y=1.02, showarrow=False,
                text=text.upper(), font={"size": 9.5, "color": palette.muted}, xanchor=anchor,
            )

    if selected is not None:
        picked = frame[frame[schema.PLAYER_NAME] == selected]
        if not picked.empty:
            figure.add_scatter(
                x=picked[view.x.key],
                y=picked[view.y.key],
                mode="markers+text",
                marker={
                    "size": 14,
                    "color": palette.ink,
                    "line": {"width": 2, "color": palette.surface},
                },
                text=picked[schema.PLAYER_NAME],
                textposition="middle right",
                textfont={"color": palette.ink, "size": 11},
                customdata=picked[[schema.PLAYER_NAME]].values,
                hoverinfo="skip",
                name="Selected",
            )

    axis_style = {
        "showgrid": True,
        "gridcolor": theme.GRID,
        "gridwidth": 1,
        "zeroline": False,
        "linecolor": theme.GRID,
        "ticks": "",
        "fixedrange": True,
        "title_font": {"size": 11.5, "color": palette.ink_soft},
    }
    figure.update_layout(**_base_layout(palette, 400))
    figure.update_xaxes(title_text=view.x.label, tickformat=_AXIS_TICK[view.x.fmt], **axis_style)
    figure.update_yaxes(title_text=view.y.label, tickformat=_AXIS_TICK[view.y.fmt], **axis_style)
    return figure


def shot_menu(row: pd.Series) -> go.Figure:
    """Horizontal breakdown of where one player's attempts come from."""
    palette = theme.palette()
    figure = go.Figure()

    for zone, colour in zip(schema.SHOT_ZONES, palette.zones):
        share = row.get(zone.attempt_rate)
        if pd.isna(share) or share <= 0:
            continue
        figure.add_bar(
            x=[share],
            y=["menu"],
            orientation="h",
            marker={"color": colour, "line": {"width": 2, "color": palette.surface}},
            name=zone.label,
            hoverinfo="skip",
        )

    figure.update_layout(**_base_layout(palette, 44), barmode="stack", bargap=0)
    figure.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
    figure.update_yaxes(visible=False, fixedrange=True)
    return figure


def zone_accuracy(row: pd.Series, medians: dict[str, float | None]) -> go.Figure:
    """One player's accuracy per zone, against the league median for each zone."""
    palette = theme.palette()
    figure = go.Figure()

    labels, values, colours, texts = [], [], [], []
    for zone in schema.SHOT_ZONES:
        attempts = row.get(zone.attempts)
        enough = pd.notna(attempts) and attempts >= schema.ZONE_MIN_ATTEMPTS
        accuracy = row.get(zone.made_pct)
        labels.append(zone.label)
        values.append(0.0 if not enough or pd.isna(accuracy) else float(accuracy))
        colours.append(palette.accent if enough else palette.muted)
        texts.append(fmt.value(metrics.PCT1, accuracy) if enough else fmt.BLANK)

    # A full-width track behind every bar, so each one is read against the same
    # 100% frame instead of against whichever zone happens to be the longest.
    figure.add_bar(
        x=[1.0] * len(labels),
        y=labels,
        orientation="h",
        marker={"color": palette.track, "line": {"width": 1, "color": palette.rule}},
        hoverinfo="skip",
        width=0.5,
        showlegend=False,
    )
    figure.add_bar(
        x=values,
        y=labels,
        orientation="h",
        marker={"color": colours},
        hoverinfo="skip",
        width=0.5,
    )

    # Values are parked against the right edge of the track rather than trailing
    # their own bar: they line up in one column and none of them can be clipped by
    # the 100% frame.
    for index, text in enumerate(texts):
        figure.add_annotation(
            x=1.0, y=index, xanchor="right", xshift=-6, showarrow=False, text=text,
            font={"color": palette.ink_soft, "size": 11},
        )

    for index, zone in enumerate(schema.SHOT_ZONES):
        median = medians.get(zone.made_pct)
        if median is not None:
            figure.add_shape(
                type="line",
                x0=median, x1=median, y0=index - 0.34, y1=index + 0.34,
                line={"color": palette.rule, "width": 2},
            )

    figure.update_layout(**_base_layout(palette, 190), barmode="overlay")
    figure.update_xaxes(visible=False, range=[0, 1.0], fixedrange=True)
    figure.update_yaxes(
        autorange="reversed",
        showgrid=False,
        linecolor=theme.TRANSPARENT,
        fixedrange=True,
        tickfont={"size": 11, "color": palette.ink_soft},
    )
    return figure
