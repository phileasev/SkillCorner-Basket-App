"""The pick-and-roll views, one lens per role.

Only four players out of 292 record fifty picks in both roles, so ball handler and
screener are very nearly two different populations. They get a lens each rather
than a filter, and every view inside a lens is built for that role's own set of
coverages — the two roles do not face the same ones.

⚠️ `{role}_ppp` counts the points a teammate scored off the player's pass as well
as his own. It measures the offence generated per screen, not his shooting. The
scorer-only figure is `{role}_points_per_shot_in_pick`.

A `Column` names nothing: its header is the display name `metric_glossary.csv`
gives that column, which already carries the role and the coverage — `Ball
Handler - Points Per Pick (vs Over)`. Only the sentences are written here.
"""

from __future__ import annotations

from src.core.metrics import (
    DEC2,
    INT,
    MINIMUM_STEP,
    PCT0,
    PCT1,
    Axis,
    Column,
    Facet,
    Lens,
    Profile,
    Segment,
    Threshold,
    View,
)
from src.data import schema

#: Where each role's overall board opens. The two are not the same number because
#: the two roles are not the same job: a screener is asked to set screens all game
#: and a ball handler runs the ones a team calls for him, so the volumes are not
#: comparable and one bar for both would judge them on the same scale. At these,
#: 141 handlers and 150 screeners are measured — a rotation's worth of each. Both
#: sit on a slider notch (`metrics.MINIMUM_STEP`), so either can be returned to.
HANDLER_MINIMUM: int = 10
SCREENER_MINIMUM: int = 20

#: What share of the league's screens each coverage and each spot accounts for,
#: measured on the two files. The same numbers serve both roles, and rightly so: a
#: screen played as a switch is one event on the floor, counted once from each end.
#: A test recomputes them from the CSVs, so they cannot quietly go stale.
LEAGUE_SHARE: dict[str, float] = {
    "over": 0.667,
    "switch": 0.164,
    "under": 0.159,
    "show": 0.451,
    "soft": 0.371,
    "ice": 0.006,
    "blitz": 0.003,
    "middle": 0.627,
    "wing": 0.235,
    "stepUp": 0.138,
}


def split_minimum(role_bar: int, split: str) -> int:
    """The bar for one coverage or one spot: the role's bar, cut to that split's share.

    A flat 25 picks per coverage was the same bar asked five times over, and it
    asked far more of a split than the board asks of the whole: a handler is
    measured from ten screens, yet needed twenty-five of them played one way. Only
    97 of the 213 players in scope had a figure against the over, 54 against the
    under, and **nobody at all** against the blitz or the ice — which reads as
    missing data rather than as a defence Spain barely plays.

    A split is therefore asked for the same slice of a season as the whole: the
    role's bar times how often the league plays it. Rounded **down** to a notch the
    slider can actually reach, never below one — a bar the reader cannot return to
    is a bar he loses the first time he moves the control, and a points-per-pick on
    zero picks is not a number. The counts sit beside every figure, so what a thin
    split looks like stays visible rather than being decided for him.
    """
    wanted = role_bar * LEAGUE_SHARE.get(split, 1.0)
    notches = [notch for notch in range(MINIMUM_STEP, role_bar + 1, MINIMUM_STEP)
               if notch <= wanted]
    return max(notches) if notches else 1


#: On the card's coverage figure, a pick is shown as soon as it happened. A bar
#: needs one pick behind it — zero picks would print a points-per-pick of nothing —
#: and no more: the count sits beside every slice, so the reader judges the sample
#: himself instead of being shown a blank.
COVERAGE_MINIMUM: int = 1


def role_minimum(role: str) -> int:
    """The overall bar for a role."""
    return HANDLER_MINIMUM if role == schema.ROLE_HANDLER_PREFIX else SCREENER_MINIMUM

