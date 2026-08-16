"""Eligibility, percentiles and ordering, all computed on the eligible players only.

Placing a player against a pool that includes small-sample noise would distort the
scale for everybody, so players below the minimum are excluded from the
computation and carry no percentile at all.

Percentiles are computed on every run rather than read from a precomputed file.
They have to be: the eligible pool is whatever the reader's filters and minimum
leave standing, so a stored percentile would be stale the moment a slider moves.
Ranking 300 rows costs microseconds.
"""

from __future__ import annotations

import pandas as pd

#: Column added by `flag_eligible`, True when the player clears the view's minimum.
ELIGIBLE: str = "eligible"

#: Prefix of the percentile column produced for a metric.
PERCENTILE_PREFIX: str = "percentile_"


def percentile_of(column: str) -> str:
    """Name of the percentile column belonging to a metric."""
    return PERCENTILE_PREFIX + column


def flag_eligible(frame: pd.DataFrame, eligible: pd.Series) -> pd.DataFrame:
    """Attach the eligibility flag to a population.

    Args:
        frame: the population in scope.
        eligible: boolean mask, aligned with the frame.

    Returns:
        A new frame carrying an `eligible` column.
    """
    out = frame.copy()
    out[ELIGIBLE] = eligible.reindex(out.index).fillna(False).astype(bool)
    return out


def add_percentiles(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    """Place every eligible player on a 0-1 scale, for each column given.

    A percentile answers "how many players does he sit above", so it is only
    meaningful inside the pool it was measured on. Players below the minimum get
    no value rather than a misleading one.

    Args:
        frame: a population already carrying the `eligible` column.
        columns: the metrics to place players on.

    Returns:
        A new frame with one `percentile_<column>` per metric.
    """
    out = frame.copy()
    measured = out[ELIGIBLE]

    for column in columns:
        if column not in out.columns:
            continue
        scores = out.loc[measured, column].rank(pct=True, na_option="keep")
        out[percentile_of(column)] = scores.reindex(out.index)

    return out


def two_tier_sort(frame: pd.DataFrame, metric: str, ascending: bool = False) -> pd.DataFrame:
    """Sort eligible players first, then ineligible ones, each group sorted alike.

    Args:
        frame: a frame already carrying the `eligible` column.
        metric: the column to sort on within each group.
        ascending: True when a lower value should come first.

    Returns:
        A new, reordered frame.
    """
    return frame.sort_values(
        by=[ELIGIBLE, metric],
        ascending=[False, ascending],
        na_position="last",
        kind="mergesort",
    )


def pin_first(frame: pd.DataFrame, column: str, value: object) -> pd.DataFrame:
    """Lift the rows matching a value to the top, leaving every other row in place.

    Used for the player the reader has loaded. It is a bookmark, not a ranking
    claim: the table carries no position column, so a pinned row states "this is
    the one you are looking at" rather than "this is the best".

    Args:
        frame: an already ordered frame.
        column: the column to match on.
        value: the value to lift.

    Returns:
        A new frame, reordered. The input order is kept among the rest.
    """
    if value is None or column not in frame.columns:
        return frame

    picked = frame[column] == value
    if not picked.any():
        return frame

    return pd.concat([frame[picked], frame[~picked]])
