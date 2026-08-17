"""The local usage journal: one JSONL line per state the reader put the app in.

Written to `logs/usage.jsonl`, never to `data/`, and the folder is out of git. No
network call, no account, no personal identifier — a session is a random string
drawn once per browser session and nothing else is kept. Everything here is a pure
function over a frame, except `append`, which is the one side effect.

**One line per state, not per rerun.** Streamlit reruns the script on every widget
touch, so writing unconditionally would fill the file with copies of the same
screen. `append` drops an event identical to the last one it wrote.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

LOG_DIR: Path = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE: Path = LOG_DIR / "usage.jsonl"

#: When a line carries a value the reader did not choose — no player open, no team
#: filter — the field is written as null rather than omitted, so the frame keeps a
#: stable set of columns however old the file is.
FIELDS: tuple[str, ...] = (
    "at",
    "session",
    "page",
    "lens",
    "view",
    "minimum",
    "minimum_default",
    "games",
    "attempts",
    "team",
    "traded",
    "searched",
    "sort",
    "mode",
    "player",
)

#: Gap after which a session is treated as over, for the length figures.
SESSION_GAP_MINUTES: int = 30


def append(event: dict, previous: str | None) -> str | None:
    """Write one event unless it repeats the last one, and return its signature.

    Args:
        event: the state to record. Missing fields are filled with None.
        previous: the signature the caller last got back, or None on a first write.

    Returns:
        The signature of the state now on file — hand it back on the next call.
        Failures are swallowed: a journal is a convenience, and an app that dies
        because it cannot write a log line is worse than one that keeps no log.
    """
    row = {field: event.get(field) for field in FIELDS}
    signature = json.dumps({k: v for k, v in row.items() if k != "at"}, sort_keys=True)
    if signature == previous:
        return previous

    row["at"] = datetime.now().isoformat(timespec="seconds")
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        return previous
    return signature


def load() -> pd.DataFrame:
    """Read the journal. Empty frame with the right columns when there is none yet.

    Deliberately not cached: the file grows while the app is being used, and a page
    reporting on activity that is one rerun stale is a page reporting on nothing.
    """
    empty = pd.DataFrame({field: pd.Series(dtype="object") for field in FIELDS})
    if not LOG_FILE.exists():
        return empty

    rows = []
    with LOG_FILE.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # A half-written last line is the one thing that can go wrong here.
                continue
    if not rows:
        return empty

    frame = pd.DataFrame(rows).reindex(columns=list(FIELDS))
    frame["at"] = pd.to_datetime(frame["at"], errors="coerce")
    return frame.dropna(subset=["at"]).sort_values("at").reset_index(drop=True)


def daily_activity(frame: pd.DataFrame) -> pd.DataFrame:
    """Screens looked at and sessions opened, per day."""
    if frame.empty:
        return pd.DataFrame(columns=["day", "screens", "sessions"])
    days = frame.assign(day=frame["at"].dt.date)
    return (
        days.groupby("day")
        .agg(screens=("at", "size"), sessions=("session", "nunique"))
        .reset_index()
    )


def sessions(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per session: when it ran, how long, how much of the app it touched."""
    if frame.empty:
        return pd.DataFrame(columns=["session", "started", "minutes", "screens", "players"])
    grouped = frame.groupby("session")
    out = grouped.agg(
        started=("at", "min"),
        ended=("at", "max"),
        screens=("at", "size"),
        players=("player", "nunique"),
        pages=("page", "nunique"),
    ).reset_index()
    out["minutes"] = (out["ended"] - out["started"]).dt.total_seconds() / 60
    return out.sort_values("started", ascending=False)


def view_usage(frame: pd.DataFrame) -> pd.DataFrame:
    """How often each page, lens and view was actually on screen.

    The point of the page: a lens nobody ever selects is a lens to rethink, and
    that is not visible from inside the code.
    """
    if frame.empty:
        return pd.DataFrame(columns=["page", "lens", "view", "screens", "sessions"])
    return (
        frame.groupby(["page", "lens", "view"], dropna=False)
        .agg(screens=("at", "size"), sessions=("session", "nunique"))
        .reset_index()
        .sort_values("screens", ascending=False)
    )


