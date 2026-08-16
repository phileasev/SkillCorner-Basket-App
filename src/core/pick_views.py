"""The pick-and-roll views, one lens per role.

Only four players out of 292 record fifty picks in both roles, so ball handler and
screener are very nearly two different populations. They get a lens each rather
than a filter, and every view inside a lens is built for that role's own set of
coverages — the two roles do not face the same ones.

⚠️ `{role}_ppp` counts the points a teammate scored off the player's pass as well
as his own. It measures the offence generated per screen, not his shooting. The
scorer-only figure is `{role}_points_per_shot_in_pick`.
"""

from __future__ import annotations

from src.core.metrics import (
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

#: Picks a coverage needs before its efficiency is worth printing. Blitz and Ice
#: are rare in the ACB, so their default sits where a handful of players clear it
#: rather than at a level that would empty the board.
COMMON_MINIMUM: int = 25
RARE_MINIMUM: int = 3
OVERALL_MINIMUM: int = 50


def _profile(role: str) -> Profile:
    """Where his screens are set, and what he produces from each spot."""
    return Profile(
        breakdown_title="Where his screens are set",
        breakdown_caption="Share of his picks, by spot on the floor",
        breakdown=tuple(
            Segment(spot.label, schema.pick_column(role, "pick_rate", spot=spot.suffix),
                    schema.picks_at(role, spot.suffix))
            for spot in schema.COURT_SPOTS
        ),
        comparison_title="Points per pick, by spot",
        comparison_caption="Bars run to 1.5 points; the line marks the league median for that spot",
        comparison=tuple(
            Segment(spot.label, schema.pick_column(role, "ppp", spot=spot.suffix),
                    schema.picks_at(role, spot.suffix), COMMON_MINIMUM)
            for spot in schema.COURT_SPOTS
        ),
        comparison_fmt=DEC2,
    )


def _overall(role: str, key: str, label: str, title: str, description: str,
             quadrants: tuple[str, str], x: Axis, summary: str,
             extra: tuple[Column, ...], tiles: tuple[str, ...]) -> View:
    """The view of a role across every pick he was involved in."""
    picks = schema.total_picks(role)
    return View(
        key=key,
        label=label,
        title=title,
        description=description,
        x=x,
        y=Axis(schema.pick_column(role, "ppp"), "Points generated per pick", DEC2),
        threshold=Threshold(picks, "Picks", OVERALL_MINIMUM),
        columns=(
            Column(picks, "Picks", INT),
            Column(schema.pick_column(role, "ppp"), "Points per pick", DEC2,
                   sample=picks, is_rank_basis=True),
            Column(schema.pick_column(role, "success_rate"), "Advantage created", PCT1,
                   sample=picks, is_context=True),
            *extra,
            Column(schema.pick_column(role, "turnover_rate"), "Turnover rate", PCT1, sample=picks),
        ),
        tiles=tiles,
        quadrants=quadrants,
        summary=summary,
    )


def _coverage_view(role: str, coverage: schema.Coverage) -> View:
    """The same role, restricted to the picks played one way by the defence."""
    picks = schema.picks_vs(role, coverage.suffix)
    ppp = schema.pick_column(role, "ppp", coverage=coverage.suffix)
    score = schema.pick_column(role, "score_rate", coverage=coverage.suffix)
    turnover = schema.pick_column(role, "turnover_rate", coverage=coverage.suffix)
    three_rate = schema.pick_column(role, "shot_rate_3pt", coverage=coverage.suffix)
    shot_rate = schema.pick_column(role, "shot_taken_pct", coverage=coverage.suffix)

    return View(
        key=f"{role}_{coverage.suffix}",
        label=coverage.label,
        title=f"{coverage.label}: what he does with it",
        description=(
            "Right, he takes the shot himself more often when the defence plays it this "
            "way. Up, the possession produces more points."
        ),
        caveat=(
            f"Spanish defences rarely play {coverage.label.lower()} on the screen, so even "
            "the busiest players see it a handful of times a season. Read the counts before "
            "the percentages."
            if coverage.rare
            else ""
        ),
        x=Axis(shot_rate, "Picks he finishes himself", PCT0),
        y=Axis(ppp, "Points generated per pick", DEC2),
        threshold=Threshold(
            picks,
            f"Picks {coverage.label.lower()}",
            RARE_MINIMUM if coverage.rare else COMMON_MINIMUM,
        ),
        columns=(
            Column(picks, "Picks", INT),
            Column(ppp, "Points per pick", DEC2, sample=picks, is_rank_basis=True),
            Column(score, "Scoring rate", PCT1, sample=picks, is_context=True),
            Column(shot_rate, "Finishes himself", PCT0, sample=picks),
            Column(three_rate, "Shoots a three", PCT0, sample=picks),
            Column(turnover, "Turnover rate", PCT1, sample=picks),
        ),
        tiles=(ppp, score, three_rate),
        quadrants=("Scores it himself", "Plays it out of the screen"),
        summary=(
            f"Against {coverage.label.lower()} he generates {{{ppp}}} points per pick, "
            f"finishing {{{shot_rate}}} of them himself."
        ),
    )


HANDLER = Lens(
    key="handler",
    label="Ball handler",
    dataset=schema.DATASET_PICKS,
    view_label="Coverage",
    caption="The player using the screen",
    profile=_profile(schema.ROLE_HANDLER_PREFIX),
    views=(
        _overall(
            schema.ROLE_HANDLER_PREFIX,
            key="handler_overall",
            label="Every pick",
            title="Scoring it, or playing out of it",
            description=(
                "Right, he finishes the screen himself more often. Up, the possession "
                "produces more points — his own and those his pass created."
            ),
            x=Axis(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "shot_taken_pct"),
                   "Picks he finishes himself", PCT0),
            quadrants=("Scores it himself", "Plays it out of the screen"),
            extra=(
                Column(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "shot_taken_pct"),
                       "Finishes himself", PCT0,
                       sample=schema.total_picks(schema.ROLE_HANDLER_PREFIX)),
                Column(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "assist_opportunity_rate"),
                       "Creates a shot", PCT1,
                       sample=schema.total_picks(schema.ROLE_HANDLER_PREFIX)),
                Column(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "pass_to_screener_pct"),
                       "Passes to the screener", PCT0,
                       sample=schema.total_picks(schema.ROLE_HANDLER_PREFIX)),
            ),
            tiles=(
                schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp"),
                schema.pick_column(schema.ROLE_HANDLER_PREFIX, "success_rate"),
                schema.pick_column(schema.ROLE_HANDLER_PREFIX, "assist_opportunity_rate"),
                schema.pick_column(schema.ROLE_HANDLER_PREFIX, "turnover_rate"),
            ),
            summary=(
                "Generates {handler_ppp} points per pick and creates a shot for a teammate "
                "on {handler_assist_opportunity_rate} of them, "
                "{handler_pass_to_screener_pct} of his passes going to the screener."
            ),
        ),
        *(_coverage_view(schema.ROLE_HANDLER_PREFIX, coverage)
          for coverage in schema.HANDLER_COVERAGES),
    ),
)

