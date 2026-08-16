"""Building a shortlist: stackable criteria, and the profile behind each player.

A criterion is two conditions, never one. "Shoots 40% from three" is worthless
without "on enough threes to mean it", so every criterion carries the count its
metric was computed from and filters on both. The reader sets the bar; the count
requirement comes from `DENOMINATORS` and is his to raise.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import pandas as pd

from src.core import catalogue, metrics
from src.data import schema

#: Events required behind a metric whose denominator no view happens to gate on.
FALLBACK_MINIMUM: int = 25


@dataclass(frozen=True)
class Filterable:
    """One metric the reader can build a criterion on, with its splits attached.

    A pick metric exists once per defensive coverage and a contested one once per
    shot type. Listing every variant separately made a selector of ninety-odd
    lines where a dozen would do, so the variants hang off the metric and are
    picked next to it instead.
    """

    key: str
    label: str
    group: str
    fmt: str
    denominator: str | None
    split_label: str = ""
    #: `(split name, column)`, the first being the one the metric opens on.
    variants: tuple[tuple[str, str], ...] = ()

    @property
    def title(self) -> str:
        """How the metric reads in the selector."""
        return f"{self.group} · {self.label}"


@dataclass(frozen=True)
class Criterion:
    """One bar a player has to clear, and the sample it has to clear it on."""

    metric: str
    at_least: bool
    value: float
    minimum: int


def default_minimum(denominator: str | None) -> int:
    """Events to require behind a metric, taken from the view that gates on it.

    Reusing a view's own threshold keeps one answer to "how many is enough" across
    the whole app instead of inventing a second one here.
    """
    if denominator is None:
        return 0
    for view in catalogue.all_views():
        if view.threshold.key == denominator:
            return view.threshold.default
    return FALLBACK_MINIMUM


@cache
def describe(key: str) -> Filterable:
    """What one column is, wherever it is displayed.

    Used to name a criterion after it has been built, when only the column is
    known. The split is folded into the label so a saved criterion still says
    which coverage it was about.
    """
    for lens in catalogue.LENSES:
        overall = lens.views[0]
        for view in lens.views:
            for column in view.columns:
                if column.key != key:
                    continue
                label = (
                    column.label if view is overall else f"{column.label} ({view.label})"
                )
                return Filterable(
                    key=key,
                    label=label,
                    group=lens.label,
                    fmt=column.fmt,
                    denominator=metrics.DENOMINATORS.get(key),
                )
    raise KeyError(key)


@cache
def options() -> tuple[Filterable, ...]:
    """Every metric the app displays anywhere, one entry per metric.

    Built from the view catalogue rather than listed again, so a metric added to a
    board becomes searchable here without a second edit. Two foldings apply:

    * columns sharing a label within a lens are the same metric on different
      splits, and become one entry carrying them as variants;
    * a column belongs to the first lens that displays it. Total three-point
      attempts appear on the contested board for context, but they are a fact
      about how far out a player shoots, not about how closely he is guarded.
    """
    built: list[Filterable] = []
    claimed: set[str] = set()

    for lens in catalogue.LENSES:
        overall = lens.views[0]
        grouped: dict[str, list[tuple[str, str]]] = {}
        detail: dict[str, Filterable] = {}

        for view in lens.views:
            for column in view.columns:
                if column.key in claimed:
                    continue
                split = "All" if view is overall else view.label
                grouped.setdefault(column.label, []).append((split, column.key))
                detail.setdefault(
                    column.label,
                    Filterable(
                        key=column.key,
                        label=column.label,
                        group=lens.label,
                        fmt=column.fmt,
                        denominator=metrics.DENOMINATORS.get(column.key),
                        split_label=lens.view_label,
                    ),
                )

        for label, listed in grouped.items():
            # The same column can be displayed by several views of a lens — the rim
            # share sits on both the all-shots and the two-point view. Offering it
            # twice would put two split names on one number. First seen wins, so the
            # overall view keeps the metric and the splits stay in reading order.
            taken: set[str] = set()
            variants = tuple(
                (split, column)
                for split, column in listed
                if not (column in taken or taken.add(column))
            )
            claimed.update(column for _, column in variants)
            base = detail[label]
            built.append(
                Filterable(
                    key=variants[0][1],
                    label=base.label,
                    group=base.group,
                    fmt=base.fmt,
                    denominator=base.denominator,
                    split_label=base.split_label if len(variants) > 1 else "",
                    variants=variants,
                )
            )

    return tuple(built)


def option_by_key(key: str) -> Filterable:
    """Look one metric up by any of its columns."""
    for option in options():
        if any(column == key for _, column in option.variants):
            return option
    return describe(key)


def mask(frame: pd.DataFrame, criterion: Criterion) -> pd.Series:
    """Which players clear one criterion, sample requirement included."""
    values = frame[criterion.metric]
    kept = values >= criterion.value if criterion.at_least else values <= criterion.value
    kept &= values.notna()

    denominator = metrics.DENOMINATORS.get(criterion.metric)
    if denominator is not None and criterion.minimum > 0:
        kept &= frame[denominator].fillna(0) >= criterion.minimum
    return kept


def apply(frame: pd.DataFrame, criteria: tuple[Criterion, ...]) -> pd.DataFrame:
    """Keep the players clearing every criterion."""
    kept = pd.Series(True, index=frame.index)
    for criterion in criteria:
        kept &= mask(frame, criterion)
    return frame.loc[kept].copy()


def pool(frame: pd.DataFrame, metric: str, minimum: int) -> pd.Series:
    """The players a bar on this metric is measured against.

    The same pool the criterion itself filters on, so the percentile a reader is
    shown is the percentile among the players he is actually comparing.
    """
    denominator = metrics.DENOMINATORS.get(metric)
    if denominator is None or minimum <= 0:
        return frame[metric].notna()
    return frame[metric].notna() & (frame[denominator].fillna(0) >= minimum)


def value_at_percentile(
    frame: pd.DataFrame, metric: str, minimum: int, percentile: float
) -> float | None:
    """The value sitting at a given percentile of the pool, or None if it is empty."""
    values = frame.loc[pool(frame, metric, minimum), metric].dropna()
    if values.empty:
        return None
    return float(values.quantile(max(0.0, min(1.0, percentile))))


def percentile_of_value(
    frame: pd.DataFrame, metric: str, minimum: int, value: float
) -> float | None:
    """Where a value sits in the pool, as a 0-1 share of players at or below it."""
    values = frame.loc[pool(frame, metric, minimum), metric].dropna()
    if values.empty:
        return None
    return float((values <= value).mean())
