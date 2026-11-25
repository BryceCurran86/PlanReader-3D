"""Topology-only continuity for native wall paint that is not drawn as a rectangle.

The strip collectors keep a filled black wall-layer shape whose outline fills
less than 85% of its bounding box (a mitred corner piece, a junction wedge) as
a plain barrier polygon. It is not a strip, so the exterior preflight left it out
of its topology union and a corner painted that way stayed open. This module
selects the pieces that are visibly part of the painted wall: opaque black paint
on an explicit wall layer that is flush with admitted wall paint along at least
two different sides.

Candidate topology only. A selected piece is never a wall, a wall length or
area, a graph node, a source owner or a quantity. Nothing is moved, snapped or
invented: the piece is the native paint, and a gap in that paint stays a gap.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from pb_layered_wall_doorway_room_ring_shadow import NOISE_PT, _is_black, _opaque
from pb_wall_layer_evidence_shadow import is_explicit_wall_layer_name

# A shorter contact is a point touch or a line crossing the wall, not a shared face.
_MIN_FLUSH_PT = 0.5
# One flush side only (an arrowhead or a marker on a wall face) does not join anything.
_MIN_FLUSH_SIDES = 2

_Side = tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class SourceWallJointPaint:
    source_path_id: int
    outline_pdf_pts: tuple[tuple[float, float], ...]
    flush_side_count: int
    page_index: int = -1
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    @property
    def bounds_pdf_pts(self) -> tuple[float, float, float, float]:
        xs, ys = zip(*self.outline_pdf_pts)
        return (min(xs), min(ys), max(xs), max(ys))

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_wall_joint_paint_topology_only",
            "source_path_id": self.source_path_id,
            "outline_pdf_pts": [list(point) for point in self.outline_pdf_pts],
            "flush_side_count": self.flush_side_count,
            "page_index": self.page_index,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _scope(row: Any) -> str:
    if not isinstance(row, Mapping):
        return ""
    return str(row.get("viewport_id") or row.get("source_viewport_id") or "").strip()


def _sides(polygon: Polygon) -> list[_Side]:
    """Straight sides of the outline; a vertex in the middle of a straight side is not a corner."""
    points = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]]
    index = 0
    while len(points) > 3 and index < len(points):
        before, after = points[index - 1], points[(index + 1) % len(points)]
        if LineString((before, after)).distance(Point(points[index])) <= NOISE_PT:
            del points[index]
            index = 0
        else:
            index += 1
    return list(zip(points, points[1:] + points[:1]))


def _on_line(side: _Side, point: tuple[float, float]) -> bool:
    (ax, ay), (bx, by) = side
    cross = (point[0] - ax) * (by - ay) - (point[1] - ay) * (bx - ax)
    return abs(cross) / math.hypot(bx - ax, by - ay) <= NOISE_PT


def _distinct_line_count(sides: Sequence[_Side]) -> int:
    """How many different straight lines the sides lie on (the longest side anchors each line)."""
    anchors: list[_Side] = []
    for start, end in sorted(sides, key=lambda side: (-math.dist(*side), side)):
        if not any(_on_line(anchor, start) and _on_line(anchor, end) for anchor in anchors):
            anchors.append((start, end))
    return len(anchors)


def _usable(polygon: Any) -> bool:
    return (
        isinstance(polygon, Polygon)
        and not polygon.is_empty
        and all(math.isfinite(value) for value in polygon.bounds)
        and polygon.is_valid
        and polygon.area > 0.0
    )


def detect_source_wall_joint_paint(
    barrier_polygons: Sequence[tuple[int, Polygon]],
    *,
    source_drawings: Sequence[Mapping[str, Any] | object],
    wall_bars: Sequence[Any],
    page_index: int = -1,
) -> tuple[SourceWallJointPaint, ...]:
    """Select the wall-joint pieces among the strip collector's barrier polygons.

    ``barrier_polygons`` are ``(native path index, outline)`` pairs, ``source_drawings`` the rows
    those indices address, and ``wall_bars`` the admitted wall strips. A piece is selected when its
    row is opaque black paint on an explicit wall layer and at least two of its sides, on different
    straight lines, run for 0.5 pt or more along the outline of the union of the wall strips. Only
    wall strips count: a piece that merely touches another selected piece is not chained on. Rows
    that declare different viewports never join. Inputs are not modified.
    """
    bars = [bar for bar in wall_bars if _usable(getattr(bar, "polygon", None))]
    if not bars:
        return ()
    wall_face = unary_union([bar.polygon for bar in bars]).boundary.buffer(NOISE_PT)
    selected: list[SourceWallJointPaint] = []
    for path_index, polygon in barrier_polygons:
        if not (0 <= path_index < len(source_drawings)) or not _usable(polygon):
            continue
        row = source_drawings[path_index]
        if not (
            isinstance(row, Mapping)
            and is_explicit_wall_layer_name(str(row.get("layer") or ""))
            and _is_black(row.get("fill"))
            and _opaque(row)
        ):
            continue
        flush = [
            side for side in _sides(polygon)
            if LineString(side).intersection(wall_face).length >= _MIN_FLUSH_PT
        ]
        side_count = _distinct_line_count(flush)
        if side_count < _MIN_FLUSH_SIDES:
            continue
        scopes = {_scope(row)} | {
            _scope(source_drawings[index])
            for bar in bars if bar.polygon.distance(polygon) <= NOISE_PT
            for index in bar.native_path_indices() if 0 <= index < len(source_drawings)
        }
        scopes.discard("")
        if len(scopes) > 1:
            continue
        selected.append(SourceWallJointPaint(
            source_path_id=int(path_index),
            outline_pdf_pts=tuple((float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]),
            flush_side_count=side_count,
            page_index=page_index,
        ))
    return tuple(sorted(selected, key=lambda item: (item.source_path_id, item.outline_pdf_pts)))
