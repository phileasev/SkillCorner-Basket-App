"""Shortlist — build a search out of stacked criteria, then open a player in place.

Interface only: the criteria engine and every profile figure live in `src.core`.
"""

from __future__ import annotations

import streamlit as st

from src.core import ranking, shortlist, thresholds
from src.data import loader, schema
from src.ui import (
    columns,
    criteria,
    detail,
    filters,
    results,
    selection,
    sorting,
    tracking,
)

st.title("Shortlist")
st.caption(
    "Set the bars a player has to clear, then open anyone on the list to see what "
    "the two files say about him."
)

everyone = loader.load_all_profiles()

# The same scope bar the boards carry, and the same answers: it is one working
# dataset for the whole app, so a reader who narrowed the league on a board finds
# it narrowed here. The criteria below sit on top of it — the bar says who counts
# as a league player, a criterion says which of them he is looking for.
with st.container(border=True):
    scope = filters.scope_row(everyone, everyone)

pool = everyone.loc[thresholds.league_mask(everyone, scope)]
players = thresholds.apply_population(everyone, scope)

with st.container(border=True):
    with st.expander("Criteria", expanded=True):
        st.caption(
            "Each bar is the value itself — nothing is required behind it that is not "
            "written above. Percentiles are read against the league in the bar."
        )
        built = criteria.builder(pool)

matched = shortlist.apply(players, built)

st.caption(criteria.summary(built))

if matched.empty:
    st.info("No player clears every bar. Loosen one of them, or widen the scope bar above.")
    st.stop()

opened = columns.opening_columns(built)

# The order is the app's, not the grid's: a header click arrives as an event, and
# players with no number for that column stay at the bottom of it either way.
targets = results.sort_targets(list(opened))
SCOPE = "shortlist"
OPENING = schema.PLAYER_NAME

previous = selection.current()
stored_key = (
    f"shortlist_{len(matched)}_{len(opened)}_"
    f"{'_'.join(str(part) for part in sorting.order_by(SCOPE, OPENING))}_"
    f"{selection.table_generation()}_{previous or ''}"
)
sorting.apply_header_click(
    SCOPE, selection.columns_clicked(stored_key), targets, stored_key
)

sort_column, ascending = sorting.order_by(SCOPE, OPENING)
marked_column, _ = sorting.chosen(SCOPE)
listed = ranking.order(matched, sort_column, ascending=ascending)

selection.sync(
    chart_key="shortlist_no_chart",
    table_key=stored_key,
    names=listed[schema.PLAYER_NAME].tolist(),
)
chosen = selection.current()
table_key = (
    f"shortlist_{len(matched)}_{len(opened)}_"
    f"{'_'.join(str(part) for part in sorting.order_by(SCOPE, OPENING))}_"
    f"{selection.table_generation()}_{chosen or ''}"
)

with st.container(border=True):
    header, mode, export = st.columns([2.6, 1.2, 1], vertical_alignment="center")
    with header:
        st.caption(
            f"**{len(matched)}** players match · click any line to open his profile "
            "below. The table's own toolbar searches for a name and brings back any "
            "metric left off screen."
        )
    with mode:
        as_percentiles = filters.value_mode(built)
    shown = columns.build(matched)[0]
    with export:
        st.download_button(
            "Download CSV",
            shown.to_csv(index=False),
            file_name="shortlist.csv",
            mime="text/csv",
            width="stretch",
            help="Every metric, not only the columns on screen.",
        )

    results.render(
        listed, opened, key=table_key, selected=chosen,
        as_percentiles=as_percentiles,
        league=pool,
        sorted_label=sorting.label_of(marked_column, targets),
        marker=sorting.arrow(ascending),
    )
    st.caption(sorting.caption(SCOPE, targets, columns.PLAYER))

# The profile opens under the list, where a row would have unfolded if the grid
# could unfold one: `st.dataframe` is a canvas with no detail row, so the panel
# stands directly beneath instead. It carries its own fold, which is how it shuts.
profile = matched[matched[schema.PLAYER_NAME] == chosen] if chosen else matched.iloc[:0]
if profile.empty:
    with st.container(border=True):
        detail.empty_state(len(matched), len(pool))
else:
    detail.block(profile.iloc[0], pool)

# Noted last, once every choice on the page is known. The criteria themselves are
# not written down — only that the reader narrowed something — because a bar is a
# search, and a search is the one thing on this screen worth calling private.
tracking.record(
    "Shortlist",
    scope,
    lens="shortlist",
    sort=sort_column,
    percentiles=as_percentiles,
    player=chosen,
)
