"""Every view the app offers, and the lookups the interface needs.

The views themselves live next door, one module per data file, so a page only
ever hands this module a group of lenses.
"""

from __future__ import annotations

from src.core.metrics import DEC1, Lens, View
from src.core.pick_views import PICK_LENSES
from src.core.shot_views import SHOT_LENSES
from src.data import glossary

LENSES: tuple[Lens, ...] = (*SHOT_LENSES, *PICK_LENSES)


def format_of(column: str) -> str:
    """Return the format key the catalogue uses for a column.

    Falls back to one decimal place for anything the catalogue never displays.
    """
    for view in all_views():
        for axis in (view.x, view.y):
            if axis.key == column:
                return axis.fmt
        for col in view.columns:
            if col.key == column:
                return col.fmt
    return DEC1


def all_views() -> list[View]:
    """Every view in the catalogue, flattened across lenses."""
    return [view for lens in LENSES for view in lens.views]


def lens_by_key(key: str) -> Lens:
    """Return a lens by its key."""
    return next(lens for lens in LENSES if lens.key == key)


def view_by_key(key: str) -> View:
    """Return a view by its key."""
    return next(view for view in all_views() if view.key == key)


def lens_of(view: View) -> Lens:
    """The lens a view belongs to."""
    return next(lens for lens in LENSES if view in lens.views)


def short(view: View, name: str) -> str:
    """A glossary name with whatever the board already states taken out of it.

    Two things get said twice on a pick-and-roll board. The lens selector names the
    role, and the view selector names the coverage — so a column headed `Screener -
    Points Per Pick (vs Soft (Drop))` spends twenty-eight of its thirty-two
    characters repeating the two controls directly above it, seven times across,
    and the reader ends up scrolling sideways to read his own board.

    The coverage only comes off a view that is *about* one coverage, where every
    column carries the same one. Elsewhere it is what tells two columns apart.
    """
    trimmed = name.removeprefix(lens_of(view).prefix)
    if "_vs_" in view.threshold.key:
        trimmed = glossary.without_split(trimmed)
    return trimmed
