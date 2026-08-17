"""Building a shortlist: stackable criteria, and the profile behind each player.

**A criterion is one condition: the bar the reader typed.** It used to be two — the
value, and a number of events silently required behind it — which meant asking for
40% from three quietly also asked for forty attempts, and a reader who had not read
the source could not tell why a name was missing. The sample requirement now lives
where he can see and move it: the scope bar at the top of every page, which asks
for games played and shots taken and says how many players it leaves.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import pandas as pd

from src.core import catalogue, metrics
from src.data import glossary, schema

#: Where the metrics that belong to no lens are filed.
GENERAL_GROUP: str = "Season totals"

#: Season totals, and how much of the season he was there for. A board prints
#: them for context — total three-point attempts sit on the contested board — but
#: they answer none of the questions a board asks: how many shots a player took is
#: a fact about his volume, of the same nature as his games played, not about how
#: far out he shoots or how closely he is guarded. They are claimed before any
#: lens can, so they group together in the selector.
_SEASON_TOTALS: tuple[str, ...] = (
    schema.GAMES_PLAYED,
    schema.ATTEMPTS,
    schema.TWO_ATTEMPTS,
    schema.THREE_ATTEMPTS,
)


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
        """How the metric reads in the selector.

        The glossary name already says whose number it is — `Ball Handler -
        Points Per Pick`, `Three-Point Zone - Attempt Share` — so the lens is not
        repeated in front of it. It only sorts the list.
        """
        return self.label


@dataclass(frozen=True)
class Criterion:
    """One bar a player has to clear. Nothing else — what the reader typed."""

    metric: str
    at_least: bool
    value: float


@cache
def season_totals() -> tuple[Filterable, ...]:
    """The counts that describe the season rather than a way of playing.

    No sample requirement applies to any of them: a total is a total, and the
    reader who asks for four hundred shots has already said how many he wants.
    """
    return tuple(
        Filterable(
            key=key,
            label=glossary.name(key),
            group=GENERAL_GROUP,
            fmt=metrics.INT,
            denominator=None,
            variants=(("All", key),),
        )
        for key in _SEASON_TOTALS
    )


@cache
def describe(key: str) -> Filterable:
    """What one column is, wherever it is displayed.

    Used to name a criterion after it has been built, when only the column is
    known. The name needs no help to say which split it came from: the glossary
    writes it in — `Ball Handler - Points Per Pick (vs Ice)`.
    """
    for total in season_totals():
        if total.key == key:
            return total

    for lens in catalogue.LENSES:
        for view in lens.views:
            for column in view.columns:
                if column.key != key:
                    continue
                return Filterable(
                    key=key,
                    label=column.label,
                    group=lens.label,
                    fmt=column.fmt,
                    denominator=metrics.DENOMINATORS.get(key),
                )
    raise KeyError(key)


@cache
def options() -> tuple[Filterable, ...]:
    """Every metric the app displays anywhere, one entry per metric.

    Built from the view catalogue rather than listed again, so a metric added to a
    board becomes searchable here without a second edit. Three foldings apply:

    * the season totals come first and stand on their own (`_SEASON_TOTALS`);
    * columns whose glossary names differ only by a coverage — `Ball Handler -
      Points Per Pick` and its five `(vs …)` siblings — are one metric asked
      several ways, and become one entry carrying them as variants;
    * a column belongs to the first lens that displays it. The share of shots at
      the rim is printed on three boards, and stays a fact about distance.
    """
    built: list[Filterable] = list(season_totals())
    claimed: set[str] = {option.key for option in built}

    for lens in catalogue.LENSES:
        overall = lens.views[0]
        grouped: dict[str, list[tuple[str, str]]] = {}
        detail: dict[str, Filterable] = {}

        for view in lens.views:
            for column in view.columns:
                if column.key in claimed:
                    continue
                family = glossary.family(column.key)
                split = "All" if view is overall else view.label
                grouped.setdefault(family, []).append((split, column.key))
                detail.setdefault(
                    family,
                    Filterable(
                        key=column.key,
                        label=family,
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
            single = len(variants) == 1
            built.append(
                Filterable(
                    key=variants[0][1],
                    # With one variant there is no coverage to choose beside the
                    # name, so the name says which one it is on its own.
                    label=glossary.name(variants[0][1]) if single else base.label,
                    group=base.group,
                    fmt=base.fmt,
                    denominator=base.denominator,
                    split_label="" if single else base.split_label,
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
    """Which players clear one criterion.

    The bar and nothing else. A player with no value at all — no guarded threes, so
    no percentage on them — is out, because there is nothing to compare; that is a
    missing number, not a low one.
    """
    values = frame[criterion.metric]
    kept = values >= criterion.value if criterion.at_least else values <= criterion.value
    return kept & values.notna()


def apply(frame: pd.DataFrame, criteria: tuple[Criterion, ...]) -> pd.DataFrame:
    """Keep the players clearing every criterion."""
    kept = pd.Series(True, index=frame.index)
    for criterion in criteria:
        kept &= mask(frame, criterion)
    return frame.loc[kept].copy()


def pool(frame: pd.DataFrame, metric: str) -> pd.Series:
    """The players a bar on this metric is measured against.

    Everybody in the frame who has the number at all — and the frame handed in is
    the scope bar's league, which is the one pool every percentile in the app uses.
    """
    return frame[metric].notna()


def value_at_percentile(frame: pd.DataFrame, metric: str, percentile: float) -> float | None:
    """The value sitting at a given percentile of the pool, or None if it is empty."""
    values = frame.loc[pool(frame, metric), metric].dropna()
    if values.empty:
        return None
    return float(values.quantile(max(0.0, min(1.0, percentile))))


def percentile_of_value(frame: pd.DataFrame, metric: str, value: float) -> float | None:
    """Where a value sits in the pool, as a 0-1 share of players at or below it."""
    values = frame.loc[pool(frame, metric), metric].dropna()
    if values.empty:
        return None
    return float((values <= value).mean())
