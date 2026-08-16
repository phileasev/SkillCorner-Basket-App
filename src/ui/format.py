"""Turning stored values into the strings the interface shows.

Ratios are stored on a 0-1 scale everywhere in the source files; the multiply by
one hundred happens here and nowhere else.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from src.core import catalogue, metrics

#: Printed wherever a value exists but is not backed by enough shots to show.
BLANK: str = "—"


def is_missing(value: Any) -> bool:
    """True for None, NaN and pandas' missing markers."""
    if value is None or value is pd.NA:
        return True
    return isinstance(value, float) and math.isnan(value)


def value(fmt: str, raw: Any) -> str:
    """Format a single value according to a catalogue format key."""
    if is_missing(raw):
        return BLANK
    if fmt == metrics.PCT1:
        return f"{raw * 100:.1f}%"
    if fmt == metrics.PCT0:
        return f"{raw * 100:.0f}%"
    if fmt == metrics.INT:
        return f"{round(raw):,}".replace(",", " ")
    if fmt == metrics.DEC1:
        return f"{raw:.1f}"
    return f"{raw:.2f}"


def column_value(column: str, raw: Any) -> str:
    """Format a value using the format the catalogue assigns to its column."""
    return value(catalogue.format_of(column), raw)


def summary(template: str, row: pd.Series) -> str:
    """Fill a view's plain-language summary with one player's numbers.

    Args:
        template: a sentence whose fields are raw column names.
        row: the player's row.

    Returns:
        The sentence, or an empty string when any number it needs is missing.
    """
    fields = {
        name: column_value(name, row.get(name))
        for name in _field_names(template)
    }
    if any(text == BLANK for text in fields.values()):
        return ""
    return template.format(**fields)


def _field_names(template: str) -> list[str]:
    from string import Formatter

    return [name for _, name, _, _ in Formatter().parse(template) if name]


def count(raw: Any) -> str:
    """Format a sample size, the count sitting behind a rate."""
    return value(metrics.INT, raw)


def percentile(raw: Any) -> str:
    """Format a 0-1 percentile as a whole number, blank when the player has none."""
    return BLANK if is_missing(raw) else f"{round(raw * 100)}"


def ordinal(raw: Any) -> str:
    """A percentile written the way a scouting report writes it: 87th."""
    if is_missing(raw):
        return BLANK
    value = round(raw * 100)
    if 11 <= value % 100 <= 13:
        return f"{value}th"
    return f"{value}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th') }"
