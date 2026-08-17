"""Column names, file locations and shot-zone definitions.

Single source of truth for every raw column string used by the app. No other
module — and no page — is allowed to hard-code a column name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATA_DIR: Path = Path(__file__).resolve().parents[2] / "data"

PICKS_FILE: Path = DATA_DIR / "SPAIN_2024-2025_picks_offense.csv"
SHOTS_FILE: Path = DATA_DIR / "SPAIN_2024-2025_shots_offense.csv"
GLOSSARY_FILE: Path = DATA_DIR / "metric_glossary.csv"

DATASET_PICKS: str = "picks_offense"
DATASET_SHOTS: str = "shots_offense"

# --- identifiers shared by both datasets ------------------------------------
PLAYER_ID: str = "player_id"
PLAYER_NAME: str = "player_name"
TEAM_NAME: str = "team_name"
GAMES_PLAYED: str = "games_played"
IS_TRADED: str = "is_traded"

#: Identifiers both files carry, coalesced when the two are joined.
SHARED_IDENTIFIERS: tuple[str, ...] = (
    PLAYER_NAME,
    TEAM_NAME,
    GAMES_PLAYED,
    IS_TRADED,
    "meta_team_id",
)

# `appearances` duplicates `games_played` row for row in both files, so it is
# never surfaced. Kept here only to document why it is dropped.
REDUNDANT_IDENTIFIERS: tuple[str, ...] = ("appearances", "league", "season")

# --- pick-and-roll role volumes, used as a position proxy -------------------
HANDLER_PICKS: str = "handler_total_picks"
SCREENER_PICKS: str = "screener_total_picks"

# --- shot volume and efficiency ---------------------------------------------
ATTEMPTS: str = "attempts"
MADES: str = "mades"
TWO_ATTEMPTS: str = "two_attempts"
THREE_ATTEMPTS: str = "three_attempts"
EFG: str = "efg_percentage"
POINTS_PER_SHOT: str = "points_per_shot"
THREE_PT_PCT: str = "three_pt_percentage"
THREE_PA_RATE: str = "three_pa_rate"
AVG_SHOT_DISTANCE: str = "avg_shot_distance"
ASSISTED_SHOTS: str = "assisted_shots"
FOULED_FGA: str = "fouled_fga"

# --- contest split -----------------------------------------------------------
CONTESTED_ATTEMPTS: str = "contested_attempts"
CONTESTED_RATE: str = "contested_attempt_rate"
CONTESTED_EFG: str = "contested_efg_percentage"
UNCONTESTED_ATTEMPTS: str = "uncontested_attempts"
UNCONTESTED_EFG: str = "uncontested_efg_percentage"

CONTESTED_TWO_ATTEMPTS: str = "contested_two_attempts"
CONTESTED_TWO_PCT: str = "contested_two_fg_percentage"
UNCONTESTED_TWO_ATTEMPTS: str = "uncontested_two_attempts"
UNCONTESTED_TWO_PCT: str = "uncontested_two_fg_percentage"

CONTESTED_THREE_ATTEMPTS: str = "contested_three_attempts"
CONTESTED_THREE_PCT: str = "contested_three_fg_percentage"
UNCONTESTED_THREE_ATTEMPTS: str = "uncontested_three_attempts"
UNCONTESTED_THREE_PCT: str = "uncontested_three_fg_percentage"

# --- shot creation split -----------------------------------------------------
CATCH_SHOOT_ATTEMPTS: str = "cns_attempts"
CATCH_SHOOT_EFG: str = "cns_efg_percentage"
OFF_DRIBBLE_ATTEMPTS: str = "od_attempts"
OFF_DRIBBLE_EFG: str = "od_efg_percentage"
OFF_DRIBBLE_RATE: str = "od_attempt_rate"

# --- derived columns, produced by src.core.aggregate -------------------------
# Named with a shared prefix so they can never be mistaken for a raw CSV column.
DERIVED_PREFIX: str = "derived_"
CONTESTED_TWO_RATE: str = DERIVED_PREFIX + "contested_two_rate"
CONTESTED_THREE_RATE: str = DERIVED_PREFIX + "contested_three_rate"
ASSISTED_SHARE: str = DERIVED_PREFIX + "assisted_share"
PRIMARY_ROLE: str = DERIVED_PREFIX + "primary_role"
SHOT_DISTANCE_METRES: str = DERIVED_PREFIX + "avg_shot_distance_metres"
MIDRANGE_RATE: str = DERIVED_PREFIX + "midrange_attempt_rate"
FOULED_RATE: str = DERIVED_PREFIX + "fouled_rate"

#: `avg_shot_distance` is labelled "metres" in the glossary but is stored in feet:
#: rim finishers sit near 3.8 and pure shooters near 22.1, and the observed maximum
#: (22.11) converts to 6.74 m — the FIBA three-point line, to the centimetre. Read
#: as metres the same figures would put every shooter beyond half court. The column
#: is converted for display and the raw one is never overwritten.
FEET_TO_METRES: float = 0.3048

#: Rounds in the ACB regular season. This is the length of the season every club
#: plays, **not** a maximum: `games_played` runs to 44 in these files because the
#: play-offs are aggregated into the same row. Nothing compares a player's games
#: against it — it exists so a minimum can be stated per official game rather than
#: as a bare number nobody can place.
REGULAR_SEASON_GAMES: int = 34

ROLE_HANDLER: str = "ball handler"
ROLE_SCREENER: str = "screener"


@dataclass(frozen=True)
class ShotZone:
    """One SkillCorner shot zone, with its three parallel columns."""

    label: str
    attempts: str
    made_pct: str
    attempt_rate: str


SHOT_ZONES: tuple[ShotZone, ...] = (
    ShotZone("At the rim", "rim_attempts", "rim_fg_percentage", "rim_attempt_rate"),
    ShotZone(
        "Short mid-range / paint",
        "short_midrange_paint_attempts",
        "short_midrange_paint_fg_percentage",
        "short_midrange_paint_attempt_rate",
    ),
    ShotZone(
        "Long mid-range",
        "long_midrange_attempts",
        "long_midrange_fg_percentage",
        "long_midrange_attempt_rate",
    ),
    ShotZone(
        "Three-point zone",
        "zone_three_attempts",
        "zone_three_fg_percentage",
        "zone_three_attempt_rate",
    ),
)

RIM_RATE: str = SHOT_ZONES[0].attempt_rate
THREE_ZONE_RATE: str = SHOT_ZONES[3].attempt_rate

#: NBA-convention zones. The only split that separates a corner three from one
#: above the break — and the only one shipped without a percentage column, so the
#: accuracy has to be computed.
@dataclass(frozen=True)
class NbaZone:
    """One NBA-convention shot zone, and where it sits on a half court."""

    label: str
    attempts: str
    mades: str
    #: Rectangle on a 0-50 wide, 0-47 long half court: (x0, y0, x1, y1).
    box: tuple[float, float, float, float]


NBA_ZONES: tuple[NbaZone, ...] = (
    NbaZone("Restricted area", "attempts_Restricted_Area", "mades_Restricted_Area",
            (21.0, 0.0, 29.0, 6.0)),
    NbaZone("Paint (non-RA)", "attempts_Paint_Non_RA", "mades_Paint_Non_RA",
            (17.0, 0.0, 33.0, 19.0)),
    NbaZone("Mid-range", "attempts_Mid_Range", "mades_Mid_Range",
            (3.0, 0.0, 47.0, 27.0)),
    NbaZone("Corner 3", "attempts_Corner_3", "mades_Corner_3",
            (0.0, 0.0, 3.0, 14.0)),
    NbaZone("Above the break 3", "attempts_Above_Break_3", "mades_Above_Break_3",
            (0.0, 27.0, 50.0, 40.0)),
)


#: The two zones a scout reads together as "the mid-range".
SHOT_ZONES_MIDRANGE: tuple[str, str] = (SHOT_ZONES[1].attempt_rate, SHOT_ZONES[2].attempt_rate)

#: Shots a zone needs before its accuracy is worth printing at all.
ZONE_MIN_ATTEMPTS: int = 20


# --- pick-and-roll -----------------------------------------------------------
# Every metric in the picks file exists twice, once per role, and again for each
# defensive coverage and each spot on the floor. The names are built rather than
# listed: 599 columns would otherwise have to be typed out one by one.

ROLE_HANDLER_PREFIX: str = "handler"
ROLE_SCREENER_PREFIX: str = "screener"


@dataclass(frozen=True)
class Coverage:
    """One way the defence plays the screen."""

    label: str
    suffix: str
    #: Rare coverages carry a note on screen rather than being hidden.
    rare: bool = False


#: The two roles do not face the same coverages. Never assume symmetry.
HANDLER_COVERAGES: tuple[Coverage, ...] = (
    Coverage("Over the top", "over"),
    Coverage("Under", "under"),
    Coverage("Switch", "switch"),
    Coverage("Blitz", "blitz", rare=True),
    Coverage("Ice", "ice", rare=True),
)

SCREENER_COVERAGES: tuple[Coverage, ...] = (
    Coverage("Show / hedge", "show"),
    Coverage("Soft / drop", "soft"),
    Coverage("Switch", "switch"),
    Coverage("Blitz", "blitz", rare=True),
    Coverage("Ice", "ice", rare=True),
)


@dataclass(frozen=True)
class CourtSpot:
    """Where on the floor the screen is set."""

    label: str
    suffix: str


#: `stepUp` is camelCase in the middle of snake_case. Do not normalise it.
COURT_SPOTS: tuple[CourtSpot, ...] = (
    CourtSpot("Middle", "middle"),
    CourtSpot("Wing", "wing"),
    CourtSpot("Step-up", "stepUp"),
)


def pick_column(role: str, metric: str, coverage: str | None = None, spot: str | None = None) -> str:
    """Build a picks-file column name from its parts.

    Args:
        role: `handler` or `screener`.
        metric: the metric stem, e.g. `ppp` or `score_rate`.
        coverage: a defensive coverage suffix, e.g. `over`.
        spot: a court location suffix, e.g. `middle`.

    Returns:
        The column name, e.g. `handler_ppp_vs_over`.
    """
    name = f"{role}_{metric}"
    if coverage:
        name = f"{name}_vs_{coverage}"
    if spot:
        name = f"{name}_at_{spot}"
    return name


def total_picks(role: str) -> str:
    """The role's overall pick count, denominator of every overall rate."""
    return f"{role}_total_picks"


def picks_vs(role: str, coverage: str) -> str:
    """The role's pick count against one coverage, denominator of that split."""
    return pick_column(role, "picks", coverage=coverage)


def picks_at(role: str, spot: str) -> str:
    """The role's pick count at one spot on the floor."""
    return pick_column(role, "picks", spot=spot)


def coverages_for(role: str) -> tuple[Coverage, ...]:
    """The coverages one role actually faces. The two sets are not the same."""
    return HANDLER_COVERAGES if role == ROLE_HANDLER_PREFIX else SCREENER_COVERAGES


def coverage_share(role: str, coverage: str) -> str:
    """Share of a role's picks played one way by the defence.

    The file ships a share per spot on the floor (`pick_rate_at_…`) but none per
    coverage, so it is derived. The five coverages do account for the whole of a
    player's picks — the lowest total observed is 98% — which is what makes a
    hundred-percent bar the right shape for them.
    """
    return DERIVED_PREFIX + pick_column(role, "pick_rate", coverage=coverage)


#: Columns that are zero for every player in this release. Never displayed.
DEAD_PICK_METRICS: tuple[str, ...] = ("no_outcome_pick", "no_outcome_pick_pct")
