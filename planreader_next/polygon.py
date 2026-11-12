"""Exact-source closed native line polygon: no inferred endpoints or snapping.

This module never asserts that source lines are internal finished wall faces;
review and independent finish/metric authority remain separate.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import Sequence

from .engine import NativePage, SourceConflict

Point = tuple[float, float]


@dataclass(frozen=True)
class SourcePolygon:
    ref: str
    segment_refs: tuple[str, ...]
    vertices: tuple[Point, ...]
    bbox: tuple[float, float, float, float]
    area_pt2: float


def _matches(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= 0.001 and abs(a[1] - b[1]) <= 0.001


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Conservative intersection test; exact touch/overlap also conflicts."""
    ab_c = _cross(a, b, c)
    ab_d = _cross(a, b, d)
    cd_a = _cross(c, d, a)
    cd_b = _cross(c, d, b)
    eps = 1e-8
    def between(x: Point, y: Point, z: Point) -> bool:
        return min(x[0], y[0]) - 1e-6 <= z[0] <= max(x[0], y[0]) + 1e-6 and min(x[1], y[1]) - 1e-6 <= z[1] <= max(x[1], y[1]) + 1e-6
    if abs(ab_c) <= eps and between(a, b, c):
        return True
    if abs(ab_d) <= eps and between(a, b, d):
        return True
    if abs(cd_a) <= eps and between(c, d, a):
        return True
    if abs(cd_b) <= eps and between(c, d, b):
        return True
    return (ab_c > 0) != (ab_d > 0) and (cd_a > 0) != (cd_b > 0)


def source_polygon(page: NativePage, selected: Sequence[str]) -> SourcePolygon:
    if not isinstance(selected, (list, tuple)) or not 3 <= len(selected) <= 4096:
        raise SourceConflict("native_polygon_segments_invalid")
    if any(not isinstance(ref, str) or not ref for ref in selected) or len(set(selected)) != len(selected):
        raise SourceConflict("native_polygon_source_segment_reused")
    owned = {segment.ref: segment for segment in page.segments}
    if any(ref not in owned for ref in selected):
        raise SourceConflict("native_polygon_segment_not_owned")
    spans = [owned[ref] for ref in selected]
    if any(segment.kind not in ("line", "rect_edge") for segment in spans):
        raise SourceConflict("native_polygon_segment_kind_unsupported")
    start = (spans[0].x1, spans[0].y1)
    current = (spans[0].x2, spans[0].y2)
    points: list[Point] = [start, current]
    for edge in spans[1:]:
        a, b = (edge.x1, edge.y1), (edge.x2, edge.y2)
        if _matches(current, a):
            current = b
        elif _matches(current, b):
            current = a
        else:
            raise SourceConflict("native_polygon_wall_cycle_gap")
        points.append(current)
    if not _matches(points[0], points[-1]):
        raise SourceConflict("native_polygon_wall_cycle_open")
    points.pop()
    if len(points) < 3 or len(set(points)) != len(points):
        raise SourceConflict("native_polygon_duplicate_vertices")
    if not all(math.isfinite(value) for point in points for value in point):
        raise SourceConflict("native_polygon_non_finite")
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        if math.dist(a, b) < 0.001:
            raise SourceConflict("native_polygon_degenerate_edge")
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = points[j], points[(j + 1) % n]
            if _intersects(a, b, c, d):
                raise SourceConflict("native_polygon_self_intersection")
    area = abs(sum(
        points[i][0] * points[(i + 1) % n][1] -
        points[(i + 1) % n][0] * points[i][1]
        for i in range(n)
    )) / 2
    if area <= 1.0:
        raise SourceConflict("native_polygon_degenerate_area")
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    # Stable identity independent of edge traversal order or direction.
    fingerprint = "|".join(sorted(selected))
    return SourcePolygon(
        ref="native-polygon:" + sha256(fingerprint.encode("utf-8")).hexdigest()[:24],
        segment_refs=tuple(selected),
        vertices=tuple(points),
        bbox=(min(xs), min(ys), max(xs), max(ys)),
        area_pt2=area,
    )
