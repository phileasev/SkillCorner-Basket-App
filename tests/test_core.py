"""Tests for the analytical core: denominators, eligibility, ranks and ordering.

No Streamlit widget is exercised here — only pure functions. `src.ui.tables` is
touched for its column layout alone, which is a data question (which column is
shown, and how many times) rather than a rendering one.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.core import aggregate, catalogue, metrics, profile, ranking, shortlist, thresholds
from src.data import glossary, schema
from src.ui import tables


@pytest.fixture(scope="module")
def shots() -> pd.DataFrame:
    """The real shooting file, with derived columns attached."""
    frame = pd.read_csv(schema.SHOTS_FILE)
    picks = pd.read_csv(schema.PICKS_FILE)[
        [schema.PLAYER_ID, schema.HANDLER_PICKS, schema.SCREENER_PICKS]
    ]
    return aggregate.derive_shot_features(frame.merge(picks, on=schema.PLAYER_ID, how="left"))


@pytest.fixture(scope="module")
def picks() -> pd.DataFrame:
    """The real pick-and-roll file, with derived columns attached."""
    return aggregate.derive_pick_features(pd.read_csv(schema.PICKS_FILE))


@pytest.fixture(scope="module")
def frames(shots: pd.DataFrame, picks: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Each file, keyed the way a lens names it."""
    return {schema.DATASET_SHOTS: shots, schema.DATASET_PICKS: picks}


