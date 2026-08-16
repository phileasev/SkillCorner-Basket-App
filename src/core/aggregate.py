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


def league_median(frame: pd.DataFrame, column: str) -> float | None:
    """Median of a column over the frame, or None when nothing is measurable."""
    values = frame[column].dropna()
    return float(values.median()) if len(values) else None


def zone_medians(frame: pd.DataFrame) -> dict[str, float | None]:
    """Median accuracy per shot zone, keyed by the zone's percentage column."""
    return {zone.made_pct: league_median(frame, zone.made_pct) for zone in schema.SHOT_ZONES}
