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
GAMES: str = "Games"
PERCENTILE: str = "percentile"

#: Opened on screen when no criterion names anything else.
_DEFAULTS: tuple[str, ...] = (
    schema.ATTEMPTS,
    schema.EFG,
    schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp"),
    schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp"),
)

#: The glossary calls the season totals "Attempts" and "Made", which says nothing
#: once a dozen other counts sit on screen beside them.
_PLAIN_NAMES: dict[str, str] = {
    schema.ATTEMPTS: "Field goal attempts",
    schema.MADES: "Field goals made",
    schema.TWO_ATTEMPTS: "Two-point attempts",
    schema.THREE_ATTEMPTS: "Three-point attempts",
}


def count_name(denominator: str) -> str:
    """The count, named the way the glossary names it, or plainly where it is bare."""
    if denominator in _PLAIN_NAMES:
        return _PLAIN_NAMES[denominator]
    info = glossary.lookup(denominator) or glossary.lookup(denominator, schema.DATASET_PICKS)
    label = info.display_name if info and info.display_name else denominator
    return label.replace(" - ", " ")


def _count_header(denominator: str) -> str:
    """The same count, shortened for a column header."""
    if denominator in _PLAIN_NAMES:
        return _PLAIN_NAMES[denominator]
    label = count_name(denominator).replace("Attempts", "shots").replace("Picks", "picks")
    return label[:1].upper() + label[1:]


def _header(option: Filterable, repeated: set[str]) -> str:
    """A column header, prefixed by its lens when the label is not unique.

    Points per pick exists for both roles, and one header cannot stand for two
    columns: the second would quietly overwrite the first, in the table and in
    the export alike.
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
    seen: set[str] = set()
    for option in described:
        if option.key not in seen:
            seen.add(option.key)
            shown.append((_header(option, repeated), option.key, option.fmt))
        if option.denominator and option.denominator not in seen:
            seen.add(option.denominator)
            shown.append((_count_header(option.denominator), option.denominator, metrics.INT))
    return tuple(shown)


def opening_columns(criteria: tuple[Criterion, ...]) -> tuple[str, ...]:
    """Headers to show on load: the criteria, or a readable default."""
    keys = [criterion.metric for criterion in criteria] or list(_DEFAULTS)
    headers = {column: header for header, column, _ in catalogue_columns()}

    opened: list[str] = [PLAYER, TEAM, GAMES]
    for key in dict.fromkeys(keys):
        for column in (key, metrics.DENOMINATORS.get(key)):
            if column and headers.get(column) and headers[column] not in opened:
                opened.append(headers[column])
    return tuple(opened)


@cache
def denominators() -> tuple[str, ...]:
    """The counts worth putting a slider on.

    Every count that already gates a number somewhere in the app, minus the
    coverage splits — a reader who cares about those sets them on the criterion
    itself, where the field already exists. That covers both the counts a board
    is built on and the ones its context columns blank themselves against, and
    leaves a panel rather than a cockpit.
    """
    seen: list[str] = []
    for view in catalogue.all_views():
        for count in (view.threshold.key, *(c.sample for c in view.columns if c.min_sample > 0)):
            if not count or "_vs_" in count or count in seen:
                continue
            seen.append(count)
    return tuple(seen)


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


def _gate(frame: pd.DataFrame, minimums: dict[str, int]) -> pd.DataFrame:
    """Blank every value resting on fewer events than asked for.

    A display gate, not a filter: the player stays on the list, but a percentage
    the sample cannot support is not printed as though it could.
    """
    out = frame.copy()
    baseline = _baseline_floors()

    for _, column, _ in catalogue_columns():
        if column not in out.columns:
            continue
        gates = []
        if column in baseline:
            gates.append(baseline[column])
        denominator = metrics.DENOMINATORS.get(column)
        if denominator and minimums.get(denominator, 0) > 0:
            gates.append((denominator, minimums[denominator]))

        for count, wanted in gates:
            if count in out.columns:
                out[column] = out[column].where(out[count].fillna(0) >= wanted)
    return out


def build(
    frame: pd.DataFrame,
    minimums: dict[str, int],
    as_percentiles: bool = False,
    league: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """The display frame carrying every metric, and the format of each column.

    Args:
        frame: the shortlisted players.
        minimums: events required behind each count.
        as_percentiles: show each rate as its place in the league rather than its
            value. Counts stay counts: a number of shots is a fact, not a standing.
        league: everybody, for the percentiles to be measured against. A standing
            computed inside the shortlist would say "best of the five players you
            already selected", which is not what a scout reads it as — a shortlist
            of shooters would show its worst shooter in the first percentile.
    """
    gated = _gate(frame, minimums)
    reference = _gate(league, minimums) if league is not None else gated

    display = pd.DataFrame(index=frame.index)
    display[PLAYER] = frame[schema.PLAYER_NAME]
    display[TEAM] = frame[schema.TEAM_NAME]
    display[GAMES] = frame[schema.GAMES_PLAYED]
    formats = {GAMES: metrics.INT}

    for header, column, fmt_key in catalogue_columns():
        if column not in gated.columns:
            continue
        if as_percentiles and fmt_key != metrics.INT:
            placed = ranking.percentile_series(reference, column, reference[column].notna())
            display[header] = placed.reindex(frame.index)
            formats[header] = PERCENTILE
        else:
            display[header] = gated[column]
            formats[header] = fmt_key
    return display, formats


def column_config(display: pd.DataFrame) -> dict[str, object]:
    """A definition on every header, including the ones a reader reveals himself."""
    tips = {
        GAMES: glossary.definition(schema.GAMES_PLAYED),
        TEAM: "Club the player finished the season with.",
    }
    for header, column, _ in catalogue_columns():
        tips[header] = glossary.definition(column)

    return {
        header: st.column_config.Column(label=header, help=tips.get(header) or None)
        for header in display.columns
    }
