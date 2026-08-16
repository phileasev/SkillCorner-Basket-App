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

#: `avg_shot_distance` is labelled "metres" in the glossary but is stored in feet:
#: rim finishers sit near 3.8 and pure shooters near 22.1, and the observed maximum
#: (22.11) converts to 6.74 m — the FIBA three-point line, to the centimetre. Read
#: as metres the same figures would put every shooter beyond half court. The column
#: is converted for display and the raw one is never overwritten.
FEET_TO_METRES: float = 0.3048

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

#: The two zones a scout reads together as "the mid-range".
SHOT_ZONES_MIDRANGE: tuple[str, str] = (SHOT_ZONES[1].attempt_rate, SHOT_ZONES[2].attempt_rate)

#: Shots a zone needs before its accuracy is worth printing at all.
ZONE_MIN_ATTEMPTS: int = 20