def _frame_for(view: catalogue.View, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return frames[catalogue.lens_of(view).dataset]


# --- the catalogue must be wired to columns that exist ----------------------


def test_every_denominator_exists_in_the_data(frames: dict[str, pd.DataFrame]) -> None:
    """A rate whose denominator is not in either file would be filtered on nothing."""
    known = set().union(*(frame.columns for frame in frames.values()))
    missing = {
        metric: denominator
        for metric, denominator in metrics.DENOMINATORS.items()
        if denominator not in known
    }
    assert not missing, f"denominators absent from both files: {missing}"


def test_every_displayed_metric_exists_in_the_data(frames: dict[str, pd.DataFrame]) -> None:
    for view in catalogue.all_views():
        frame = _frame_for(view, frames)
        for column in (*[c.key for c in view.columns], view.x.key, view.y.key):
            assert column in frame.columns, f"{view.key}: unknown column {column}"


def test_every_profile_segment_exists_in_the_data(frames: dict[str, pd.DataFrame]) -> None:
    """The two figures on a player card are wired to real columns."""
    for lens in catalogue.LENSES:
        if lens.profile is None:
            continue
        frame = frames[lens.dataset]
        for segment in (*lens.profile.breakdown, *lens.profile.comparison):
            assert segment.value in frame.columns, f"{lens.key}: {segment.value}"
            assert segment.count in frame.columns, f"{lens.key}: {segment.count}"


def test_every_view_threshold_is_a_count_column(frames: dict[str, pd.DataFrame]) -> None:
    for view in catalogue.all_views():
        frame = _frame_for(view, frames)
        column = view.threshold.key
        assert column in frame.columns, f"{view.key}: unknown threshold column {column}"
        assert frame[column].dropna().ge(0).all()


def test_rate_columns_declare_their_denominator() -> None:
    """Any rate a view displays must be listed in DENOMINATORS, with no silent fallback."""
    rates = {
        column.key
        for view in catalogue.all_views()
        for column in view.columns
        if column.fmt in (metrics.PCT0, metrics.PCT1)
    }
    assert rates <= set(metrics.DENOMINATORS), rates - set(metrics.DENOMINATORS)


def test_each_view_has_exactly_one_rank_basis() -> None:
    for view in catalogue.all_views():
        bases = [c for c in view.columns if c.is_rank_basis]
        assert len(bases) == 1, f"{view.key} declares {len(bases)} rank columns"


def test_each_view_has_exactly_one_context_column() -> None:
    for view in catalogue.all_views():
        contexts = [c for c in view.columns if c.is_context]
        assert len(contexts) == 1, f"{view.key} declares {len(contexts)} context columns"
        assert not contexts[0].is_rank_basis, f"{view.key}: context repeats the headline"


def test_every_displayed_column_has_a_definition() -> None:
    """A column with no definition would leave its tooltip silently empty."""
    for view in catalogue.all_views():
        for column in view.columns:
            assert glossary.definition(column.key), f"{view.key}: {column.key} undocumented"


def test_no_column_is_shown_twice_in_a_table() -> None:
    """`attempts` is both a volume and the denominator of eFG%; it appears once."""
    for view in catalogue.all_views():
        keys = [key for _, key in tables.layout(view)]
        labels = [label for label, _ in tables.layout(view)]
        assert len(keys) == len(set(keys)), f"{view.key}: column shown twice: {keys}"
        assert len(labels) == len(set(labels)), f"{view.key}: header used twice: {labels}"


def test_every_rate_shows_the_count_behind_it() -> None:
    """A percentage is never printed without its sample size somewhere in the row."""
    for view in catalogue.all_views():
        shown = {key for _, key in tables.layout(view)}
        for column in view.columns:
            if column.fmt in (metrics.PCT0, metrics.PCT1) and column.sample:
                assert column.sample in shown, f"{view.key}: {column.key} hides its count"


def test_percentile_mode_leaves_counts_alone(shots: pd.DataFrame) -> None:
    """Swapping to standings must not swallow the sample sizes."""
    view = catalogue.view_by_key("contest_three")
    frame = ranking.add_percentiles(
        ranking.flag_eligible(shots, shots[view.threshold.key] >= 40),
        tuple(column.key for column in view.columns),
    )
    raw, _ = tables.build(frame, view, as_percentiles=False)
    placed, _ = tables.build(frame, view, as_percentiles=True)

    counts = tables.sample_label(schema.CONTESTED_THREE_ATTEMPTS)
    assert placed[counts].equals(raw[counts]), "the shots behind a rate stay shots"
    assert not placed["Guarded 3PT%"].equals(raw["Guarded 3PT%"]), "the rate becomes a standing"
    assert placed["Guarded 3PT%"].dropna().between(0, 1).all()


def test_midrange_share_sums_the_two_middle_zones(shots: pd.DataFrame) -> None:
    """Not 100% minus rim minus three: the four zones only cover ~97% of attempts."""
    regulars = shots[shots[schema.ATTEMPTS] >= 100]
    expected = regulars[schema.SHOT_ZONES_MIDRANGE[0]] + regulars[schema.SHOT_ZONES_MIDRANGE[1]]
    assert regulars[schema.MIDRANGE_RATE].equals(expected)

    leftover = 1 - regulars[[zone.attempt_rate for zone in schema.SHOT_ZONES]].sum(axis=1)
    assert leftover.max() > 0.05, "some attempts fall outside the four zones; do not subtract"


def test_shot_distance_is_converted_out_of_feet(shots: pd.DataFrame) -> None:
    """The glossary says metres; the values are feet. Guard the conversion.

    Among regular shooters the deepest average lands on the FIBA arc (6.75 m) and
    the shallowest on a layup. Read as metres the same figures would put the whole
    league beyond half court.
    """
    regulars = shots[shots[schema.ATTEMPTS] >= 100]
    metres = regulars[schema.SHOT_DISTANCE_METRES]

    assert metres.max() == pytest.approx(6.75, abs=0.05), "the deepest shooter sits on the arc"
    assert 1.0 < metres.min() < 1.5, "the most rim-bound big averages a layup"
    assert regulars[schema.AVG_SHOT_DISTANCE].max() > 20, "the raw column is left in feet"


# --- derived columns ---------------------------------------------------------


def test_safe_ratio_returns_missing_on_zero_denominator() -> None:
    result = aggregate.safe_ratio(pd.Series([4, 7]), pd.Series([8, 0]))
    assert result.iloc[0] == pytest.approx(0.5)
    assert pd.isna(result.iloc[1])


def test_role_falls_back_to_screener_without_pick_data() -> None:
    frame = pd.DataFrame(
        {
            schema.CONTESTED_TWO_ATTEMPTS: [1],
            schema.TWO_ATTEMPTS: [2],
            schema.CONTESTED_THREE_ATTEMPTS: [1],
            schema.THREE_ATTEMPTS: [2],
            schema.ASSISTED_SHOTS: [1],
            schema.MADES: [2],
            schema.AVG_SHOT_DISTANCE: [10.0],
            schema.FOULED_FGA: [1],
            schema.ATTEMPTS: [10],
            schema.SHOT_ZONES_MIDRANGE[0]: [0.2],
            schema.SHOT_ZONES_MIDRANGE[1]: [0.1],
            schema.HANDLER_PICKS: [pd.NA],
            schema.SCREENER_PICKS: [pd.NA],
        }
    )
    out = aggregate.derive_shot_features(frame)
    assert out[schema.PRIMARY_ROLE].iloc[0] == schema.ROLE_HANDLER


# --- two-stage filtering -----------------------------------------------------


def test_population_stage_only_touches_scope(shots: pd.DataFrame) -> None:
    scoped = thresholds.apply_population(shots, thresholds.PopulationFilter(min_games=20))
    assert scoped[schema.GAMES_PLAYED].min() >= 20
    assert len(scoped) < len(shots)


def test_eligibility_uses_the_view_denominator_not_games(shots: pd.DataFrame) -> None:
    """A full season of games must not, on its own, make a split trustworthy."""
    view = catalogue.view_by_key("contest_three")
    played_a_lot = shots[shots[schema.GAMES_PLAYED] >= 25]
    mask = thresholds.eligibility_mask(played_a_lot, view, 40)
    assert (~mask).any(), "expected regulars with too few guarded threes to judge"
    assert played_a_lot.loc[mask, view.threshold.key].min() >= 40


def test_slider_bounds_come_from_the_observed_maximum(shots: pd.DataFrame) -> None:
    view = catalogue.view_by_key("contest_three")
    low, high = thresholds.slider_bounds(shots, view)
    assert low == 0
    assert high == int(shots[view.threshold.key].max())


def test_sample_mask_is_open_when_no_floor_is_set(shots: pd.DataFrame) -> None:
    mask = thresholds.sample_mask(shots, schema.ATTEMPTS, 0)
    assert mask.all()


# --- the shortlist -----------------------------------------------------------


@pytest.fixture(scope="module")
def everyone(shots: pd.DataFrame, picks: pd.DataFrame) -> pd.DataFrame:
    """Both files on one row per player, the way the shortlist reads them."""
    shared = [c for c in picks.columns if c in shots.columns and c != schema.PLAYER_ID]
    return shots.merge(picks.drop(columns=shared), on=schema.PLAYER_ID, how="inner")


def test_a_criterion_filters_on_its_sample_as_well_as_its_value(everyone: pd.DataFrame) -> None:
    """The whole point: a percentage on five shots must not clear a bar."""
    metric, denominator = schema.CONTESTED_THREE_PCT, schema.CONTESTED_THREE_ATTEMPTS
    loose = shortlist.Criterion(metric, at_least=True, value=0.4, minimum=0)
    strict = shortlist.Criterion(metric, at_least=True, value=0.4, minimum=40)

    passed_loose = everyone[shortlist.mask(everyone, loose)]
    passed_strict = everyone[shortlist.mask(everyone, strict)]

    assert len(passed_strict) < len(passed_loose), "the sample requirement must bite"
    assert passed_strict[denominator].min() >= 40
    assert passed_loose[denominator].min() < 40, "somebody clears it on a handful of shots"


def test_criteria_stack(everyone: pd.DataFrame) -> None:
    shooting = shortlist.Criterion(schema.THREE_PT_PCT, True, 0.36, 100)
    handling = shortlist.Criterion(
        schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp"), True, 0.85, 100
    )
    both = shortlist.apply(everyone, (shooting, handling))

    assert len(both) <= len(shortlist.apply(everyone, (shooting,)))
    assert both[schema.THREE_PT_PCT].min() >= 0.36
    assert both[schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp")].min() >= 0.85


def test_every_filterable_metric_exists(everyone: pd.DataFrame) -> None:
    for option in shortlist.options():
        assert option.key in everyone.columns, option.key
        if option.denominator:
            assert option.denominator in everyone.columns, option.denominator


def test_filterable_titles_are_unique() -> None:
    """Every coverage view repeats the same column labels; the title must separate them.

    Without the split in the title, "Screener - Finishes himself" names six
    different columns and a selector keyed on it silently picks one of them.
    """
    titles = [option.title for option in shortlist.options()]
    assert len(titles) == len(set(titles)), [t for t in titles if titles.count(t) > 1]


def test_a_metric_carries_its_splits_rather_than_repeating_itself() -> None:
    """One line per idea in the selector, the coverage picked beside it."""
    picks = [option for option in shortlist.options() if option.group == "Screener"]
    ppp = next(option for option in picks if option.label == "Points per pick")

    assert len(ppp.variants) == 1 + len(schema.SCREENER_COVERAGES)
    assert ppp.variants[0][0] == "All"
    assert ppp.split_label == "Coverage"
    assert {name for name, _ in ppp.variants[1:]} == {
        coverage.label for coverage in schema.SCREENER_COVERAGES
    }


def test_every_variant_names_a_distinct_column() -> None:
    """The bug this replaced: one label standing for six different columns."""
    for option in shortlist.options():
        columns = [column for _, column in option.variants]
        assert len(columns) == len(set(columns)), option.title


def test_describe_names_the_split_it_came_from() -> None:
    described = shortlist.describe(
        schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp", coverage="ice")
    )
    assert "Ice" in described.label
    assert described.group == "Screener"


def test_percentile_and_value_are_the_same_bar_from_two_sides(everyone: pd.DataFrame) -> None:
    metric, minimum = schema.CONTESTED_THREE_PCT, 40
    for wanted in (0.25, 0.5, 0.9):
        value = shortlist.value_at_percentile(everyone, metric, minimum, wanted)
        assert shortlist.percentile_of_value(everyone, metric, minimum, value) == pytest.approx(
            wanted, abs=0.02
        )


def test_the_bar_is_read_against_the_pool_it_filters_on(everyone: pd.DataFrame) -> None:
    """Raising the events required changes the pool, so it changes the percentile."""
    metric, value = schema.CONTESTED_THREE_PCT, 0.38
    loose = shortlist.percentile_of_value(everyone, metric, 0, value)
    strict = shortlist.percentile_of_value(everyone, metric, 40, value)

    assert int(shortlist.pool(everyone, metric, 40).sum()) < int(
        shortlist.pool(everyone, metric, 0).sum()
    )
    assert loose != strict


def test_radar_places_each_axis_in_its_own_pool(everyone: pd.DataFrame) -> None:
    """A spoke gated on guarded shots is not scaled by players who barely take any."""
    name = everyone.nlargest(1, schema.ATTEMPTS)[schema.PLAYER_NAME].iloc[0]
    scores = profile.radar_scores(everyone, name)

    assert len(scores) == len(profile.radar_axes())
    placed = scores.dropna(subset=["percentile"])
    assert placed["percentile"].between(0, 1).all()
    assert scores.loc[~scores["enough"], "percentile"].isna().all(), (
        "a player below an axis minimum carries no standing on it"
    )


def test_radar_carries_both_pick_roles(everyone: pd.DataFrame) -> None:
    """A player with 59 handler picks and 55 screener picks is neither one nor the other."""
    keys = {axis.key for axis in profile.radar_axes()}
    assert schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp") in keys
    assert schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp") in keys

    both = everyone[
        (everyone[schema.total_picks(schema.ROLE_HANDLER_PREFIX)] >= profile.PICK_MINIMUM)
        & (everyone[schema.total_picks(schema.ROLE_SCREENER_PREFIX)] >= profile.PICK_MINIMUM)
    ]
    assert not both.empty, "some players really do play both roles"

    scores = profile.radar_scores(everyone, both[schema.PLAYER_NAME].iloc[0])
    placed = scores.loc[scores["label"].str.contains("points per pick"), "percentile"]
    assert placed.notna().all(), "both roles are placed for a player who plays both"


def test_nba_zone_accuracy_is_computed_not_read(everyone: pd.DataFrame) -> None:
    """These zones ship attempts and makes but no percentage; it has to be derived."""
    row = everyone.nlargest(1, schema.ATTEMPTS).iloc[0]
    zones = profile.zone_accuracy(row)

    assert list(zones["zone"]) == [zone.label for zone in schema.NBA_ZONES]
    computed = zones["mades"] / zones["attempts"].replace(0, pd.NA)
    assert zones["accuracy"].round(6).equals(computed.astype(float).round(6))
    for zone in schema.NBA_ZONES:
        assert f"{zone.attempts}_percentage" not in everyone.columns


def test_zone_accuracy_is_missing_rather_than_zero() -> None:
    row = pd.Series({zone.attempts: 0 for zone in schema.NBA_ZONES} |
                    {zone.mades: 0 for zone in schema.NBA_ZONES})
    assert profile.zone_accuracy(row)["accuracy"].isna().all()


# --- ranking -----------------------------------------------------------------


def _tiny_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            schema.PLAYER_NAME: ["A", "B", "C", "D"],
            "metric": [0.60, 0.40, 0.95, 0.50],
            "count": [100, 100, 5, 100],
        }
    )


