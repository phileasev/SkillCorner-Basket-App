"""The board every page is built from: filters, plot, player card, table.

Both pages ask the same thing of the reader — pick a lens, narrow the population,
set a minimum, then read a plot, a card and a table. Writing that once means the
two pages cannot drift apart, and a third page inherits the whole behaviour for
the price of a lens.

Draw order matters. The containers are laid out first, the stored clicks are read
second, and only then is anything drawn — so the plot, the table and the card all
show the same player on the very first click.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core import catalogue, ranking, thresholds
from src.core.metrics import Lens
from src.data import schema
from src.ui import charts, filters, panel, selection, sorting, tables


def render(frames: dict[str, pd.DataFrame], lenses: tuple[Lens, ...], caption: str) -> None:
    """Draw a full board.

    Args:
        frames: the loaded population per dataset, keyed the way a lens names it.
        lenses: the lenses this page offers.
        caption: the sentence under the title saying what the page separates.
    """
    st.caption(caption)
    lens = filters.lens_picker(lenses)
    st.caption(lens.caption)

    # Containers are created in reading order and filled out of order.
    scope_slot = st.container(border=True)
    board = st.columns([1.6, 1], gap="medium")
    chart_slot = board[0].container(border=True)
    panel_slot = board[1].container(border=True)
    table_slot = st.container(border=True)

    with chart_slot:
        st.markdown(f"**{lens.label}**")
        view = filters.view_picker(lens)

    source = frames[lens.dataset]
    with scope_slot:
        scope = filters.scope_row(source, source)
        minimum, show_ineligible = filters.minimum_expander(source, view)

    # The scope bar's league is the pool every standing on this page is read
    # against — computed before the team and the name search narrow the view, so
    # searching for one man does not rank him against himself. The counts are
    # placed too, not only the rates: a season total is a fact, and where that fact
    # sits in the league is another one.
    pool_mask = thresholds.league_mask(source, scope)
    placed = ranking.add_percentiles(
        source,
        (schema.GAMES_PLAYED, *(key for _, key in tables.layout(view))),
        pool_mask,
    )
    pool = placed.loc[pool_mask]

    population = thresholds.apply_population(placed, scope)
    if population.empty:
        with table_slot:
            st.info("No player matches these filters.")
        return

    scored = ranking.flag_eligible(
        population, thresholds.eligibility_mask(population, view, minimum)
    )
    targets = tables.sort_targets(view)

    def table_key(sort_column: str, ascending: bool, generation: int, pinned: str | None) -> str:
        """Key identifying the exact slice, order and pin a table was drawn with.

        The pinned player is part of it: he sits on the first row, so every row
        index below him shifts when he changes. A stored click has to be read
        against the order it was made in, or it would point at his neighbour.
        """
        shape = f"{view.key}_{len(scored)}_{minimum}_{show_ineligible}"
        return f"table_{shape}_{sort_column}_{ascending}_{generation}_{pinned or ''}"

    previous = selection.current()
    stored_key = table_key(*sorting.order_by(view), selection.table_generation(), previous)
    resorted = sorting.apply_header_click(
        view, selection.columns_clicked(stored_key), targets, stored_key
    )

    sort_column, ascending = sorting.order_by(view)
    marked_column, _ = sorting.chosen(view)
    ordered = ranking.two_tier_sort(scored, sort_column, ascending=ascending)
    visible = ordered if show_ineligible else ordered[ordered[ranking.ELIGIBLE]]
    if visible.empty:
        with table_slot:
            st.info("Nobody clears this minimum. Lower it in the panel above.")
        return

    measured = int(visible[ranking.ELIGIBLE].sum())
    chart_key = f"scatter_{view.key}_{len(visible)}_{minimum}"

    # The order the table was drawn in last time, rebuilt rather than remembered:
    # a stored row index only means something against the rows it was clicked on.
    selection.sync(
        chart_key=chart_key,
        table_key=stored_key,
        names=ranking.pin_first(visible, schema.PLAYER_NAME, previous)[
            schema.PLAYER_NAME
        ].tolist(),
        adopt_rows=not resorted,
    )
    chosen = selection.current()
    render_key = table_key(sort_column, ascending, selection.table_generation(), chosen)

    # The loaded player is lifted to the top so his line is on screen without
    # hunting for it. He keeps his own single row — the table is never doubled —
    # and the order behind him is untouched.
    listed = ranking.pin_first(visible, schema.PLAYER_NAME, chosen)

    with chart_slot:
        st.caption(view.description)
        if view.caveat:
            st.info(view.caveat, icon=":material/info:")
        st.plotly_chart(
            charts.scatter(visible, view, chosen),
            width="stretch",
            on_select="rerun",
            selection_mode="points",
            key=chart_key,
            config=charts.CLICKABLE,
        )
        st.caption("Click a dot, or any line in the table, to load that player.")

    with table_slot:
        header, mode = st.columns([3, 1.4], vertical_alignment="center")
        with header:
            st.caption(
                f"{measured} players clear the minimum · {len(visible) - measured} below it, "
                "greyed out and held at the bottom whatever the order."
            )
        with mode:
            as_percentiles = filters.value_mode(view)

        tables.render(
            listed,
            view,
            key=render_key,
            sorted_label=sorting.label_of(marked_column, targets),
            marker=sorting.arrow(ascending),
            selected=chosen,
            as_percentiles=as_percentiles,
        )

        if as_percentiles:
            tables.percentile_key()

        note = f" · **{chosen}** is held on the first row while he is loaded." if chosen else ""
        st.caption(sorting.caption(view, targets) + note)

    with panel_slot:
        match = visible[visible[schema.PLAYER_NAME] == chosen] if chosen else visible.iloc[:0]
        if match.empty:
            panel.empty_state(visible, pool, view, out_of_scope=chosen)
        else:
            # The median lines come from the scope bar's league, like the
            # percentiles: a reference line read off the handful of players a team
            # filter leaves standing is not a league median.
            panel.card(match.iloc[0], view, catalogue.lens_of(view), pool, minimum)
