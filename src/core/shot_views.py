"""The shot-quality views: where he shoots, how guarded he is, how he creates.

Pure declaration: which axes a view plots, which count its minimum applies to,
which columns its table carries. Nothing here is listed that the interface does
not actually show.
"""

from __future__ import annotations

from src.core.metrics import (
    DEC1,
    DEC2,
    INT,
    PCT0,
    PCT1,
    Axis,
    Column,
    Lens,
    Profile,
    Segment,
    Threshold,
    View,
)
from src.data import schema

SHOT_PROFILE = Profile(
    breakdown_title="Shot menu",
    breakdown_caption="How his attempts break down, from the rim outwards",
    breakdown=tuple(
        Segment(zone.label, zone.attempt_rate, zone.attempts)
        for zone in schema.SHOT_ZONES
    ),
    comparison_title="Accuracy by zone",
    comparison_caption="Bars run to 100%; the vertical line marks the league median for that zone",
    comparison=tuple(
        Segment(zone.label, zone.made_pct, zone.attempts, schema.ZONE_MIN_ATTEMPTS)
        for zone in schema.SHOT_ZONES
    ),
)

ZONE = Lens(
    profile=SHOT_PROFILE,
    key="zone",
    label="Shot distance",
    caption="How far out he shoots, and what it returns",
    views=(
        View(
            key="zone",
            label="Every shot",
            title="Shot distance and efficiency",
            description=(
                "Further right, he shoots from further out on average. Higher, he turns "
                "those shots into more points. His full shot menu is on the right."
            ),
            x=Axis(schema.SHOT_DISTANCE_METRES, "Average shot distance (m)", DEC1),
            y=Axis(schema.POINTS_PER_SHOT, "Points per shot", DEC2),
            threshold=Threshold(schema.ATTEMPTS, "Field goal attempts", 100),
            columns=(
                Column(schema.ATTEMPTS, "Shots", INT),
                Column(schema.EFG, "eFG%", PCT1, sample=schema.ATTEMPTS, is_rank_basis=True),
                Column(schema.SHOT_DISTANCE_METRES, "Avg distance (m)", DEC1),
                Column(schema.THREE_ATTEMPTS, "Three-point shots", INT),
                Column(schema.RIM_RATE, "% at the rim", PCT0),
                Column(schema.MIDRANGE_RATE, "% from mid-range", PCT0),
                Column(schema.THREE_ZONE_RATE, "% from three", PCT0, is_context=True),
            ),
            tiles=(schema.EFG, schema.RIM_RATE, schema.MIDRANGE_RATE, schema.THREE_ZONE_RATE),
            quadrants=("Scores from distance", "Scores near the rim"),
            summary=(
                "Averages {derived_avg_shot_distance_metres} m per shot, with {zone_three_attempt_rate} "
                "of his attempts from three and {rim_attempt_rate} at the rim."
            ),
        ),
    ),
)