def test_eligible_flag_marks_the_measured_players() -> None:
    frame = _tiny_frame()
    flagged = ranking.flag_eligible(frame, frame["count"] >= 50)
    assert flagged[ranking.ELIGIBLE].tolist() == [True, True, False, True]


def test_percentiles_are_computed_on_eligible_players_only() -> None:
    """A small-sample player is placed on no scale, and stretches nobody else's."""
    frame = ranking.flag_eligible(_tiny_frame(), _tiny_frame()["count"] >= 50)
    scored = ranking.add_percentiles(frame, ("metric",))
    column = ranking.percentile_of("metric")

    assert pd.isna(scored.loc[2, column]), "C has 5 events and sits on no scale"
    assert scored.loc[0, column] == pytest.approx(1.0), "the best eligible value tops the scale"
    assert scored.loc[1, column] == pytest.approx(1 / 3), "three eligible players, he is last"


def test_percentiles_ignore_the_ineligible_when_scaling() -> None:
    """C holds the highest raw value; including him would push everyone down."""
    frame = ranking.flag_eligible(_tiny_frame(), _tiny_frame()["count"] >= 50)
    scored = ranking.add_percentiles(frame, ("metric",))
    top = scored.loc[0, ranking.percentile_of("metric")]

    assert top == pytest.approx(1.0)
    assert scored.loc[0, "metric"] < scored.loc[2, "metric"], "C really is higher, and excluded"