def ball_columns(role: str, coverage: str | None = None) -> tuple[str, ...]:
    """The four figures that say what he did with the ball, in reading order.

    A pick is one possession handed to a player, and there are only so many things
    he can do with it: take the shot, give it up, create one for somebody else, or
    lose it. Those four are the card's headline figures on every pick view — the
    same four whichever coverage is on screen, so the card reads the same way
    throughout and points per pick, which says what came of it all, is the sentence
    above them rather than a fifth box.

    The second differs by role, because the two jobs differ. A ball handler either
    keeps the ball or passes out of the action; a screener barely ever passes out of
    one — the league median is one pick in eighty — so what matters once he does get
    it is whether he rolled to the rim or popped for three.
    """
    given_up = "only_pass_pick_pct" if role == schema.ROLE_HANDLER_PREFIX else "shot_rate_3pt"
    stems = ("shot_taken_pct", given_up, "assist_opportunity_pct", "turnover_rate")
    return tuple(schema.pick_column(role, stem, coverage=coverage) for stem in stems)


def _ball_table_columns(role: str, coverage: str | None = None) -> tuple[Column, ...]:
    """The same four as table columns, each gated on the picks it was counted from."""
    picks = (
        schema.picks_vs(role, coverage) if coverage else schema.total_picks(role)
    )
    return tuple(
        Column(key, PCT0 if key.endswith(("shot_taken_pct", "shot_rate_3pt")) else PCT1,
               sample=picks)
        for key in ball_columns(role, coverage)
    )


def _coverage_facet(role: str) -> Facet:
    """What the defence throws at him, and what he does with each of it.

    Two questions a scout asks together and this data answers separately: what he
    sees most, and what he punishes. The board can already be walked coverage by
    coverage, but that is six clicks to compare six numbers — here they sit on one
    figure, and the volume bar beside it says which of them he is actually asked.

    Nothing here is withheld for being thin. This is a card, not a ranking: nobody
    is placed against anybody, the picks behind each slice are printed next to it,
    and a coverage a player saw four times is a fact about him worth seeing.
    """
    coverages = schema.coverages_for(role)
    return Facet(
        title="What the defence does about it",
        caption="Share of his picks, by how the defence played the screen",
        breakdown=tuple(
            Segment(coverage.label, schema.coverage_share(role, coverage.suffix),
                    schema.picks_vs(role, coverage.suffix))
            for coverage in coverages
        ),
        comparison=tuple(
            Segment(coverage.label, schema.pick_column(role, "ppp", coverage=coverage.suffix),
                    schema.picks_vs(role, coverage.suffix), COVERAGE_MINIMUM)
            for coverage in coverages
        ),
    )


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
                    schema.picks_at(role, spot.suffix),
                    split_minimum(role_minimum(role), spot.suffix))
            for spot in schema.COURT_SPOTS
        ),
        comparison_fmt=DEC2,
        on_court=True,
        coverage=_coverage_facet(role),
    )


def _overall(role: str, key: str, label: str, title: str, description: str,
             quadrants: tuple[str, str], x: Axis, summary: str,
             extra: tuple[Column, ...], minimum: int) -> View:
    """The view of a role across every pick he was involved in."""
    picks = schema.total_picks(role)
    return View(
        key=key,
        label=label,
        title=title,
        description=description,
        x=x,
        y=Axis(schema.pick_column(role, "ppp"), "Points generated per pick", DEC2),
        threshold=Threshold(picks, "picks", minimum),
        columns=(
            Column(picks, INT),
            Column(schema.pick_column(role, "ppp"), DEC2, sample=picks, is_rank_basis=True),
            Column(schema.pick_column(role, "success_rate"), PCT1,
                   sample=picks, is_context=True),
            *_ball_table_columns(role),
            *extra,
        ),
        tiles=ball_columns(role),
        quadrants=quadrants,
        summary=summary,
    )


