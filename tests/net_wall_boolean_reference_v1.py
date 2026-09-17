"""Test-only portable reference geometry for Net-wall Boolean Union.

This module has no authority role. It deliberately avoids adding a production
geometry dependency merely to execute the validator foundation. Future Item 17
production is still required to use a real polygon Boolean-union implementation.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)


def rect(x0: float, y0: float, x1: float, y1: float) -> Rect:
    assert x1 >= x0 and y1 >= y0
    return Rect(float(x0), float(y0), float(x1), float(y1))


def reference_void_union_area(voids: Iterable[Rect]) -> float:
    """Exact union area for axis-aligned validator rectangles via x-sweep."""
    items = tuple(voids)
    if not items:
        return 0.0
    xs = sorted({v.x0 for v in items} | {v.x1 for v in items})
    total = 0.0
    for left, right in zip(xs, xs[1:]):
        if right <= left:
            continue
        active = [v for v in items if v.x0 < right and v.x1 > left]
        intervals = sorted((v.y0, v.y1) for v in active if v.y1 > v.y0)
        if not intervals:
            continue
        covered = 0.0
        start, end = intervals[0]
        for y0, y1 in intervals[1:]:
            if y0 <= end:
                end = max(end, y1)
            else:
                covered += end - start
                start, end = y0, y1
        covered += end - start
        total += (right - left) * covered
    return total


def reference_net_wall_area(gross_wall: Rect, voids: Iterable[Rect]) -> float:
    return gross_wall.area - reference_void_union_area(voids)


def normalized_rect_set(voids: Iterable[Rect]) -> tuple[Rect, ...]:
    """Deterministic test serialization independent of input order."""
    return tuple(sorted(set(voids)))
