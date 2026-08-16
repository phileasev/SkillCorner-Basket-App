"""Shot Quality Board — what shots a player takes, and how well he takes them.

Interface only: this file reads widgets, calls `src`, and hands the results to a
renderer. Every filter, ratio and ordering lives in `src.core`.

Draw order matters here. The containers are laid out first, the table's stored
clicks are read second, and only then is anything drawn — so the plot, the table
and the card all show the same player on the very first click.
"""

from __future__ import annotations

import streamlit as st

from src.core import ranking, thresholds
from src.data import loader, schema
from src.ui import charts, filters, panel, selection, sorting, tables

st.title("Shot Quality Board")
st.caption(
    "Every shooter takes a different menu of shots. This board separates what he "
    "takes from how well he takes it."
)

shots = loader.load_shot_profiles()
lens = filters.lens_picker()
st.caption(lens.caption)

# Containers are created in reading order and filled out of order.
scope_slot = st.container(border=True)
board = st.columns([1.6, 1], gap="medium")
chart_slot = board[0].container(border=True)
panel_slot = board[1].container(border=True)
table_slot = st.container(border=True)

with chart_slot:
    st.markdown(f"**{lens.label}**" if len(lens.views) > 1 else f"**{lens.views[0].title}**")
    view = filters.view_picker(lens)

with scope_slot:
    scope = filters.scope_row(shots)
    minimum, show_ineligible = filters.minimum_expander(shots, view)

population = thresholds.apply_population(shots, scope)
if population.empty:
    with table_slot:
        st.info("No player matches these filters.")
    st.stop()

flagged = ranking.flag_eligible(population, thresholds.eligibility_mask(population, view, minimum))
scored = ranking.add_percentiles(flagged, tuple(column.key for column in view.columns))

# Widgets are keyed to the slice they were drawn from: when the filters or the
# ordering change, a stored row index no longer describes the same player, so the
# inputs start over rather than quietly pointing at somebody else.
targets = tables.sort_targets(view)


def table_key(sort_column: str, ascending: bool, generation: int, pinned: str | None) -> str:
    """Key identifying the exact slice, order and pin a table was drawn with.

    The pinned player is part of it: he sits on the first row, so every row index
    below him shifts when he changes. A stored click has to be read against the
    order it was made in, or it would point at the player's neighbour.
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
    st.stop()

measured = int(visible[ranking.ELIGIBLE].sum())
chart_key = f"scatter_{view.key}_{len(visible)}_{minimum}"

# The order the table was drawn in last time, rebuilt rather than remembered: a
# stored row index only means something against the rows it was clicked on.
selection.sync(
    chart_key=chart_key,
    table_key=stored_key,
    names=ranking.pin_first(visible, schema.PLAYER_NAME, previous)[schema.PLAYER_NAME].tolist(),
    adopt_rows=not resorted,
)
chosen = selection.current()
render_key = table_key(sort_column, ascending, selection.table_generation(), chosen)

# The loaded player is lifted to the top so his line is on screen without hunting
# for it. He keeps his own single row — the table is never doubled — and the order
# behind him is untouched.
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
            f"{measured} players have enough shots · {len(visible) - measured} below the "
            "minimum, greyed out and held at the bottom whatever the order."
        )
    with mode:
        as_percentiles = filters.value_mode()

    tables.render(
        listed,
        view,
        key=render_key,
        sorted_label=sorting.label_of(marked_column, targets),
        marker=sorting.arrow(ascending),
        selected=chosen,
        as_percentiles=as_percentiles,
    )

    caption_col, reverse_col = st.columns([5, 1], vertical_alignment="center")
    with caption_col:
        note = f" · **{chosen}** is held on the first row while he is loaded." if chosen else ""
        st.caption(sorting.caption(view, targets) + note)
    with reverse_col:
        if st.button("Reverse", type="tertiary", width="stretch"):
            sorting.reverse(view)
            st.rerun()

with panel_slot:
    match = visible[visible[schema.PLAYER_NAME] == chosen] if chosen else visible.iloc[:0]
    if match.empty:
        panel.empty_state(visible, view, out_of_scope=chosen)
    else:
        panel.card(match.iloc[0], view, visible)
