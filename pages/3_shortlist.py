"""Shortlist — build a search out of stacked criteria, then open a player in place.

Interface only: the criteria engine and every profile figure live in `src.core`.
"""

from __future__ import annotations

import streamlit as st

from src.core import shortlist, thresholds
from src.data import loader, schema
from src.ui import columns, criteria, detail, filters, results, selection

st.title("Shortlist")
st.caption(
    "Set the bars a player has to clear, then open anyone on the list to see what "
    "the two files say about him."
)

players = loader.load_all_profiles()

with st.container(border=True):
    scope = filters.scope_row(players)
    with st.expander("Criteria", expanded=True):
        st.caption(
            "Every bar carries the events it rests on: a percentage on five shots "
            "clears nothing here."
        )
        built = criteria.builder(players)

    with st.expander("Minimum shots behind each number", expanded=False):
        st.caption(
            "A value resting on fewer events than this is left blank rather than "
            "printed. The player stays on the list; only the number he cannot "
            "support disappears."
        )
        floors = results.minimums(players, columns.denominators())

population = thresholds.apply_population(players, scope)
matched = shortlist.apply(population, built)

st.caption(criteria.summary(built))

if matched.empty:
    st.info("No player clears every bar. Loosen one of them, or lower the events it rests on.")
    st.stop()

opened = columns.opening_columns(built)
table_key = f"shortlist_{len(matched)}_{len(opened)}_{selection.table_generation()}"

selection.sync(
    chart_key="shortlist_no_chart",
    table_key=table_key,
    names=matched[schema.PLAYER_NAME].tolist(),
)
chosen = selection.current()

# The profile sits above the list: `st.dataframe` cannot open a row in place, so
# rather than push the reader down the page it opens where he is already looking.
with st.container(border=True):
    profile = matched[matched[schema.PLAYER_NAME] == chosen] if chosen else matched.iloc[:0]
    if profile.empty:
        detail.empty_state(len(matched))
    else:
        detail.block(profile.iloc[0], players)

with st.container(border=True):
    header, mode, export = st.columns([2.6, 1.2, 1], vertical_alignment="center")
    with header:
        st.caption(
            f"**{len(matched)}** players match · click any line to open his profile "
            "above, or use the table's column menu to bring back any other metric."
        )
    with mode:
        as_percentiles = filters.value_mode(built)
    shown = columns.build(matched, floors)[0]
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
        matched, floors, opened, key=table_key, selected=chosen,
        as_percentiles=as_percentiles,
        league=players,
    )
