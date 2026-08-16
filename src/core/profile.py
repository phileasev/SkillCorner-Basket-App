"""One player's offensive profile: his standing on each axis, and his shot zones.

Kept apart from the criteria engine: one answers "who should I look at", the
other "what does this one look like".
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.core import metrics, ranking
from src.core.aggregate import safe_ratio
from src.core.metrics import DEC2, INT, PCT1
from src.data import schema


#: Picks a role needs before its efficiency is placed on the web.
PICK_MINIMUM: int = 30


@dataclass(frozen=True)
class Axis:
    """One spoke of the radar: a metric, and the sample it needs to be placed."""

    label: str
    key: str
    minimum: int
    fmt: str = PCT1


def radar_axes() -> tuple[Axis, ...]:
    """The ten things this data can say about an offensive player.

    Both roles are on the web, never the main one alone. A player with 59 picks as
    ball handler and 55 as screener does a bit of each, and picking a side for him
    would hide half of what he is. A role he barely plays simply leaves a gap,
    which is itself the reading.

    The spokes are named after the metric, not after a quality: the same words
    here and in the tables mean a reader never has to map one onto the other.
    """
    return (
        Axis("Shots", schema.ATTEMPTS, 0, INT),
        Axis("eFG%", schema.EFG, 50),
        Axis("3PA rate", schema.THREE_PA_RATE, 50),
        Axis("% off the dribble", schema.OFF_DRIBBLE_RATE, 50),
        Axis("Guarded eFG%", schema.CONTESTED_EFG, 40),
        Axis("Fouled on the shot", schema.FOULED_RATE, 50),
        Axis(
            "Handler points per pick",
            schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp"),
            PICK_MINIMUM,
            DEC2,
        ),
        Axis(
            "Handler creates a shot",
            schema.pick_column(schema.ROLE_HANDLER_PREFIX, "assist_opportunity_rate"),
            PICK_MINIMUM,
        ),
        Axis(
            "Screener points per pick",
            schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp"),
            PICK_MINIMUM,
            DEC2,
        ),
        Axis(
            "Screener assists out of the roll",
            schema.pick_column(schema.ROLE_SCREENER_PREFIX, "assist_rate"),
            PICK_MINIMUM,
        ),
    )


def radar_scores(frame: pd.DataFrame, player: str) -> pd.DataFrame:
    """Place one player on each radar spoke, within that spoke's own population.

    Each axis is measured among the players who clear its own minimum: an axis
    gated on guarded shots must not be scaled by players who barely take any.
    A spoke the player himself cannot clear is left empty rather than drawn at zero.

    Returns:
        One row per axis: `label`, `percentile`, `value` and `enough`.
    """
    row = frame.loc[frame[schema.PLAYER_NAME] == player]
    rows = []
    for axis in radar_axes():
        # A metric with no denominator is a count in its own right: everybody has
        # one, so nobody is held off that spoke.
        denominator = metrics.DENOMINATORS.get(axis.key)
        eligible = (
            pd.Series(True, index=frame.index)
            if denominator is None or axis.minimum <= 0
            else frame[denominator].fillna(0) >= axis.minimum
        )
        scores = ranking.percentile_series(frame, axis.key, eligible)
        value = row[axis.key].iloc[0] if not row.empty else None
        rows.append(
            {
                "label": axis.label,
                "percentile": scores.loc[row.index[0]] if not row.empty else None,
                "value": value,
                "fmt": axis.fmt,
                "enough": bool(eligible.loc[row.index[0]]) if not row.empty else False,
            }
        )
    return pd.DataFrame(rows)


def zone_accuracy(row: pd.Series) -> pd.DataFrame:
    """Attempts and accuracy per NBA-convention zone, for one player.

    These are the only columns that separate a corner three from one above the
    break, and the only zone split shipped without a percentage — so the accuracy
    is computed here, missing rather than zero where nothing was attempted.
    """
    attempts = pd.Series({zone.label: row.get(zone.attempts) for zone in schema.NBA_ZONES})
    mades = pd.Series({zone.label: row.get(zone.mades) for zone in schema.NBA_ZONES})
    return pd.DataFrame(
        {
            "zone": attempts.index,
            "attempts": attempts.values,
            "mades": mades.values,
            "accuracy": safe_ratio(mades, attempts).values,
        }
    )
