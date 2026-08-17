"""One player's offensive profile: his standing on each axis, and his shot zones.

Kept apart from the criteria engine: one answers "who should I look at", the
other "what does this one look like".
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.core import metrics, ranking
from src.core.aggregate import safe_ratio
from src.core.metrics import DEC2, INT, PCT1, Profile
from src.data import glossary, schema


#: Picks a role needs before its efficiency is placed on the web.
PICK_MINIMUM: int = 30


@dataclass(frozen=True)
class Axis:
    """One spoke of the radar: a metric, and the sample it needs to be placed."""

    key: str
    minimum: int
    fmt: str = PCT1

    @property
    def label(self) -> str:
        """The metric's name, as the data dictionary writes it."""
        return glossary.name(self.key)


def radar_axes() -> tuple[Axis, ...]:
    """The ten things this data can say about an offensive player.

    Both roles are on the web, never the main one alone. A player with 59 picks as
    ball handler and 55 as screener does a bit of each, and picking a side for him
    would hide half of what he is. A role he barely plays simply leaves a gap,
    which is itself the reading.

    The spokes are named after the metric, not after a quality, and named by the
    glossary rather than here: the same words on the web and in the tables mean a
    reader never has to map one onto the other.
    """
    return (
        Axis(schema.ATTEMPTS, 0, INT),
        Axis(schema.EFG, 50),
        Axis(schema.THREE_PA_RATE, 50),
        Axis(schema.OFF_DRIBBLE_RATE, 50),
        Axis(schema.CONTESTED_EFG, 40),
        Axis(schema.FOULED_RATE, 50),
        Axis(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp"), PICK_MINIMUM, DEC2),
        Axis(
            schema.pick_column(schema.ROLE_HANDLER_PREFIX, "assist_opportunity_rate"),
            PICK_MINIMUM,
        ),
        Axis(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp"), PICK_MINIMUM, DEC2),
        Axis(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "assist_rate"), PICK_MINIMUM),
    )


def radar_scores(frame: pd.DataFrame, player: str) -> pd.DataFrame:
    """Place one player on each radar spoke, against the scope bar's league.

    One pool for the whole web, and for the whole app: the players the scope bar
    leaves standing. Each spoke used to carry a pool of its own — only the players
    clearing that spoke's minimum — which scaled each axis more tightly but meant
    ten different populations on one figure, and a standing here that did not match
    the one in the table below.

    `Axis.minimum` still decides whether **this player** is placed: a man with four
    screens is left off the pick spokes rather than drawn at zero, which would read
    as a weakness he has not shown.

    Returns:
        One row per axis: `label`, `percentile`, `value` and `enough`.
    """
    row = frame.loc[frame[schema.PLAYER_NAME] == player]
    everyone = pd.Series(True, index=frame.index)
    rows = []
    for axis in radar_axes():
        # A metric with no denominator is a count in its own right: everybody has
        # one, so nobody is held off that spoke.
        denominator = metrics.DENOMINATORS.get(axis.key)
        eligible = (
            everyone
            if denominator is None or axis.minimum <= 0
            else frame[denominator].fillna(0) >= axis.minimum
        )
        scores = ranking.percentile_series(frame, axis.key, everyone)
        value = row[axis.key].iloc[0] if not row.empty else None
        measured = bool(eligible.loc[row.index[0]]) if not row.empty else False
        rows.append(
            {
                "label": axis.label,
                # He is placed against the league, but only if he has the events to
                # be placed at all: a points-per-pick on four screens is a number
                # the scale would happily rank and the reader should not be shown.
                "percentile": scores.loc[row.index[0]] if (measured and not row.empty) else None,
                "value": value,
                "fmt": axis.fmt,
                "enough": measured,
            }
        )
    return pd.DataFrame(rows)


def standing(pool: pd.DataFrame, column: str, player: str) -> float | None:
    """Where one player's number sits in the pool, as a 0-1 share at or below him.

    Used for the counts a card prints in words. Six hundred and fifteen screens is
    a number nobody can place; that it is more than all but four per cent of the
    league is the fact underneath it, and it costs one line to say.
    """
    row = pool.loc[pool[schema.PLAYER_NAME] == player, column]
    values = pool[column].dropna()
    if row.empty or values.empty or pd.isna(row.iloc[0]):
        return None
    return float((values <= row.iloc[0]).mean())


def spot_returns(row: pd.Series, profile: Profile) -> pd.DataFrame:
    """One row per spot on the floor: how much of his pick load it is, and what it pays.

    The two figures a card used to stack — where his screens are set, then what each
    spot returns — are one question asked twice, and answering it twice is what made
    the card too tall to read. Put on a floor plan they become one.

    Returns:
        One row per spot: `spot`, `share`, `picks`, `ppp` and `enough`.
    """
    rows = []
    for share, value in zip(profile.breakdown, profile.comparison):
        picks = row.get(value.count)
        rows.append(
            {
                "spot": share.label,
                "share": row.get(share.value),
                "picks": picks,
                "ppp": row.get(value.value),
                "enough": bool(pd.notna(picks) and picks >= value.min_count),
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
