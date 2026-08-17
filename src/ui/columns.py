"""Which columns the shortlist carries, which of them open, and how they are gated.

The table holds every metric the app knows; `opening_columns` decides which of
them are on screen when the page loads. Streamlit's own column menu, in the
table's toolbar, brings back any of the others — so choosing columns happens on
the table itself, and the export always carries the lot.
"""

from __future__ import annotations

from functools import cache

import pandas as pd
import streamlit as st

from src.core import catalogue, metrics, ranking, shortlist
from src.core.shortlist import Criterion, Filterable
from src.data import glossary, schema

PLAYER: str = "Player"
TEAM: str = "Team"
#: Games played is a criterion like any other, so the column has to answer to the
#: name the selector offers it under. Player and team are named nowhere else.
GAMES: str = glossary.name(schema.GAMES_PLAYED)
PERCENTILE: str = "percentile"

#: Always on screen, ahead of whatever the criteria bring.
_ANCHOR: tuple[str, ...] = (PLAYER, TEAM, GAMES)

#: Opened on screen when no criterion names anything else.
_DEFAULTS: tuple[str, ...] = (
    schema.ATTEMPTS,
    schema.EFG,
    schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp"),
    schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp"),
)

#: Carried by the table on their own, ahead of every metric — never a second time.
_IDENTITY: tuple[str, ...] = (schema.PLAYER_NAME, schema.TEAM_NAME, schema.GAMES_PLAYED)


def count_name(denominator: str) -> str:
    """The count, named the way the data dictionary names it.

    Plain `Attempts` used to say nothing next to a dozen other counts, which is
    why it was renamed here. It no longer needs to be: every other count now
    carries the split the glossary gives it — `Contested - Attempts`, `3PT
    Attempts`, `Ball Handler - Picks` — so the bare one is the whole-season one.
    """
    return glossary.name(denominator)


def _header(option: Filterable, repeated: set[str]) -> str:
    """A column header, prefixed by its lens if two columns ever shared a name.

    Points per pick exists for both roles, and one header cannot stand for two
    columns: the second would quietly overwrite the first, in the table and in
    the export alike. The glossary separates them itself — `Ball Handler -` and
    `Screener -` — so this is a guard, not a routine.
    """
    return f"{option.group} · {option.label}" if option.label in repeated else option.label


@cache
def catalogue_columns() -> tuple[tuple[str, str, str], ...]:
    """`(header, column, format)` for every metric the app knows, counts included."""
    described = [
        shortlist.describe(column)
        for option in shortlist.options()
        for _, column in option.variants
    ]
    labels = [option.label for option in described]
    repeated = {label for label in labels if labels.count(label) > 1}

    shown: list[tuple[str, str, str]] = []
    # Games played is a filterable metric like any other, but the table opens with
    # it beside the player's name: counting it here would print it twice.
    seen: set[str] = set(_IDENTITY)
    for option in described:
        if option.key not in seen:
            seen.add(option.key)
            shown.append((_header(option, repeated), option.key, option.fmt))
        if option.denominator and option.denominator not in seen:
            seen.add(option.denominator)
            shown.append((count_name(option.denominator), option.denominator, metrics.INT))
    return tuple(shown)


def _opened_for(keys: tuple[str, ...]) -> list[str]:
    """The identity columns, then each metric asked for with the count behind it."""
    headers = {column: header for header, column, _ in catalogue_columns()}
    opened: list[str] = list(_ANCHOR)
    for key in dict.fromkeys(keys):
        for column in (key, metrics.DENOMINATORS.get(key)):
            if column and headers.get(column) and headers[column] not in opened:
                opened.append(headers[column])
    return opened


def opening_columns(criteria: tuple[Criterion, ...]) -> tuple[str, ...]:
    """Headers to show on load: the criteria, or a readable default.

    A shortlist built on games played alone names no column of its own — that
    total is already beside the player's name — so the table falls back to the
    default set rather than opening on three identity columns and nothing to read.
    """
    opened = _opened_for(tuple(criterion.metric for criterion in criteria))
    return tuple(opened if len(opened) > len(_ANCHOR) else _opened_for(_DEFAULTS))


@cache
def _baseline_floors() -> dict[str, tuple[str, int]]:
    """The floor each board already applies to its context columns.

    Open 3PT% blanks below ten open threes on the contested board; it does the
    same here, whether or not the reader ever opens the panel.
    """
    floors: dict[str, tuple[str, int]] = {}
    for view in catalogue.all_views():
        for column in view.columns:
            if column.sample and column.min_sample > 0:
                floors.setdefault(column.key, (column.sample, column.min_sample))
    return floors


def _gate(frame: pd.DataFrame) -> pd.DataFrame:
    """Blank every value its own board would refuse to print.

    A display gate, not a filter: the player stays on the list, but a percentage
    the sample cannot support is not printed as though it could. The floors are
    the boards' own, so Open 3PT% clears at ten open threes here exactly as it does
    there. This page sets no minimums of its own — what protects a number here is
    the criterion the reader can see, which carries the count behind it.
    """
    out = frame.copy()

    for column, (count, wanted) in _baseline_floors().items():
        if column in out.columns and count in out.columns:
            out[column] = out[column].where(out[count].fillna(0) >= wanted)
    return out


def build(
    frame: pd.DataFrame,
    as_percentiles: bool = False,
    league: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """The display frame carrying every metric, and the format of each column.

    Args:
        frame: the shortlisted players.
        as_percentiles: show every number as its place in the league rather than its
            value, counts included — where a player's shot volume sits among his
            peers is a fact a scout reads, and the table opens on values anyway.
        league: the scope bar's league, for the percentiles to be measured against.
            A standing computed inside the shortlist would say "best of the five
            players you already selected", which is not what a scout reads it as —
            a shortlist of shooters would show its worst shooter in the first
            percentile.
    """
    gated = _gate(frame)
    reference = _gate(league) if league is not None else gated

    # Gathered first and assembled in one pass: inserted one at a time, a hundred
    # columns leave pandas re-copying a fragmented block on every assignment.
    built: dict[str, pd.Series] = {
        PLAYER: frame[schema.PLAYER_NAME],
        TEAM: frame[schema.TEAM_NAME],
    }
    formats: dict[str, str] = {}

    def place(column: str) -> pd.Series:
        return ranking.percentile_series(
            reference, column, reference[column].notna()
        ).reindex(frame.index)

    if as_percentiles:
        built[GAMES] = place(schema.GAMES_PLAYED)
        formats[GAMES] = PERCENTILE
    else:
        built[GAMES] = frame[schema.GAMES_PLAYED]
        formats[GAMES] = metrics.INT

    for header, column, fmt_key in catalogue_columns():
        if column not in gated.columns:
            continue
        if as_percentiles:
            built[header] = place(column)
            formats[header] = PERCENTILE
        else:
            built[header] = gated[column]
            formats[header] = fmt_key

    display = pd.concat(built, axis=1)
    display.columns = list(built)
    return display, formats


@cache
def _tips() -> dict[str, str]:
    """One tooltip per header the table can carry. Configuration, so read once."""
    tips = {
        GAMES: glossary.definition(schema.GAMES_PLAYED),
        TEAM: "Club the player finished the season with.",
    }
    for header, column, _ in catalogue_columns():
        tips[header] = glossary.definition(column)
    return tips


def column_config(display: pd.DataFrame) -> dict[str, object]:
    """A definition on every header, including the ones a reader reveals himself."""
    tips = _tips()
    return {
        header: st.column_config.Column(label=header, help=tips.get(header) or None)
        for header in display.columns
    }