def opened_players(frame: pd.DataFrame) -> pd.DataFrame:
    """Who was actually looked at — the closest thing here to market interest."""
    if frame.empty or frame["player"].isna().all():
        return pd.DataFrame(columns=["player", "screens", "sessions"])
    looked = frame.dropna(subset=["player"])
    return (
        looked.groupby("player")
        .agg(screens=("at", "size"), sessions=("session", "nunique"))
        .reset_index()
        .sort_values(["sessions", "screens"], ascending=False)
    )


def threshold_choices(frame: pd.DataFrame) -> pd.DataFrame:
    """What each view's minimum was actually set to, against what it opens on.

    The figure this page exists for. A default is a guess written in the source; if
    every reader moves the same slider in the same direction, the guess is wrong and
    nothing but a journal would say so.
    """
    if frame.empty:
        return pd.DataFrame(
            columns=["view", "opens_on", "median_chosen", "moved", "screens", "verdict"]
        )
    known = frame.dropna(subset=["view", "minimum", "minimum_default"])
    if known.empty:
        return pd.DataFrame(
            columns=["view", "opens_on", "median_chosen", "moved", "screens", "verdict"]
        )

    known = known.assign(moved=known["minimum"] != known["minimum_default"])
    out = (
        known.groupby("view")
        .agg(
            opens_on=("minimum_default", "first"),
            median_chosen=("minimum", "median"),
            moved=("moved", "mean"),
            screens=("at", "size"),
        )
        .reset_index()
    )
    out["verdict"] = [
        _verdict(row.moved, row.median_chosen, row.opens_on) for row in out.itertuples()
    ]
    return out.sort_values("screens", ascending=False)


def _verdict(moved: float, chosen: float, opens_on: float) -> str:
    """Whether the default looks right, in the words the reader of this page needs."""
    if moved < 0.25:
        return "Left alone — the default holds"
    direction = "up" if chosen > opens_on else "down"
    return f"Moved {direction} most of the time — consider {int(round(chosen))}"


def scope_choices(frame: pd.DataFrame) -> pd.DataFrame:
    """Same question for the one control that reaches the whole app."""
    if frame.empty:
        return pd.DataFrame(columns=["control", "opens_on", "median_chosen", "moved"])
    rows = []
    for field, default in (("games", 15), ("attempts", 35)):
        values = pd.to_numeric(frame[field], errors="coerce").dropna()
        if values.empty:
            continue
        rows.append(
            {
                "control": "Minimum games" if field == "games" else "Minimum shots",
                "opens_on": default,
                "median_chosen": float(values.median()),
                "moved": float((values != default).mean()),
            }
        )
    return pd.DataFrame(rows)


def funnel(frame: pd.DataFrame) -> pd.DataFrame:
    """Sessions that arrived, narrowed something, then opened somebody.

    Three steps, because they are the three things this app is for. A session that
    never opens a player either found nothing or could not work out how to.
    """
    if frame.empty:
        return pd.DataFrame(columns=["step", "sessions"])
    total = frame["session"].nunique()

    chosen = pd.to_numeric(frame["minimum"], errors="coerce")
    opens_on = pd.to_numeric(frame["minimum_default"], errors="coerce")
    # Both have to be present before they can differ. A bare `!=` reads two missing
    # values as a difference — NaN never equals NaN — so every screen of a page with
    # no slider on it, the shortlist included, counted as a minimum somebody moved.
    moved = chosen.notna() & opens_on.notna() & (chosen != opens_on)

    narrowed = frame[
        (pd.to_numeric(frame["games"], errors="coerce") != 15)
        | (pd.to_numeric(frame["attempts"], errors="coerce") != 35)
        | frame["team"].notna()
        | frame["searched"].astype("boolean").fillna(False).astype(bool)
        | moved
    ]["session"].nunique()

    opened = frame.dropna(subset=["player"])["session"].nunique()
    return pd.DataFrame(
        [
            {"step": "Sessions", "sessions": total},
            {"step": "Narrowed the league or a minimum", "sessions": narrowed},
            {"step": "Opened a player", "sessions": opened},
        ]
    )
