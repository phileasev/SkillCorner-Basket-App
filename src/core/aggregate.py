"""Columns the CSVs do not ship, derived from columns they do.

Every function here is pure: it takes a frame and returns a new one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.data import schema


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide two count columns, returning NaN where the denominator is zero.

    A zero denominator means the events never happened, which is unknown rather
    than zero — printing 0% there would invent a fact.
    """
    return numerator.divide(denominator.replace(0, np.nan))


def derive_shot_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the derived shooting columns the views need.

    Three ratios the file does not provide, plus the ball handler / screener
    label used as a position proxy.

    Args:
        frame: a shooting frame already carrying the two pick-volume columns.

    Returns:
        A new frame; the input is left untouched.
    """
    out = frame.copy()

    out[schema.CONTESTED_TWO_RATE] = safe_ratio(
        out[schema.CONTESTED_TWO_ATTEMPTS], out[schema.TWO_ATTEMPTS]
    )
    out[schema.CONTESTED_THREE_RATE] = safe_ratio(
        out[schema.CONTESTED_THREE_ATTEMPTS], out[schema.THREE_ATTEMPTS]
    )
    out[schema.ASSISTED_SHARE] = safe_ratio(out[schema.ASSISTED_SHOTS], out[schema.MADES])
    out[schema.SHOT_DISTANCE_METRES] = out[schema.AVG_SHOT_DISTANCE] * schema.FEET_TO_METRES
    out[schema.FOULED_RATE] = safe_ratio(out[schema.FOULED_FGA], out[schema.ATTEMPTS])

    # The file splits the mid-range in two; a scout reads it as one area. Summing
    # the two zones is the same figure as 100% minus the rim and the three-point
    # shares, without the rounding drift of a subtraction.
    out[schema.MIDRANGE_RATE] = (
        out[schema.SHOT_ZONES_MIDRANGE[0]] + out[schema.SHOT_ZONES_MIDRANGE[1]]
    )

    handler = pd.to_numeric(out[schema.HANDLER_PICKS], errors="coerce").fillna(0)
    screener = pd.to_numeric(out[schema.SCREENER_PICKS], errors="coerce").fillna(0)
    out[schema.PRIMARY_ROLE] = np.where(
        handler >= screener, schema.ROLE_HANDLER, schema.ROLE_SCREENER
    )

    return out


def derive_pick_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add the derived pick columns the views need.

    The file already carries almost everything as a rate. Two things it does not:
    how many screens a role runs per game, and what share of them the defence plays
    each way — there is a share per spot on the floor but none per coverage, though
    both counts are there to divide.

    Args:
        frame: the raw pick-and-roll frame.

    Returns:
        A new frame; the input is left untouched.
    """
    out = frame.copy()

    for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX):
        picks = out[schema.total_picks(role)]
        out[schema.pick_column(role, "picks_per_game")] = safe_ratio(
            picks, out[schema.GAMES_PLAYED]
        )
        for coverage in schema.coverages_for(role):
            out[schema.coverage_share(role, coverage.suffix)] = safe_ratio(
                out[schema.picks_vs(role, coverage.suffix)], picks
            )

    return out


def segment_medians(frame: pd.DataFrame, segments: tuple) -> dict[str, float | None]:
    """Median value per profile segment, keyed by the segment's value column.

    Each median is taken among the players who clear that segment's own count, not
    across everybody. A player with two step-up screens who scored on neither
    carries a real 0.00, and there are enough of them that the whole-file median of
    `screener_ppp_at_stepUp` is 0.09 against 0.32 among the players with 25 picks
    there — so a measured player read against the first line looked outstanding for
    being ordinary. The same rule the app applies to percentiles — measure on the
    population that was measured — applied to the reference line.

    Note that a player with *no* picks at a spot carries NaN rather than 0 in the
    source file, and `league_median` drops those; the drag comes from thin samples
    that did happen, not from absent ones.
    """
    medians: dict[str, float | None] = {}
    for segment in segments:
        pool = frame
        if segment.min_count > 0 and segment.count in frame.columns:
            pool = frame[frame[segment.count].fillna(0) >= segment.min_count]
        medians[segment.value] = league_median(pool, segment.value)
    return medians


def league_median(frame: pd.DataFrame, column: str) -> float | None:
    """Median of a column over the frame, or None when nothing is measurable."""
    values = frame[column].dropna()
    return float(values.median()) if len(values) else None