def test_two_tier_sort_puts_eligible_players_first() -> None:
    frame = ranking.flag_eligible(_tiny_frame(), _tiny_frame()["count"] >= 50)
    ordered = ranking.two_tier_sort(frame, "metric")

    assert ordered[schema.PLAYER_NAME].tolist() == ["A", "D", "B", "C"]


def test_two_tier_sort_orders_within_each_group() -> None:
    frame = _tiny_frame()
    frame.loc[4] = ["E", 0.99, 1]
    ordered = ranking.two_tier_sort(ranking.flag_eligible(frame, frame["count"] >= 50), "metric")

    ineligible = ordered[~ordered[ranking.ELIGIBLE]][schema.PLAYER_NAME].tolist()
    assert ineligible == ["E", "C"], "the ineligible tail is sorted too"


def test_pin_first_lifts_one_row_and_leaves_the_rest_alone() -> None:
    """The loaded player sits on the first row; nobody else moves relative to anybody."""
    frame = ranking.two_tier_sort(
        ranking.flag_eligible(_tiny_frame(), _tiny_frame()["count"] >= 50), "metric"
    )
    pinned = ranking.pin_first(frame, schema.PLAYER_NAME, "B")

    assert pinned[schema.PLAYER_NAME].tolist() == ["B", "A", "D", "C"]
    rest = pinned[schema.PLAYER_NAME].tolist()[1:]
    assert rest == [name for name in frame[schema.PLAYER_NAME] if name != "B"]


def test_pin_first_is_a_no_op_without_a_selection() -> None:
    frame = ranking.two_tier_sort(
        ranking.flag_eligible(_tiny_frame(), _tiny_frame()["count"] >= 50), "metric"
    )
    assert ranking.pin_first(frame, schema.PLAYER_NAME, None).equals(frame)
    assert ranking.pin_first(frame, schema.PLAYER_NAME, "nobody").equals(frame)


def test_two_tier_sort_holds_whatever_column_is_chosen() -> None:
    """Sorting on any column keeps the greyed players underneath."""
    frame = ranking.flag_eligible(_tiny_frame(), _tiny_frame()["count"] >= 50)
    for ascending in (False, True):
        for column in ("metric", "count", schema.PLAYER_NAME):
            ordered = ranking.two_tier_sort(frame, column, ascending=ascending)
            flags = ordered[ranking.ELIGIBLE].tolist()
            assert flags == sorted(flags, reverse=True), f"{column} asc={ascending}"
