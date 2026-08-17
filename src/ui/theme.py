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
    #: Ordered ramp for a breakdown bar. Five tones, because the defensive
    #: coverages come in fives; the shot zones and court spots take the first
    #: four and three, which is why the fifth was added at the dark end rather
    #: than folded into the middle — nothing already drawn changes colour.
    zones: tuple[str, ...]


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
    zones=("#86b6ef", "#3987e5", "#256abf", "#104281", "#0a2547"),
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
    # The middle tone was `#2a78d6`, which sits in the narrow luminance band where
    # neither near-black nor near-white reaches the 4.5:1 contrast small text needs
    # — a hair too dark to write on, a hair too light to write over. Now that the
    # shot chart prints a percentage inside a mark of this colour, it is nudged one
    # step down so white clears the bar. Dark theme only, and invisible beside the
    # old tone; a test holds every tone of both ramps to that bar.
    zones=("#b7d3f6", "#6da7ec", "#2570cc", "#184f95", "#0d2c55"),
)


#: How strong the wash behind a percentile cell runs, bottom of the league to top.
#: It stops well short of solid: the number has to stay readable through it, and
#: the loaded player's row has to stay the strongest mark on the table.
TINT_FLOOR: float = 0.04
TINT_CEILING: float = 0.50


def _rgb(colour: str) -> tuple[int, int, int]:
    """The three channels of a `#rrggbb` colour."""
    return tuple(int(colour[start:start + 2], 16) for start in (1, 3, 5))  # type: ignore[return-value]


def percentile_tint(place: float, accent: str) -> str:
    """The blue behind a percentile: barely there at the bottom, solid at the top.

    One hue, one axis. A red-to-green scale would read as good-to-bad, which is a
    judgement the app does not make — a high share of guarded shots is not a virtue
    — whereas depth of one colour reads as more-of-it, which is all a percentile
    says.
    """
    red, green, blue = _rgb(accent)
    strength = TINT_FLOOR + (TINT_CEILING - TINT_FLOOR) * max(0.0, min(1.0, float(place)))
    return f"rgba({red},{green},{blue},{strength:.3f})"


def _relative_luminance(colour: str) -> float:
    """The sRGB relative luminance of a `#rrggbb` colour, as the WCAG defines it."""
    channels = []
    for start in (1, 3, 5):
        value = int(colour[start:start + 2], 16) / 255
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def ink_on(colour: str) -> str:
    """A readable text colour for a label drawn *on top of* `colour`.

    Text sitting on a filled mark is read against that fill, not against the page,
    so it cannot take `Palette.ink`: a ramp runs from a pale tone to a deep one, and
    one colour cannot serve both ends of it. Near-black and near-white are taken
    from the light palette in both themes on purpose — what decides the answer is
    the swatch under the text, not the background behind the swatch.
    """
    luminance = _relative_luminance(colour)
    against_black = (luminance + 0.05) / (_relative_luminance(LIGHT.ink) + 0.05)
    against_white = (_relative_luminance(LIGHT.surface) + 0.05) / (luminance + 0.05)
    return LIGHT.ink if against_black >= against_white else LIGHT.surface


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
