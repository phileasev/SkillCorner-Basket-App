"""Tests for the analytical core: denominators, eligibility, ranks and ordering.

No Streamlit widget is exercised here — only pure functions. `src.ui.tables` is
touched for its column layout alone, which is a data question (which column is
shown, and how many times) rather than a rendering one.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.core import (
    aggregate,
    catalogue,
    metrics,
    pick_views,
    profile,
    ranking,
    shortlist,
    thresholds,
)
from src.data import glossary, schema
from src.ui import columns, profile_charts, tables, theme


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
    """Every figure on a player card is wired to real columns, coverages included."""
    for lens in catalogue.LENSES:
        if lens.profile is None:
            continue
        frame = frames[lens.dataset]
        extra = lens.profile.coverage
        segments = (*lens.profile.breakdown, *lens.profile.comparison)
        if extra is not None:
            segments += (*extra.breakdown, *extra.comparison)
        for segment in segments:
            assert segment.value in frame.columns, f"{lens.key}: {segment.value}"
            assert segment.count in frame.columns, f"{lens.key}: {segment.count}"


def test_only_the_pick_lenses_read_a_coverage() -> None:
    """A shooter faces no defensive coverage; the facet is the pick lenses' own."""
    with_coverage = {
        lens.key
        for lens in catalogue.LENSES
        if lens.profile is not None and lens.profile.coverage is not None
    }
    assert with_coverage == {"handler", "screener"}


def test_coverage_shares_account_for_every_pick(picks: pd.DataFrame) -> None:
    """What makes a hundred-percent bar the right shape for them.

    The five coverages are exhaustive in practice — the lowest total observed is
    98% of a player's picks — so a stacked bar is reading a whole, not a sample of
    one. It also means the shares are derived rather than read: the file ships a
    share per spot on the floor and none per coverage.
    """
    for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX):
        regulars = picks[picks[schema.total_picks(role)] >= 50]
        shares = regulars[
            [schema.coverage_share(role, c.suffix) for c in schema.coverages_for(role)]
        ].sum(axis=1)

        assert shares.min() > 0.97, f"{role}: coverages miss too many picks"
        assert shares.max() <= 1.0001, f"{role}: coverages overlap"


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


def test_no_displayed_column_is_named_by_hand() -> None:
    """Every name on screen comes out of the data dictionary, or out of one map.

    `glossary.name` falls back to the raw column name when it knows nothing, which
    is the failure this catches: a header reading `derived_fouled_rate` means a
    computed column was added without being named beside the definitions.
    """
    named = [
        *(column.key for view in catalogue.all_views() for column in view.columns),
        *(view.threshold.key for view in catalogue.all_views()),
        *(axis.key for axis in profile.radar_axes()),
        *(option.key for option in shortlist.options()),
        *(column for _, column, _ in columns.catalogue_columns()),
    ]
    unnamed = sorted({key for key in named if glossary.name(key) == key})
    assert not unnamed, f"columns with no glossary or derived name: {unnamed}"


def test_a_derived_column_is_named_where_it_is_defined() -> None:
    """The two maps describing computed columns must not drift apart."""
    assert set(glossary.derived_names()) == set(glossary.DERIVED_DEFINITIONS)


def test_a_coverage_share_is_named_after_the_count_it_divides() -> None:
    """Ten split names not retyped: they are read off the counts in the glossary.

    `Ball Handler - Picks (vs Soft (Drop))` becomes `… Pick Share (vs Soft (Drop))`,
    so a share folds onto its own family exactly as the counts do.
    """
    for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX):
        for coverage in schema.coverages_for(role):
            share = glossary.name(schema.coverage_share(role, coverage.suffix))
            counted = glossary.name(schema.picks_vs(role, coverage.suffix))
            assert share == counted.replace(" - Picks (", " - Pick Share ("), share

            family = glossary.family(schema.coverage_share(role, coverage.suffix))
            assert family != share and share.startswith(family), family


def test_a_coverage_split_folds_onto_its_family() -> None:
    """The glossary writes the coverage in; that suffix is what groups the six."""
    handler_ppp = schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp")
    for coverage in schema.HANDLER_COVERAGES:
        split = schema.pick_column(handler_ppp.split("_", 1)[0], "ppp", coverage=coverage.suffix)
        assert glossary.name(split) != glossary.name(handler_ppp), split
        assert glossary.family(split) == glossary.name(handler_ppp), split

    # `vs Soft (Drop)` nests a bracket inside the bracket; it still comes off whole.
    soft = schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp", coverage="soft")
    assert glossary.family(soft) == glossary.name(
        schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp")
    )