SCREENER = Lens(
    key="screener",
    label="Screener",
    dataset=schema.DATASET_PICKS,
    view_label="Coverage",
    caption="The player setting the screen",
    profile=_profile(schema.ROLE_SCREENER_PREFIX),
    views=(
        _overall(
            schema.ROLE_SCREENER_PREFIX,
            key="screener_overall",
            label="Every pick",
            title="Rolling, popping, or passing out of the short roll",
            description=(
                "Right, more of his shots out of the screen are threes — he pops rather "
                "than rolls. Up, the possession produces more points."
            ),
            x=Axis(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "shot_rate_3pt"),
                   "Shots out of the screen taken from three", PCT0),
            quadrants=("Pops and scores", "Rolls and finishes"),
            extra=(
                Column(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "shot_rate_3pt"),
                       "Pops for three", PCT0,
                       sample=schema.total_picks(schema.ROLE_SCREENER_PREFIX)),
                Column(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "assist_rate"),
                       "Assists out of the roll", PCT1,
                       sample=schema.total_picks(schema.ROLE_SCREENER_PREFIX)),
                Column(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "foul_pct"),
                       "Draws a foul", PCT1,
                       sample=schema.total_picks(schema.ROLE_SCREENER_PREFIX)),
            ),
            tiles=(
                schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp"),
                schema.pick_column(schema.ROLE_SCREENER_PREFIX, "success_rate"),
                schema.pick_column(schema.ROLE_SCREENER_PREFIX, "assist_rate"),
                schema.pick_column(schema.ROLE_SCREENER_PREFIX, "shot_rate_3pt"),
            ),
            summary=(
                "Generates {screener_ppp} points per pick, takes "
                "{screener_shot_rate_3pt} of his shots out of the screen from three, and "
                "finds a teammate on {screener_assist_rate} of his picks."
            ),
        ),
        *(_coverage_view(schema.ROLE_SCREENER_PREFIX, coverage)
          for coverage in schema.SCREENER_COVERAGES),
    ),
)

PICK_LENSES: tuple[Lens, ...] = (HANDLER, SCREENER)
