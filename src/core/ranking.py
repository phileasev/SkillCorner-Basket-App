"""Eligibility, percentiles and ordering.

**Every percentile in the app is measured on one pool: the scope bar's league.**
Games played and shots taken define who counts as a league player, and a standing
means the same thing on every page and under every view because of it. A per-view
pool was tried first and dropped: a percentile that moved whenever a slider moved
was a number the reader could not carry from one screen to the next.

Percentiles are computed on every run rather than read from a precomputed file.
They have to be: the pool is whatever the scope bar leaves standing, so a stored
percentile would be stale the moment the reader widens it. Ranking 300 rows costs
microseconds.
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


def add_percentiles(
    frame: pd.DataFrame, columns: tuple[str, ...], pool: pd.Series | None = None
) -> pd.DataFrame:
    """Place every player on a 0-1 scale, for each column given.

    A percentile answers "how many players does he sit above", so it only means
    something inside the pool it was measured on — which is why the pool is the
    scope bar's league everywhere, and not the players who happen to clear the
    view's own bar. A man below that bar keeps his standing and his greyed row: the
    grey says he is thin, the standing says where the number he does have sits.

    Args:
        frame: the players to place.
        columns: the metrics to place them on.
        pool: boolean mask of the players the scale is built from. Defaults to
            everybody in the frame.

    Returns:
        A new frame with one `percentile_<column>` per metric.
    """
    out = frame.copy()
    measured = (
        pd.Series(True, index=out.index) if pool is None else pool.reindex(out.index).fillna(False)
    )

    for column in columns:
        if column not in out.columns:
            continue
        scores = out.loc[measured, column].rank(pct=True, na_option="keep")
        out[percentile_of(column)] = scores.reindex(out.index)

    return out


def percentile_series(frame: pd.DataFrame, column: str, eligible: pd.Series) -> pd.Series:
    """Percentiles for one column, measured among one pool.

    The pool handed in is the scope bar's league wherever this is called. It stays
    a parameter rather than being assumed, so the one place that decides what the
    league is stays the one place that says so.
    """
    pool = eligible.reindex(frame.index).fillna(False)
    return frame.loc[pool, column].rank(pct=True, na_option="keep").reindex(frame.index)


def order(frame: pd.DataFrame, column: str, ascending: bool = False) -> pd.DataFrame:
    """Sort on one column, **missing values last whichever way it runs**.

    A blank is not a low number: it is a number the file does not have, and a player
    with no guarded threes has not shot the worst percentage on them. Sorting a
    column upwards and being handed a screen of empty cells is the grid's own
    default, and it is wrong here — which is why the app owns the row order rather
    than letting the grid sort.
    """
    return frame.sort_values(
        by=column, ascending=ascending, na_position="last", kind="mergesort"
    )


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
