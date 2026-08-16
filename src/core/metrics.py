"""The vocabulary the views are written in, and what each displayed rate is made of.

One rule drives this file: every rate the interface shows names the count it was
computed from (`DENOMINATORS`), so a minimum can be applied to that count and
never to games played. The views themselves live in `src.core.catalogue`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.data import schema

#: Format keys interpreted by `src.ui.format`. Plain strings, so this module
#: stays free of any interface dependency.
PCT1: str = "pct1"
PCT0: str = "pct0"
INT: str = "int"
DEC1: str = "dec1"
DEC2: str = "dec2"


@dataclass(frozen=True)
class Column:
    """One column of a league table."""

    key: str
    label: str
    fmt: str
    sample: str | None = None
    min_sample: int = 0
    is_rank_basis: bool = False
    is_context: bool = False


@dataclass(frozen=True)
class Axis:
    """One axis of a scatter plot."""

    key: str
    label: str
    fmt: str


@dataclass(frozen=True)
class Threshold:
    """The count a view's headline rate is computed from."""

    key: str
    label: str
    default: int


@dataclass(frozen=True)
class View:
    """A single question, and everything needed to answer it on screen."""

    key: str
    label: str
    title: str
    description: str
    x: Axis
    y: Axis
    threshold: Threshold
    columns: tuple[Column, ...]
    quadrants: tuple[str, str]
    summary: str
    #: Headline figures on the player card, in order. Defaults to the metric the
    #: view is built around plus the column that gives it meaning.
    tiles: tuple[str, ...] = ()
    caveat: str = ""

    @property
    def rank_column(self) -> Column:
        """The column ranks are computed on: the one the view is built around."""
        return next(c for c in self.columns if c.is_rank_basis)

    @property
    def context_column(self) -> Column:
        """The column that gives the headline number its meaning by comparison."""
        return next(c for c in self.columns if c.is_context)

    @property
    def tile_columns(self) -> tuple[Column, ...]:
        """The columns shown as headline figures on the player card."""
        if not self.tiles:
            return (self.rank_column, self.context_column)
        by_key = {column.key: column for column in self.columns}
        return tuple(by_key[key] for key in self.tiles)


@dataclass(frozen=True)
class Segment:
    """One slice of a player's profile: a share, or a value with its own count."""

    label: str
    value: str
    count: str
    min_count: int = 0


@dataclass(frozen=True)
class Profile:
    """The two figures every player card carries, whatever the page.

    `breakdown` is a share of the player's own events, so it needs no minimum and
    holds for everyone. `comparison` is a value per slice, gated slice by slice on
    its own count and read against the league median.
    """

    breakdown_title: str
    breakdown_caption: str
    breakdown: tuple[Segment, ...]
    comparison_title: str
    comparison_caption: str
    comparison: tuple[Segment, ...]
    comparison_fmt: str = PCT1


@dataclass(frozen=True)
class Lens:
    """A group of views answering the same question from one angle."""

    key: str
    label: str
    caption: str
    views: tuple[View, ...] = field(default_factory=tuple)
    profile: Profile | None = None
    #: Which of the two files the lens reads. Decides what a page loads.
    dataset: str = schema.DATASET_SHOTS
    #: What the views inside this lens are, in the reader's words.
    view_label: str = "View"


#: Every displayed rate, mapped to the count it is computed from. The minimum a
#: user sets applies to this count — never to games played.
DENOMINATORS: dict[str, str] = {
    schema.EFG: schema.ATTEMPTS,
    schema.POINTS_PER_SHOT: schema.ATTEMPTS,
    schema.THREE_PT_PCT: schema.THREE_ATTEMPTS,
    schema.CONTESTED_EFG: schema.CONTESTED_ATTEMPTS,
    schema.UNCONTESTED_EFG: schema.UNCONTESTED_ATTEMPTS,
    schema.CONTESTED_TWO_PCT: schema.CONTESTED_TWO_ATTEMPTS,
    schema.UNCONTESTED_TWO_PCT: schema.UNCONTESTED_TWO_ATTEMPTS,
    schema.CONTESTED_THREE_PCT: schema.CONTESTED_THREE_ATTEMPTS,
    schema.UNCONTESTED_THREE_PCT: schema.UNCONTESTED_THREE_ATTEMPTS,
    schema.OFF_DRIBBLE_EFG: schema.OFF_DRIBBLE_ATTEMPTS,
    schema.CATCH_SHOOT_EFG: schema.CATCH_SHOOT_ATTEMPTS,
    schema.CONTESTED_RATE: schema.ATTEMPTS,
    schema.OFF_DRIBBLE_RATE: schema.ATTEMPTS,
    schema.CONTESTED_TWO_RATE: schema.TWO_ATTEMPTS,
    schema.CONTESTED_THREE_RATE: schema.THREE_ATTEMPTS,
    schema.ASSISTED_SHARE: schema.MADES,
    schema.MIDRANGE_RATE: schema.ATTEMPTS,
    schema.THREE_PA_RATE: schema.ATTEMPTS,
    schema.FOULED_RATE: schema.ATTEMPTS,
    **{zone.made_pct: zone.attempts for zone in schema.SHOT_ZONES},
    **{zone.attempt_rate: schema.ATTEMPTS for zone in schema.SHOT_ZONES},
}


def _pick_denominators() -> dict[str, str]:
    """Every pick rate mapped to the picks it was computed from.

    Generated rather than typed: the picks file repeats the same metric stems for
    each role, each coverage and each spot on the floor, so the regularity does
    the work and only the stems have to be listed.
    """
    stems = (
        "ppp",
        "score_rate",
        "turnover_rate",
        "success_rate",
        "shot_taken_pct",
        "assist_rate",
        "assist_opportunity_rate",
        "pass_to_screener_pct",
        "shot_rate_2pt",
        "shot_rate_3pt",
        "foul_pct",
        "points_per_shot_in_pick",
    )
    roles = (
        (schema.ROLE_HANDLER_PREFIX, schema.HANDLER_COVERAGES),
        (schema.ROLE_SCREENER_PREFIX, schema.SCREENER_COVERAGES),
    )

    mapping: dict[str, str] = {}
    for role, coverages in roles:
        overall = schema.total_picks(role)
        for stem in stems:
            mapping[schema.pick_column(role, stem)] = overall
            for coverage in coverages:
                mapping[schema.pick_column(role, stem, coverage=coverage.suffix)] = (
                    schema.picks_vs(role, coverage.suffix)
                )
            for spot in schema.COURT_SPOTS:
                mapping[schema.pick_column(role, stem, spot=spot.suffix)] = (
                    schema.picks_at(role, spot.suffix)
                )
        # A share of his picks is measured against all of them, wherever it is set.
        for spot in schema.COURT_SPOTS:
            mapping[schema.pick_column(role, "pick_rate", spot=spot.suffix)] = overall

    return mapping


DENOMINATORS.update(_pick_denominators())
