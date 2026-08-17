"""Admin — what the app is actually used for, read off a local journal.

Interface only: every figure comes from `src.data.usage`, which is pure functions
over one JSONL file. Nothing here writes.
"""

from __future__ import annotations

import streamlit as st

from src.data import usage
from src.ui import charts, tracking, usage_charts

st.title("Admin")
st.caption(
    "What readers actually do with the app, from a journal kept on this machine. "
    "No account, no network, no name — a random session identifier and nothing else."
)

log = usage.load()

with st.container(border=True):
    left, right = st.columns([3, 1.2], vertical_alignment="center")
    with left:
        st.markdown("**Journal**")
        st.caption(
            f"`{usage.LOG_FILE.relative_to(usage.LOG_FILE.parents[1])}` · "
            f"{len(log)} screens recorded. The folder is outside version control, and "
            "the search box is never written down — only whether one was used."
        )
    with right:
        tracking.set_enabled(
            st.checkbox("Record this session", value=tracking.enabled())
        )

if log.empty:
    st.info(
        "Nothing recorded yet. Open the shortlist or a board, move a filter, load a "
        "player, and come back — the journal fills as the app is used.",
        icon=":material/hourglass_empty:",
    )
    st.stop()

sessions = usage.sessions(log)

# --- how much use, and how deep ------------------------------------------------
with st.container(border=True):
    st.markdown("**Activity**")
    st.caption("A screen is one state the reader put the app in, not one click.")

    tiles = st.columns(4)
    tiles[0].metric("Sessions", f"{len(sessions)}")
    tiles[1].metric("Screens", f"{len(log)}")
    tiles[2].metric("Median session", f"{sessions['minutes'].median():.0f} min")
    tiles[3].metric("Screens per session", f"{sessions['screens'].median():.0f}")

    st.plotly_chart(
        usage_charts.activity(usage.daily_activity(log)),
        width="stretch",
        config=charts.STATIC,
    )

# --- what gets used, and who gets looked at ------------------------------------
left, right = st.columns(2, gap="medium")

with left.container(border=True):
    st.markdown("**Which views are used**")
    st.caption(
        "A lens nobody selects is a lens to rethink. This is the only place that "
        "question can be answered."
    )
    views = usage.view_usage(log).head(10)
    st.plotly_chart(
        usage_charts.ranked(
            [f"{row.page} · {row.view}" for row in views.itertuples()],
            views["screens"].tolist(),
            "screens",
            max(150, 34 * len(views)),
        ),
        width="stretch",
        config=charts.STATIC,
    )

with right.container(border=True):
    st.markdown("**Who gets opened**")
    st.caption("The closest thing this journal holds to interest in a player.")
    players = usage.opened_players(log).head(10)
    if players.empty:
        st.caption("No player has been opened yet.")
    else:
        st.plotly_chart(
            usage_charts.ranked(
                players["player"].tolist(),
                players["sessions"].tolist(),
                "sessions",
                max(150, 34 * len(players)),
            ),
            width="stretch",
            config=charts.STATIC,
        )

# --- are the defaults right? ---------------------------------------------------
with st.container(border=True):
    st.markdown("**Are the bars set where they should be?**")
    st.caption(
        "Every default in the app is a guess written in the source. If readers move "
        "the same one the same way every time, the guess is wrong — and a journal is "
        "the only thing that can say so."
    )

    scope = usage.scope_choices(log)
    if not scope.empty:
        st.dataframe(
            scope.rename(
                columns={
                    "control": "Control",
                    "opens_on": "Opens on",
                    "median_chosen": "Median chosen",
                    "moved": "Moved",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Moved": st.column_config.NumberColumn(
                    format="percent", help="Share of screens where it was not left alone."
                ),
                "Median chosen": st.column_config.NumberColumn(format="%.0f"),
            },
        )

    thresholds = usage.threshold_choices(log)
    if thresholds.empty:
        st.caption("No board minimum has been touched yet.")
    else:
        st.dataframe(
            thresholds.rename(
                columns={
                    "view": "View",
                    "opens_on": "Opens on",
                    "median_chosen": "Median chosen",
                    "moved": "Moved",
                    "screens": "Screens",
                    "verdict": "Reading",
                }
            ),
            width="stretch",
            hide_index=True,
            column_config={
                "Moved": st.column_config.NumberColumn(format="percent"),
                "Median chosen": st.column_config.NumberColumn(format="%.0f"),
            },
        )

# --- did the visit go anywhere? ------------------------------------------------
with st.container(border=True):
    st.markdown("**Did the visit go anywhere?**")
    st.caption(
        "Arriving, narrowing the league, opening somebody — the three things the app "
        "is for. A session that stops at the first step found nothing, or could not "
        "work out how to."
    )
    st.plotly_chart(usage.funnel(log).pipe(usage_charts.funnel), width="stretch",
                    config=charts.STATIC)

with st.expander("Recent sessions"):
    st.dataframe(
        sessions.head(25)[["session", "started", "minutes", "screens", "pages", "players"]]
        .rename(
            columns={
                "session": "Session",
                "started": "Started",
                "minutes": "Minutes",
                "screens": "Screens",
                "pages": "Pages",
                "players": "Players opened",
            }
        ),
        width="stretch",
        hide_index=True,
        column_config={"Minutes": st.column_config.NumberColumn(format="%.0f")},
    )