def _coverage_view(role: str, coverage: schema.Coverage) -> View:
    """The same role, restricted to the picks played one way by the defence."""
    picks = schema.picks_vs(role, coverage.suffix)
    ppp = schema.pick_column(role, "ppp", coverage=coverage.suffix)
    score = schema.pick_column(role, "score_rate", coverage=coverage.suffix)
    three_rate = schema.pick_column(role, "shot_rate_3pt", coverage=coverage.suffix)
    shot_rate = schema.pick_column(role, "shot_taken_pct", coverage=coverage.suffix)
    # A handler's four already say whether he gave the ball up; whether he pulled
    # from three when he kept it is the tell against an under, so it is added back.
    # A screener's four carry it, roll or pop being what he does with the ball.
    extra = (
        (Column(three_rate, PCT0, sample=picks),)
        if role == schema.ROLE_HANDLER_PREFIX
        else ()
    )

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
            f"picks against {coverage.label.lower()}",
            split_minimum(role_minimum(role), coverage.suffix),
        ),
        columns=(
            Column(picks, INT),
            Column(ppp, DEC2, sample=picks, is_rank_basis=True),
            Column(score, PCT1, sample=picks, is_context=True),
            *_ball_table_columns(role, coverage.suffix),
            *extra,
        ),
        tiles=ball_columns(role, coverage.suffix),
        quadrants=("Scores it himself", "Plays it out of the screen"),
        summary=(
            f"Against {coverage.label.lower()} he generates {{{ppp}}} points per pick "
            f"and scores on {{{score}}} of them himself."
        ),
    )


HANDLER = Lens(
    key="handler",
    label="Ball handler",
    dataset=schema.DATASET_PICKS,
    prefix_from=schema.total_picks(schema.ROLE_HANDLER_PREFIX),
    view_label="Coverage",
    caption="The player using the screen",
    profile=_profile(schema.ROLE_HANDLER_PREFIX),
    views=(
        _overall(
            schema.ROLE_HANDLER_PREFIX,
            key="handler_overall",
            minimum=HANDLER_MINIMUM,
            label="Every pick",
            title="Scoring it, or playing out of it",
            description=(
                "Right, he finishes the screen himself more often. Up, the possession "
                "produces more points — his own and those his pass created."
            ),
            x=Axis(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "shot_taken_pct"),
                   "Picks he finishes himself", PCT0),
            quadrants=("Scores it himself", "Plays it out of the screen"),
            # Where his pass goes when he gives it up: the roll man, or somebody
            # else. The one thing the four headline figures do not say about a
            # handler, and the question a scout asks about him first.
            extra=(
                Column(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "pass_to_screener_pct"),
                       PCT0, sample=schema.total_picks(schema.ROLE_HANDLER_PREFIX)),
                Column(schema.pick_column(schema.ROLE_HANDLER_PREFIX, "pass_to_other_pct"),
                       PCT0, sample=schema.total_picks(schema.ROLE_HANDLER_PREFIX)),
            ),
            summary=(
                "Generates {handler_ppp} points per pick, and {handler_success_rate} of "
                "his screens end well for the offence. He goes to the screener on "
                "{handler_pass_to_screener_pct} of them."
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
    prefix_from=schema.total_picks(schema.ROLE_SCREENER_PREFIX),
    view_label="Coverage",
    caption="The player setting the screen",
    profile=_profile(schema.ROLE_SCREENER_PREFIX),
    views=(
        _overall(
            schema.ROLE_SCREENER_PREFIX,
            key="screener_overall",
            minimum=SCREENER_MINIMUM,
            label="Every pick",
            title="Rolling, popping, or passing out of the short roll",
            description=(
                "Right, more of his shots out of the screen are threes — he pops rather "
                "than rolls. Up, the possession produces more points."
            ),
            x=Axis(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "shot_rate_3pt"),
                   "Shots out of the screen taken from three", PCT0),
            quadrants=("Pops and scores", "Rolls and finishes"),
            # An assist opportunity is a pass that produced a shot; an assist is one
            # that produced a made shot. Both are shown, because the first is his
            # doing and the second is partly his teammate's.
            extra=(
                Column(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "assist_rate"), PCT1,
                       sample=schema.total_picks(schema.ROLE_SCREENER_PREFIX)),
                Column(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "foul_pct"), PCT1,
                       sample=schema.total_picks(schema.ROLE_SCREENER_PREFIX)),
            ),
            summary=(
                "Generates {screener_ppp} points per pick, and {screener_success_rate} of "
                "his screens end well for the offence. He finds a teammate on "
                "{screener_assist_rate} of them."
            ),
        ),
        *(_coverage_view(schema.ROLE_SCREENER_PREFIX, coverage)
          for coverage in schema.SCREENER_COVERAGES),
    ),
)

PICK_LENSES: tuple[Lens, ...] = (HANDLER, SCREENER)