CONTEST = Lens(
    profile=SHOT_PROFILE,
    view_label="Shot type",
    key="contest",
    label="Shot contestation",
    caption="How closely he is guarded, and whether he still scores",
    views=(
        View(
            key="contest_all",
            label="Every shot",
            title="Shot difficulty and shot-making",
            description=(
                "Right means a bigger cut of his shots go up with a defender on him. "
                "Up means he still scores on them."
            ),
            caveat=(
                "Big men sit at the top here: most of their guarded shots are layups and "
                "dunks, which stay efficient under pressure. Switch to **Two-pointers** or "
                "**Threes** to compare like for like."
            ),
            x=Axis(schema.CONTESTED_RATE, "% of his shots taken guarded", PCT0),
            y=Axis(schema.CONTESTED_EFG, "eFG% when guarded", PCT1),
            threshold=Threshold(schema.CONTESTED_ATTEMPTS, "Guarded shots", 60),
            columns=(
                Column(schema.ATTEMPTS, "Shots", INT),
                Column(schema.CONTESTED_RATE, "% taken guarded", PCT0),
                Column(
                    schema.CONTESTED_EFG,
                    "Guarded eFG%",
                    PCT1,
                    sample=schema.CONTESTED_ATTEMPTS,
                    is_rank_basis=True,
                ),
                Column(
                    schema.UNCONTESTED_EFG,
                    "Open eFG%",
                    PCT1,
                    sample=schema.UNCONTESTED_ATTEMPTS,
                    min_sample=20,
                    is_context=True,
                ),
                Column(schema.RIM_RATE, "% at the rim", PCT0),
            ),
            tiles=(schema.CONTESTED_EFG, schema.UNCONTESTED_EFG, schema.CONTESTED_RATE),
            quadrants=("Makes guarded shots", "Kept open by the system"),
            summary=(
                "{contested_attempt_rate} of his shots go up guarded, and he scores "
                "{contested_efg_percentage} eFG on them against "
                "{uncontested_efg_percentage} when open."
            ),
        ),
        View(
            key="contest_two",
            label="Two-pointers",
            title="Guarded two-point shooting",
            description=(
                "Two-pointers only, so a rim finisher is measured against other rim "
                "finishers rather than against shooters."
            ),
            x=Axis(schema.CONTESTED_TWO_RATE, "% of his twos taken guarded", PCT0),
            y=Axis(schema.CONTESTED_TWO_PCT, "2PT% when guarded", PCT1),
            threshold=Threshold(schema.CONTESTED_TWO_ATTEMPTS, "Guarded two-point shots", 60),
            columns=(
                Column(schema.TWO_ATTEMPTS, "Two-point shots", INT),
                Column(schema.CONTESTED_TWO_RATE, "% taken guarded", PCT0),
                Column(
                    schema.CONTESTED_TWO_PCT,
                    "Guarded 2PT%",
                    PCT1,
                    sample=schema.CONTESTED_TWO_ATTEMPTS,
                    is_rank_basis=True,
                ),
                Column(
                    schema.UNCONTESTED_TWO_PCT,
                    "Open 2PT%",
                    PCT1,
                    sample=schema.UNCONTESTED_TWO_ATTEMPTS,
                    min_sample=15,
                    is_context=True,
                ),
                Column(schema.RIM_RATE, "% at the rim", PCT0),
            ),
            tiles=(schema.CONTESTED_TWO_PCT, schema.UNCONTESTED_TWO_PCT, schema.CONTESTED_TWO_RATE),
            quadrants=("Makes guarded twos", "Gets clean looks inside"),
            summary=(
                "Shoots {contested_two_fg_percentage} on guarded two-pointers, against "
                "{uncontested_two_fg_percentage} when left open."
            ),
        ),
        View(
            key="contest_three",
            label="Threes",
            title="Guarded three-point shooting",
            description=(
                "Three-pointers only. The cleanest read on shot-making under pressure: "
                "it is the same shot for everybody on the floor."
            ),
            x=Axis(schema.CONTESTED_THREE_RATE, "% of his threes taken guarded", PCT0),
            y=Axis(schema.CONTESTED_THREE_PCT, "3PT% when guarded", PCT1),
            threshold=Threshold(schema.CONTESTED_THREE_ATTEMPTS, "Guarded three-point shots", 40),
            columns=(
                Column(schema.THREE_ATTEMPTS, "Three-point shots", INT),
                Column(schema.CONTESTED_THREE_RATE, "% taken guarded", PCT0),
                Column(
                    schema.CONTESTED_THREE_PCT,
                    "Guarded 3PT%",
                    PCT1,
                    sample=schema.CONTESTED_THREE_ATTEMPTS,
                    is_rank_basis=True,
                ),
                Column(
                    schema.UNCONTESTED_THREE_PCT,
                    "Open 3PT%",
                    PCT1,
                    sample=schema.UNCONTESTED_THREE_ATTEMPTS,
                    min_sample=10,
                    is_context=True,
                ),
                Column(schema.THREE_PT_PCT, "Overall 3PT%", PCT1, sample=schema.THREE_ATTEMPTS),
            ),
            tiles=(schema.CONTESTED_THREE_PCT, schema.UNCONTESTED_THREE_PCT, schema.THREE_PT_PCT),
            quadrants=("Makes guarded threes", "Spot-up shooter"),
            summary=(
                "Shoots {contested_three_fg_percentage} on guarded threes, against "
                "{uncontested_three_fg_percentage} when left open."
            ),
        ),
    ),
)

CREATION = Lens(
    profile=SHOT_PROFILE,
    key="creation",
    label="Shot creation",
    caption="Whether he makes his own shot or is set up",
    views=(
        View(
            key="creation",
            label="Every shot",
            title="Self-creation and efficiency off the dribble",
            description=(
                "Right means he makes his own shot rather than being set up. Up means the "
                "shots he creates still go in. Far left is a finisher who needs a passer."
            ),
            x=Axis(schema.OFF_DRIBBLE_RATE, "% of his shots taken off the dribble", PCT0),
            y=Axis(schema.OFF_DRIBBLE_EFG, "eFG% off the dribble", PCT1),
            threshold=Threshold(schema.OFF_DRIBBLE_ATTEMPTS, "Shots off the dribble", 50),
            columns=(
                Column(schema.ATTEMPTS, "Shots", INT),
                Column(schema.OFF_DRIBBLE_RATE, "% off the dribble", PCT0),
                Column(
                    schema.OFF_DRIBBLE_EFG,
                    "Off-dribble eFG%",
                    PCT1,
                    sample=schema.OFF_DRIBBLE_ATTEMPTS,
                    is_rank_basis=True,
                ),
                Column(
                    schema.CATCH_SHOOT_EFG,
                    "Catch and shoot eFG%",
                    PCT1,
                    sample=schema.CATCH_SHOOT_ATTEMPTS,
                    min_sample=25,
                    is_context=True,
                ),
                Column(schema.ASSISTED_SHARE, "% of baskets assisted", PCT0),
            ),
            tiles=(schema.OFF_DRIBBLE_EFG, schema.CATCH_SHOOT_EFG, schema.ASSISTED_SHARE),
            quadrants=("Creates and converts", "Set up by others"),
            summary=(
                "Takes {od_attempt_rate} of his shots off the dribble, and "
                "{derived_assisted_share} of his baskets come off a teammate's pass."
            ),
        ),
    ),
)

SHOT_LENSES: tuple[Lens, ...] = (ZONE, CONTEST, CREATION)
