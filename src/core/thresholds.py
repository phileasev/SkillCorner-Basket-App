"""Two-stage filtering: who is in scope, and whose numbers can be trusted.

Stage one is about the analysis perimeter (games played). Stage two is about the
estimate itself, and always applies to the count the displayed rate is made of.
The two answer different questions and are never merged.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.core.metrics import View
from src.data import schema

#: Default for the population stage. Rotation player, not a one-off appearance.
DEFAULT_MIN_GAMES: int = 15

#: Offered in the games selector. `games_played` runs from 1 to 44 in this file —
#: the season is 34 rounds plus play-offs — so nothing here is a hard-coded total.
GAMES_CHOICES: tuple[int, ...] = (0, 10, 15, 20, 25)


@dataclass(frozen=True)
class PopulationFilter:
    """Stage one — the analysis perimeter."""

    min_games: int = DEFAULT_MIN_GAMES
    team: str | None = None
    exclude_traded: bool = False
    name_query: str = ""


def apply_population(frame: pd.DataFrame, options: PopulationFilter) -> pd.DataFrame:
    """Restrict a frame to the players in scope.

    This stage never protects a percentage; it only decides who is being looked at.
    """
    mask = frame[schema.GAMES_PLAYED] >= options.min_games
    if options.team:
        mask &= frame[schema.TEAM_NAME] == options.team
    if options.exclude_traded:
        mask &= ~frame[schema.IS_TRADED].astype(bool)
    if options.name_query:
        mask &= frame[schema.PLAYER_NAME].str.contains(options.name_query, case=False, na=False)
    return frame.loc[mask].copy()


def eligibility_mask(frame: pd.DataFrame, view: View, minimum: int) -> pd.Series:
    """Stage two — whether each player has enough shots to judge on this view.

    Args:
        frame: the population already in scope.
        view: the view on screen; its threshold names the count that matters.
        minimum: the count a player must reach.

    Returns:
        A boolean Series aligned with the frame.
    """
    counts = frame[view.threshold.key].fillna(0)
    return counts >= minimum


def slider_bounds(frame: pd.DataFrame, view: View) -> tuple[int, int]:
    """Return `(0, league high)` for a view's threshold slider.

    The maximum is whatever the CSV actually contains for that count, so a split
    where nobody clears 10 events cannot be given a misleading 500-wide slider.
    """
    observed = frame[view.threshold.key].fillna(0)
    highest = int(observed.max()) if len(observed) else 0
    return 0, highest


def sample_mask(frame: pd.DataFrame, count_column: str, minimum: int) -> pd.Series:
    """Whether each player has enough events behind a secondary column.

    Used for context columns that carry their own count but no slider: below the
    floor the value is blanked rather than printed.
    """
    if minimum <= 0:
        return pd.Series(True, index=frame.index)
    return frame[count_column].fillna(0) >= minimum
