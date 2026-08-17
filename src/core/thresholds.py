"""Two-stage filtering: who is in scope, and whose numbers can be trusted.

Stage one is the scope bar at the top of every page — games played and shots taken.
It defines the working dataset: who is in the league as far as the app is
concerned, and therefore who every percentile in the app is measured against.
Stage two is about one estimate, and always applies to the count the displayed
rate is made of. The two answer different questions and are never merged.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.core.metrics import SEASON_MINIMUM, View
from src.data import schema

#: Default for the population stage. Rotation player, not a one-off appearance.
DEFAULT_MIN_GAMES: int = 15

#: Offered in the games selector. `games_played` runs from 1 to 44 in this file —
#: the season is 34 rounds plus play-offs — so nothing here is a hard-coded total.
GAMES_CHOICES: tuple[int, ...] = (0, 10, 15, 20, 25)

#: Offered in the shots selector, in notches of `metrics.MINIMUM_STEP`. One shot
#: per official game is the default, as everywhere else in the app.
SHOT_CHOICES: tuple[int, ...] = (0, 15, 25, SEASON_MINIMUM, 50, 75, 100)


@dataclass(frozen=True)
class PopulationFilter:
    """The scope bar — the working dataset, and what is being looked at inside it.

    The first three fields say who counts as a league player at all, and are what
    every percentile in the app is measured against. The last two only narrow what
    is on screen: a reader typing a name into the search box is not asking to be
    ranked against himself.
    """

    min_games: int = DEFAULT_MIN_GAMES
    min_attempts: int = SEASON_MINIMUM
    exclude_traded: bool = False
    team: str | None = None
    name_query: str = ""


def league_mask(frame: pd.DataFrame, options: PopulationFilter) -> pd.Series:
    """Who counts as a league player, and therefore who percentiles are read against.

    Team and name search are deliberately left out: they say which of these players
    the reader wants on screen, not who he wants them compared to. Narrowing the
    scale to one club — or to the single man he searched for — would leave every
    standing in the app describing a population nobody can see.
    """
    mask = frame[schema.GAMES_PLAYED].fillna(0) >= options.min_games
    if options.min_attempts > 0:
        mask &= frame[schema.ATTEMPTS].fillna(0) >= options.min_attempts
    if options.exclude_traded:
        mask &= ~frame[schema.IS_TRADED].fillna(False).astype(bool)
    return mask


def apply_population(frame: pd.DataFrame, options: PopulationFilter) -> pd.DataFrame:
    """Restrict a frame to the players on screen: the league, then the reader's view.

    This stage never protects a percentage; it only decides who is being looked at.
    """
    mask = league_mask(frame, options)
    if options.team:
        mask &= frame[schema.TEAM_NAME] == options.team
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