def test_no_column_is_shown_twice_in_a_table() -> None:
    """`attempts` is both a volume and the denominator of eFG%; it appears once."""
    for view in catalogue.all_views():
        keys = [key for _, key in tables.layout(view)]
        labels = [label for label, _ in tables.layout(view)]
        assert len(keys) == len(set(keys)), f"{view.key}: column shown twice: {keys}"
        assert len(labels) == len(set(labels)), f"{view.key}: header used twice: {labels}"


def test_a_board_header_does_not_repeat_its_own_controls() -> None:
    """The lens names the role and the view names the coverage; a header need not.

    `Screener - Points Per Pick (vs Soft (Drop))` spends twenty-eight of its
    thirty-two characters repeating the two selectors directly above it, and seven
    of those across is a table the reader has to scroll sideways to read. What is
    taken out is still in the tooltip, which carries the glossary definition.
    """
    for lens in catalogue.LENSES:
        for view in lens.views:
            headers = [header for header, _ in tables.layout(view)]
            assert len(headers) == len(set(headers)), f"{view.key}: {headers}"

            for header in headers:
                assert lens.prefix == "" or not header.startswith(lens.prefix), header
                if "_vs_" in view.threshold.key:
                    assert "(vs " not in header, f"{view.key}: {header}"


def test_the_shortlist_keeps_the_names_whole() -> None:
    """Both roles are listed there, so the prefix is what tells them apart.

    Trimming it on the shortlist the way a board trims it would leave two columns
    called `Points Per Pick`, the second quietly overwriting the first in the table
    and in the export alike.
    """
    headers = {header for header, _, _ in columns.catalogue_columns()}
    for role, prefix in (
        (schema.ROLE_HANDLER_PREFIX, "Ball Handler - "),
        (schema.ROLE_SCREENER_PREFIX, "Screener - "),
    ):
        assert prefix + "Points Per Pick" in headers
        assert glossary.name(schema.pick_column(role, "ppp", coverage="switch")) in headers


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
    rate = glossary.name(schema.CONTESTED_THREE_PCT)
    assert placed[counts].equals(raw[counts]), "the shots behind a rate stay shots"
    assert not placed[rate].equals(raw[rate]), "the rate becomes a standing"
    assert placed[rate].dropna().between(0, 1).all()


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


def test_a_segment_median_is_taken_among_the_players_it_measured() -> None:
    """The reference line on a slice must not be dragged down by players with none.

    A player who never saw a coverage still carries a 0.00 in its column, so taken
    across everybody the median lands on the floor and anybody who ever faced one
    looks outstanding. The same rule the app applies to percentiles — measure on the
    population that was measured — applied to the reference line.
    """
    frame = pd.DataFrame({"value": [0.0, 0.0, 0.0, 0.9, 1.1], "count": [0, 1, 2, 30, 40]})
    segment = metrics.Segment("Blitz", "value", "count", 25)

    assert aggregate.league_median(frame, "value") == 0.0, "the trap, in miniature"
    assert aggregate.segment_medians(frame, (segment,))["value"] == pytest.approx(1.0)


def test_the_median_filter_bites_on_a_real_split(picks: pd.DataFrame) -> None:
    """And on the file itself, where the zeros are the majority for a rare coverage."""
    ppp = schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp", coverage="under")
    counted = schema.picks_vs(schema.ROLE_HANDLER_PREFIX, "under")
    segment = metrics.Segment("Under", ppp, counted, 25)

    assert aggregate.segment_medians(picks, (segment,))[ppp] > aggregate.league_median(
        picks, ppp
    )


def test_each_pick_role_opens_on_its_own_bar() -> None:
    """A screener sets screens all game; a handler runs the ones called for him.

    One bar for both would judge two different jobs on one scale of volume, so the
    overall view of each role opens where a rotation's worth of that role is
    measured — and neither is the other's number.
    """
    handler = catalogue.view_by_key("handler_overall").threshold
    screener = catalogue.view_by_key("screener_overall").threshold

    assert handler.default == pick_views.HANDLER_MINIMUM
    assert screener.default == pick_views.SCREENER_MINIMUM
    assert handler.default != screener.default


