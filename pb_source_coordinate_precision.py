"""Equality within the precision of parsed source coordinates (#4764 geometry task C14), used only when opted in.

PDF coordinates are parsed as float32, so points on one angled line miss each other by a few ulps (about 1.4e-5 pt at 500 pt),
below the absolute 1e-6 and relative 1e-9 tests that axis-aligned geometry satisfies exactly. This tolerance is representation
error, a few ulps at the page's coordinate magnitude (about 2.4e-4 pt at 500 pt): it is not a snap or a drawing tolerance.
"""
from __future__ import annotations

from typing import Iterable, Sequence

_FLOAT32_EPSILON = 2.0 ** -23
_ULPS = 4.0


def source_coordinate_tolerance(lines: Iterable[Sequence[float]], *, floor: float) -> float:
    magnitude = max((abs(float(value)) for line in lines for value in line), default=0.0)
    return max(float(floor), _ULPS * _FLOAT32_EPSILON * magnitude)
