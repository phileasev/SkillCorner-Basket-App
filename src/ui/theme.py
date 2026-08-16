"""Colours shared by every chart, resolved against the theme the reader is using.

The zone ramp is ordered by distance from the basket, so its lightness carries
real information rather than decoration.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Palette:
    """One resolved set of chart colours."""

    accent: str
    muted: str
    ink: str
    ink_soft: str
    rule: str
    surface: str
    highlight: str
    selected: str
    track: str
    zones: tuple[str, str, str, str]


#: The sorted column is a hint, the loaded player is the point: `highlight` stays
#: far below `selected` so the two never compete for the eye.
#:
#: Gridlines are a reference, not content: translucent grey reads as a hairline on
#: either background, and stays behind the marks even if the theme is misdetected
#: on first load.
GRID: str = "rgba(137,135,129,0.22)"
TRANSPARENT: str = "rgba(0,0,0,0)"

LIGHT = Palette(
    accent="#2a78d6",
    muted="#9a9892",
    ink="#0b0b0b",
    ink_soft="#52514e",
    rule="rgba(137,135,129,0.55)",
    surface="#fcfcfb",
    highlight="rgba(42,120,214,0.045)",
    selected="rgba(42,120,214,0.22)",
    track="rgba(137,135,129,0.10)",
    zones=("#86b6ef", "#3987e5", "#256abf", "#104281"),
)

DARK = Palette(
    accent="#3987e5",
    muted="#6f6e69",
    ink="#ffffff",
    ink_soft="#c3c2b7",
    rule="rgba(137,135,129,0.45)",
    surface="#1a1a19",
    highlight="rgba(57,135,229,0.09)",
    selected="rgba(57,135,229,0.34)",
    track="rgba(137,135,129,0.14)",
    zones=("#b7d3f6", "#6da7ec", "#2a78d6", "#184f95"),
)


def is_dark() -> bool:
    """Whether the reader is looking at the app in dark mode.

    Prefers the theme Streamlit infers from the rendered background, and falls
    back to the configured base when that is unavailable.
    """
    try:
        inferred = st.context.theme["type"]
    except Exception:  # noqa: BLE001 - context is absent outside a script run
        inferred = None
    base = inferred or st.get_option("theme.base") or "light"
    return str(base).lower() == "dark"


def palette() -> Palette:
    """Return the palette matching the theme the reader is currently using."""
    return DARK if is_dark() else LIGHT