def test_a_slider_can_always_return_to_the_bar_it_opened_on() -> None:
    """One step for the whole app, so a default has to sit on one of its notches.

    A bar of eight, reachable from neither five nor ten, is a bar the reader loses
    the first time he nudges the control. Defaults under one step are the exception
    and are allowed: three picks against the blitz opens below the slider's first
    stop, and zero — every player, counts on show — is the way back from it.
    """
    for view in catalogue.all_views():
        default = view.threshold.default
        assert (
            default % metrics.MINIMUM_STEP == 0 or default < metrics.MINIMUM_STEP
        ), f"{view.key} opens on {default}, which its slider cannot return to"


def test_the_card_withholds_no_coverage(picks: pd.DataFrame) -> None:
    """One pick is enough to print what it returned, because the count is printed too.

    At a flat bar of twenty-five, not one player in the league would have been given
    a figure against the blitz or the ice — which reads as missing data rather than
    as a coverage Spain barely plays.
    """
    for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX):
        facet = catalogue.lens_by_key(role).profile.coverage
        assert {segment.min_count for segment in facet.comparison} == {
            pick_views.COVERAGE_MINIMUM
        }

        for rare in (c for c in schema.coverages_for(role) if c.rare):
            counted = picks[schema.picks_vs(role, rare.suffix)].fillna(0)
            assert (counted >= pick_views.COVERAGE_MINIMUM).any(), rare.label
            assert not (counted >= 25).any(), (
                f"{role} vs {rare.label}: the old flat bar left the whole league blank"
            )


def test_a_split_is_asked_for_the_share_of_a_season_the_whole_is(
    picks: pd.DataFrame,
) -> None:
    """The coverage bars are the role's bar cut to how often the league plays it.

    A flat twenty-five per coverage asked far more of a split than the board asks of
    the whole — a handler is measured from ten screens, yet needed twenty-five of
    them played one way. The shares are measured here rather than trusted, so the
    constants cannot go stale against the file.
    """
    league = picks[schema.total_picks(schema.ROLE_HANDLER_PREFIX)].fillna(0).sum()

    for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX):
        bar = pick_views.role_minimum(role)
        splits = [(c.suffix, schema.picks_vs(role, c.suffix)) for c in schema.coverages_for(role)]
        splits += [(s.suffix, schema.picks_at(role, s.suffix)) for s in schema.COURT_SPOTS]

        for suffix, column in splits:
            measured = picks[column].fillna(0).sum() / league
            assert measured == pytest.approx(pick_views.LEAGUE_SHARE[suffix], abs=0.002), (
                f"{column}: the file says {measured:.4f}"
            )
            expected = pick_views.split_minimum(bar, suffix)
            assert expected <= max(bar * measured, 1) + 1e-9, f"{column} asks for too much"
            assert expected % metrics.MINIMUM_STEP == 0 or expected == 1, column


def test_every_coverage_bar_came_down(picks: pd.DataFrame) -> None:
    """And the point of it: far more players carry a figure than before."""
    for role in (schema.ROLE_HANDLER_PREFIX, schema.ROLE_SCREENER_PREFIX):
        for coverage in schema.coverages_for(role):
            counted = picks[schema.picks_vs(role, coverage.suffix)].fillna(0)
            bar = pick_views.split_minimum(pick_views.role_minimum(role), coverage.suffix)
            assert bar <= 5, f"{role} vs {coverage.label} still opens at {bar}"
            assert int((counted >= bar).sum()) > int((counted >= 25).sum()), coverage.label


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


def test_a_criterion_is_the_bar_and_nothing_else(everyone: pd.DataFrame) -> None:
    """A bar filters on its own value, never on a second condition nobody typed.

    Asking for 40% from three used to require forty attempts as well, which is a
    reason a name could be missing that the reader had no way of seeing. What
    guards the sample now is the scope bar at the top of the page, where he can
    read it and move it.
    """
    metric = schema.CONTESTED_THREE_PCT
    bar = shortlist.Criterion(metric, at_least=True, value=0.4)
    passed = everyone[shortlist.mask(everyone, bar)]

    assert passed[metric].min() >= 0.4
    assert (passed[metric] >= 0.4).all()
    # Everybody at or above the bar is kept, whatever the sample behind it.
    assert len(passed) == int((everyone[metric] >= 0.4).sum())


