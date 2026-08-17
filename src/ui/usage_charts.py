"""Figures for the admin page, drawn to the same rules as the rest of the app.

Static, no toolbar, colours out of `theme` only — an internal page is still part
of the product, and a reader moving to it should not feel he has left it.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from src.ui import theme
from src.ui.charts import _base_layout


def activity(frame: pd.DataFrame) -> go.Figure:
    """Screens looked at per day, with the sessions behind them on the hover."""
    palette = theme.palette()
    figure = go.Figure()
    figure.add_bar(
        x=frame["day"],
        y=frame["screens"],
        marker={"color": palette.accent},
        customdata=frame["sessions"],
        hovertemplate="<b>%{x}</b><br>%{y} screens<br>%{customdata} sessions<extra></extra>",
    )
    figure.update_layout(**_base_layout(palette, 240))
    figure.update_layout(margin={"l": 8, "r": 8, "t": 8, "b": 8}, bargap=0.35)
    figure.update_xaxes(showgrid=False, fixedrange=True, tickfont={"color": palette.ink_soft})
    figure.update_yaxes(
        gridcolor=theme.GRID, fixedrange=True, tickfont={"color": palette.ink_soft}
    )
    return figure


def ranked(labels: list[str], values: list[float], unit: str, height: int) -> go.Figure:
    """A horizontal bar per row, longest at the top.

    Horizontal because the labels are names — a view key or a player — and a name
    turned on its side is a name nobody reads.
    """
    palette = theme.palette()
    figure = go.Figure()
    figure.add_bar(
        x=values[::-1],
        y=labels[::-1],
        orientation="h",
        marker={"color": palette.accent},
        text=[f"{value:g}" for value in values[::-1]],
        textposition="outside",
        textfont={"color": palette.ink_soft, "size": 11},
        hovertemplate="<b>%{y}</b><br>%{x:g} " + unit + "<extra></extra>",
    )
    figure.update_layout(**_base_layout(palette, height))
    figure.update_layout(margin={"l": 8, "r": 40, "t": 8, "b": 8}, bargap=0.3)
    figure.update_xaxes(visible=False, fixedrange=True)
    figure.update_yaxes(
        fixedrange=True, tickfont={"color": palette.ink, "size": 11}, ticksuffix="  "
    )
    return figure


def funnel(frame: pd.DataFrame) -> go.Figure:
    """The three steps, each bar read against the first one.

    Not a percentage of the step above: what matters is how much of everybody who
    arrived got as far as opening a player, and stacking the ratios hides it.
    """
    palette = theme.palette()
    total = max(int(frame["sessions"].iloc[0]), 1)
    figure = go.Figure()
    figure.add_bar(
        x=[total] * len(frame),
        y=frame["step"][::-1],
        orientation="h",
        marker={"color": palette.track},
        hoverinfo="skip",
        showlegend=False,
    )
    figure.add_bar(
        x=frame["sessions"][::-1],
        y=frame["step"][::-1],
        orientation="h",
        marker={"color": palette.accent},
        text=[f"{value}  ({value / total:.0%})" for value in frame["sessions"][::-1]],
        textposition="inside",
        insidetextanchor="start",
        textfont={"color": palette.surface, "size": 12},
        hovertemplate="<b>%{y}</b><br>%{x} sessions<extra></extra>",
    )
    figure.update_layout(**_base_layout(palette, 170))
    figure.update_layout(
        margin={"l": 8, "r": 8, "t": 8, "b": 8}, barmode="overlay", bargap=0.35
    )
    figure.update_xaxes(visible=False, fixedrange=True)
    figure.update_yaxes(
        fixedrange=True, tickfont={"color": palette.ink, "size": 11}, ticksuffix="  "
    )
    return figure