def test_the_scope_bar_is_what_guards_the_sample(everyone: pd.DataFrame) -> None:
    """And it does the job the criterion used to do invisibly, in the open."""
    metric = schema.CONTESTED_THREE_PCT
    bar = shortlist.Criterion(metric, at_least=True, value=0.4)

    wide = thresholds.PopulationFilter(min_games=0, min_attempts=0)
    narrow = thresholds.PopulationFilter(min_games=15, min_attempts=metrics.SEASON_MINIMUM)

    loose = shortlist.apply(thresholds.apply_population(everyone, wide), (bar,))
    strict = shortlist.apply(thresholds.apply_population(everyone, narrow), (bar,))

    assert len(strict) < len(loose), "the scope bar has to bite"
    assert strict[schema.ATTEMPTS].min() >= metrics.SEASON_MINIMUM
    assert strict[schema.GAMES_PLAYED].min() >= 15


def test_criteria_stack(everyone: pd.DataFrame) -> None:
    shooting = shortlist.Criterion(schema.THREE_PT_PCT, True, 0.36)
    handling = shortlist.Criterion(
        schema.pick_column(schema.ROLE_HANDLER_PREFIX, "ppp"), True, 0.85
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
    """The selector is keyed on the title, so two metrics may never share one.

    The title is the glossary name alone. It already separates the roles — `Ball
    Handler -` against `Screener -` — but nothing guarantees the dictionary never
    reuses a name across two columns, and a clash would silently drop one metric
    out of the selector.
    """
    titles = [option.title for option in shortlist.options()]
    assert len(titles) == len(set(titles)), [t for t in titles if titles.count(t) > 1]


def test_a_metric_carries_its_splits_rather_than_repeating_itself() -> None:
    """One line per idea in the selector, the coverage picked beside it."""
    picks = [option for option in shortlist.options() if option.group == "Screener"]
    ppp = next(
        option
        for option in picks
        if option.label == glossary.name(schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp"))
    )

    assert len(ppp.variants) == 1 + len(schema.SCREENER_COVERAGES)
    assert ppp.variants[0][0] == "All"
    assert ppp.split_label == "Coverage"
    assert {name for name, _ in ppp.variants[1:]} == {
        coverage.label for coverage in schema.SCREENER_COVERAGES
    }


def test_every_variant_names_a_distinct_column() -> None:
    """The bug this replaced: one label standing for six different columns."""
    for option in shortlist.options():
        named = [column for _, column in option.variants]
        assert len(named) == len(set(named)), option.title


def test_season_totals_are_filed_apart_from_the_boards() -> None:
    """How many shots he took is a fact about volume, not about distance.

    The shot-distance board prints the total attempts for context and the
    contested one prints the threes; neither owns them. Filed under a board, a
    volume criterion would be hidden behind a question the reader is not asking.
    """
    by_key = {option.key: option for option in shortlist.options()}
    for key in (
        schema.GAMES_PLAYED,
        schema.ATTEMPTS,
        schema.TWO_ATTEMPTS,
        schema.THREE_ATTEMPTS,
    ):
        assert by_key[key].group == shortlist.GENERAL_GROUP, key
        assert by_key[key].denominator is None, key
        assert shortlist.describe(key).group == shortlist.GENERAL_GROUP, key


def test_a_season_total_is_claimed_once() -> None:
    """Claimed ahead of the lenses, so no board offers a second copy of it."""
    counted = [
        column
        for option in shortlist.options()
        for _, column in option.variants
        if column == schema.THREE_ATTEMPTS
    ]
    assert counted == [schema.THREE_ATTEMPTS]


def test_the_scope_bar_opens_on_a_rotation_player_who_shoots(everyone: pd.DataFrame) -> None:
    """One bar for the whole app, and it opens where every page used to open.

    Fifteen games and one shot per official game — the perimeter the boards started
    from and the two criteria the shortlist used to seed, now said once, at the top
    of every page, where moving it moves the whole site.
    """
    default = thresholds.PopulationFilter()
    assert default.min_games == thresholds.DEFAULT_MIN_GAMES
    assert default.min_attempts == metrics.SEASON_MINIMUM

    pool = everyone.loc[thresholds.league_mask(everyone, default)]
    assert pool[schema.GAMES_PLAYED].min() >= thresholds.DEFAULT_MIN_GAMES
    assert pool[schema.ATTEMPTS].min() >= metrics.SEASON_MINIMUM
    assert 0 < len(pool) < len(everyone)

    games_only = thresholds.PopulationFilter(min_attempts=0)
    assert len(pool) < int(thresholds.league_mask(everyone, games_only).sum()), (
        "the shooting bar has to bite on top of the games one"
    )


def test_the_scope_bar_ranks_against_the_league_not_against_one_team(
    everyone: pd.DataFrame,
) -> None:
    """Team and name search narrow what is on screen, never what it is measured against.

    A reader who types a name would otherwise be ranked against himself, and every
    standing in the app would describe a population of one.
    """
    team = everyone[schema.TEAM_NAME].dropna().iloc[0]
    scope = thresholds.PopulationFilter(team=team, name_query="a")

    pool = int(thresholds.league_mask(everyone, scope).sum())
    shown = len(thresholds.apply_population(everyone, scope))

    assert shown < pool, "the team filter must narrow the view"
    assert pool == int(
        thresholds.league_mask(everyone, thresholds.PopulationFilter()).sum()
    ), "but not the pool"


def test_a_shooting_minimum_is_one_attempt_per_official_game() -> None:
    """Stated per game, so the number can be read back rather than taken on trust.

    Every board that gates on a shot count uses it, which is what stops one view
    asking a hundred shots while its neighbour asks forty for the same confidence.
    It is rounded up onto a slider notch: a default the control cannot return to
    is a default the reader loses the moment he touches it.
    """
    per_game = metrics.SHOTS_PER_GAME * schema.REGULAR_SEASON_GAMES
    assert metrics.SEASON_MINIMUM % metrics.MINIMUM_STEP == 0
    assert per_game <= metrics.SEASON_MINIMUM < per_game + metrics.MINIMUM_STEP

    shot_counts = {
        view.threshold.key: view.threshold.default
        for view in catalogue.all_views()
        if catalogue.lens_of(view).dataset == schema.DATASET_SHOTS
    }
    assert set(shot_counts.values()) == {metrics.SEASON_MINIMUM}, shot_counts


def test_the_shortlist_still_blanks_what_a_board_would_blank(everyone: pd.DataFrame) -> None:
    """No minimum panel here any more, but a board's own floors still hold.

    Open 3PT% clears at ten open threes on its board; printing it here on three
    attempts would make the shortlist the one place a thin number gets through.
    """
    floors = columns._baseline_floors()
    assert schema.UNCONTESTED_THREE_PCT in floors

    count, wanted = floors[schema.UNCONTESTED_THREE_PCT]
    display, _ = columns.build(everyone)
    header = glossary.name(schema.UNCONTESTED_THREE_PCT)
    thin = everyone[count].fillna(0) < wanted

    assert thin.any(), "expected players under the floor to exist"
    assert display.loc[thin.values, header].isna().all()
    assert display.loc[~thin.values, header].notna().any()


def test_describe_names_the_split_it_came_from() -> None:
    described = shortlist.describe(
        schema.pick_column(schema.ROLE_SCREENER_PREFIX, "ppp", coverage="ice")
    )
    assert "Ice" in described.label
    assert described.group == "Screener"


def test_percentile_and_value_are_the_same_bar_from_two_sides(everyone: pd.DataFrame) -> None:
    metric = schema.CONTESTED_THREE_PCT
    for wanted in (0.25, 0.5, 0.9):
        value = shortlist.value_at_percentile(everyone, metric, wanted)
        assert shortlist.percentile_of_value(everyone, metric, value) == pytest.approx(
            wanted, abs=0.02
        )


def test_the_bar_is_read_against_the_scope_bars_league(everyone: pd.DataFrame) -> None:
    """Narrowing the league moves the percentile a criterion prints — and only that."""
    metric, value = schema.CONTESTED_THREE_PCT, 0.38
    scoped = thresholds.apply_population(everyone, thresholds.PopulationFilter())

    assert int(shortlist.pool(scoped, metric).sum()) < int(
        shortlist.pool(everyone, metric).sum()
    )
    assert shortlist.percentile_of_value(everyone, metric, value) != (
        shortlist.percentile_of_value(scoped, metric, value)
    )


def test_radar_places_every_axis_against_the_one_pool(everyone: pd.DataFrame) -> None:
    """One league for the whole app, the web included — but he is still only
    placed on a spoke he has the events for."""
    name = everyone.nlargest(1, schema.ATTEMPTS)[schema.PLAYER_NAME].iloc[0]
    scores = profile.radar_scores(everyone, name)

    assert len(scores) == len(profile.radar_axes())
    placed = scores.dropna(subset=["percentile"])
    assert placed["percentile"].between(0, 1).all()
    assert scores.loc[~scores["enough"], "percentile"].isna().all(), (
        "a player below an axis minimum carries no standing on it"
    )

    # The scale itself is the whole pool: the top scorer's shot-volume standing is
    # measured against everybody handed in, not against a sub-population.
    volume = scores.loc[scores["label"] == glossary.name(schema.ATTEMPTS), "percentile"]
    assert volume.iloc[0] == pytest.approx(1.0)


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
    placed = scores.loc[scores["label"].str.contains("Points Per Pick"), "percentile"]
    assert len(placed) == 2, "one spoke per role"
    assert placed.notna().all(), "both roles are placed for a player who plays both"


def test_spot_returns_keeps_each_share_with_its_own_value(everyone: pd.DataFrame) -> None:
    """The floor plan reads two segment lists side by side; they must line up.

    `breakdown` carries the share of picks set at a spot and `comparison` what that
    spot returned, and they are zipped by position. Reordering one of them would
    quietly print the middle's points per pick on the step-up.
    """
    lens = catalogue.lens_by_key("handler")
    row = everyone.nlargest(1, schema.HANDLER_PICKS).iloc[0]
    spots = profile.spot_returns(row, lens.profile)

    assert list(spots["spot"]) == [spot.label for spot in schema.COURT_SPOTS]
    for spot, segment in zip(spots.itertuples(), lens.profile.comparison):
        assert spot.ppp == row[segment.value]
        assert spot.picks == row[segment.count]
    assert spots["share"].sum() == pytest.approx(1.0, abs=0.01)


def test_every_spot_has_a_place_on_the_floor_plan() -> None:
    """A spot with no box drawn would vanish from the plan without a word."""
    from src.ui import profile_charts

    assert {spot.label for spot in schema.COURT_SPOTS} == set(profile_charts._SPOT_BOXES)
    for boxes in profile_charts._SPOT_BOXES.values():
        for x0, y0, x1, y1 in boxes:
            assert 0 <= x0 < x1 <= 50 and 0 <= y0 < y1 <= 40, (x0, y0, x1, y1)


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


def test_percentiles_are_measured_on_the_pool_handed_in() -> None:
    """One pool for the whole app: whoever the scope bar leaves standing.

    Not the players who clear the view's own bar. A standing that moved every time
    a slider moved was a number the reader could not carry from one screen to the
    next — and the grey row is what says the sample is thin, not a missing rank.
    """
    frame = ranking.flag_eligible(_tiny_frame(), _tiny_frame()["count"] >= 50)
    scored = ranking.add_percentiles(frame, ("metric",))
    column = ranking.percentile_of("metric")

    assert scored[column].notna().all(), "everybody in the pool is placed"
    assert scored.loc[2, column] == pytest.approx(1.0), "C really does hold the top value"
    assert scored.loc[1, column] == pytest.approx(0.25), "four players, he is last"


def test_a_narrower_pool_is_a_different_scale() -> None:
    """Which is the whole reason the pool is a parameter and not an assumption."""
    frame = _tiny_frame()
    inside = frame["count"] >= 50
    scored = ranking.add_percentiles(frame, ("metric",), inside)
    column = ranking.percentile_of("metric")

    assert pd.isna(scored.loc[2, column]), "C is outside this pool, so he is not placed"
    assert scored.loc[0, column] == pytest.approx(1.0), "and the scale is the three left"


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


def test_the_shot_chart_and_the_shot_menu_shade_a_distance_the_same_way() -> None:
    """Both figures sit on one card, so a distance must not change colour between them.

    The two use different zone conventions — the menu splits the floor four ways,
    the chart five, because it is the only one that separates a corner three from
    one above the break — but both are ordered outwards from the basket, so the
    ramp lines them up: rim palest in each, threes deepest in each.
    """
    tones = profile_charts._ZONE_TONE

    assert [tones[zone.label] for zone in schema.NBA_ZONES] == list(range(len(schema.NBA_ZONES)))
    assert len(set(tones.values())) == len(schema.NBA_ZONES), "no two zones share a tone"
    for palette in (theme.LIGHT, theme.DARK):
        assert len(palette.zones) >= len(schema.NBA_ZONES), "the ramp runs out of tones"
        # The menu takes the head of the same ramp, so the rim agrees on both.
        assert palette.zones[tones["Restricted area"]] == palette.zones[0]


def test_a_label_on_a_mark_is_read_against_the_mark() -> None:
    """Every ramp tone gets an ink that clears the WCAG bar for small text on it."""
    for palette in (theme.LIGHT, theme.DARK):
        for tone in palette.zones:
            ink = theme.ink_on(tone)
            lighter, darker = sorted(
                (theme._relative_luminance(tone), theme._relative_luminance(ink)), reverse=True
            )
            assert (lighter + 0.05) / (darker + 0.05) >= 4.5, f"{ink} on {tone}"
