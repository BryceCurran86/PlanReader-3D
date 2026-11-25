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

from shapely.geometry import Polygon
from shapely.ops import unary_union

from pb_layered_wall_doorway_room_ring_shadow import NOISE_PT, _is_black, _opaque
from pb_wall_layer_evidence_shadow import is_explicit_wall_layer_name

# A shorter contact is a point touch or a line crossing the wall, not a shared face.
_MIN_FLUSH_PT = 0.5
# One flush side only (an arrowhead or a marker on a wall face) does not join anything.
_MIN_FLUSH_SIDES = 2
# Edges within this turn of each other can be one straight side; edges below the rounding
# length have no usable direction and are placed by position alone.
_MAX_STRAIGHT_TURN_SIN = math.sin(math.radians(0.5))
_ROUNDING_PT = 0.001

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


def _on_line(side: _Side, point: tuple[float, float]) -> bool:
    (ax, ay), (bx, by) = side
    cross = (point[0] - ax) * (by - ay) - (point[1] - ay) * (bx - ax)
    return abs(cross) / math.hypot(bx - ax, by - ay) <= NOISE_PT


def _same_straight_side(anchor: _Side, edge: _Side) -> bool:
    """Whether ``edge`` continues the straight line of ``anchor`` (either way round)."""
    (ax, ay), (bx, by) = anchor
    (cx, cy), (dx, dy) = edge
    turn = abs((bx - ax) * (dy - cy) - (by - ay) * (dx - cx))
    length = math.dist(*edge)
    if length > _ROUNDING_PT and turn > _MAX_STRAIGHT_TURN_SIN * math.dist(*anchor) * length:
        return False
    return _on_line(anchor, edge[0]) and _on_line(anchor, edge[1])


def _outline_segments(bars: Sequence[Any]) -> list[_Side]:
    """The straight segments of the outline of the union of these wall strips."""
    boundary = unary_union([bar.polygon for bar in bars]).boundary
    segments: list[_Side] = []
    for part in getattr(boundary, "geoms", (boundary,)):
        points = [(float(x), float(y)) for x, y in part.coords]
        segments.extend(pair for pair in zip(points, points[1:]) if pair[0] != pair[1])
    return segments


def _flush_length(edge: _Side, wall_segments: Sequence[_Side]) -> float:
    """How far ``edge`` runs along a parallel wall face (not merely close to it)."""
    (ax, ay), (bx, by) = edge
    length = math.dist(*edge)
    ux, uy = (bx - ax) / length, (by - ay) / length
    spans = []
    for (cx, cy), (dx, dy) in wall_segments:
        along_c = (cx - ax) * ux + (cy - ay) * uy
        along_d = (dx - ax) * ux + (dy - ay) * uy
        low, high = max(0.0, min(along_c, along_d)), min(length, max(along_c, along_d))
        if high <= low:
            continue
        off_c, off_d = ux * (cy - ay) - uy * (cx - ax), ux * (dy - ay) - uy * (dx - ax)
        if abs(off_d - off_c) > _MAX_STRAIGHT_TURN_SIN * math.dist((cx, cy), (dx, dy)):
            continue
        rate = (off_d - off_c) / (along_d - along_c)
        if all(abs(off_c + rate * (at - along_c)) <= NOISE_PT for at in (low, high)):
            spans.append((low, high))
    covered, reached = 0.0, 0.0
    for low, high in sorted(spans):
        if high > reached:
            covered += high - max(low, reached)
            reached = high
    return covered


def _flush_sides(polygon: Polygon, wall_segments: Sequence[_Side]) -> list[_Side]:
    """Straight sides of the outline that run ``_MIN_FLUSH_PT`` or more along wall faces.

    A side is the outline's own edges that stay on one straight line, so an extra vertex in the
    middle of a side changes nothing. No vertex is moved or removed: a curve drawn as many short
    edges keeps turning and never becomes a long side.
    """
    x0, y0, x1, y1 = polygon.bounds
    nearby = [
        segment for segment in wall_segments
        if min(segment[0][0], segment[1][0]) <= x1 + 1.0 and max(segment[0][0], segment[1][0]) >= x0 - 1.0
        and min(segment[0][1], segment[1][1]) <= y1 + 1.0 and max(segment[0][1], segment[1][1]) >= y0 - 1.0
    ]
    points = [(float(x), float(y)) for x, y in polygon.exterior.coords]
    touching = []
    for edge in zip(points, points[1:]):
        if edge[0] != edge[1]:
            length = _flush_length(edge, nearby)
            if length > 0.0:
                touching.append((edge, length))
    runs: list[tuple[_Side, list[float], list[tuple[float, float]]]] = []
    for edge, length in sorted(touching, key=lambda item: (-math.dist(*item[0]), item[0])):
        run = next((item for item in runs if _same_straight_side(item[0], edge)), None)
        if run is None:
            runs.append((edge, [length], list(edge)))
        else:
            run[1].append(length)
            run[2].extend(edge)
    flush: list[_Side] = []
    for ((ax, ay), (bx, by)), lengths, ends in runs:
        if math.fsum(lengths) >= _MIN_FLUSH_PT:
            along = sorted(ends, key=lambda p: ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay), p))
            flush.append((along[0], along[-1]))
    return flush


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


def _bar_scope(bar: Any, source_drawings: Sequence[Mapping[str, Any] | object]) -> str | None:
    """Unique declared viewport scope for one wall bar, '' if unscoped, None if malformed/conflicting."""
    try:
        indices = tuple(bar.native_path_indices())
    except (AttributeError, TypeError):
        return None
    if not indices:
        return None
    scopes: set[str] = set()
    for index in indices:
        if type(index) is not int or not (0 <= index < len(source_drawings)):
            return None
        scope = _scope(source_drawings[index])
        if scope:
            scopes.add(scope)
    if len(scopes) > 1:
        return None
    return next(iter(scopes)) if scopes else ""


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
    straight lines, run for 0.5 pt or more along a parallel face of the union of compatible wall
    strips (within 0.5 degrees and 0.05 pt, so a curve or a tangent touch is not a shared face).
    Only wall strips count: a piece that merely touches another selected piece is not chained on.
    Wall unions and contact are strictly viewport-scoped so overlapping declared viewports never
    bridge or veto each other. Inputs are not modified.
    """
    if type(page_index) is not int or page_index < -1:
        raise ValueError("source_wall_joint_paint_page_index_invalid")
    bars_by_scope: dict[str, list[Any]] = {}
    for bar in wall_bars:
        if not _usable(getattr(bar, "polygon", None)):
            continue
        scope = _bar_scope(bar, source_drawings)
        if scope is None:
            continue
        bars_by_scope.setdefault(scope, []).append(bar)
    if not bars_by_scope:
        return ()

    wall_face_cache: dict[str, Any] = {}

    def _wall_face_for(scope_key: str):
        if scope_key not in wall_face_cache:
            scoped_bars = bars_by_scope.get(scope_key, ())
            wall_face_cache[scope_key] = _outline_segments(scoped_bars) if scoped_bars else None
        return wall_face_cache[scope_key]

    selected: list[SourceWallJointPaint] = []
    seen_keys: set[tuple[int, tuple[tuple[float, float], ...]]] = set()
    for path_index, polygon in barrier_polygons:
        if type(path_index) is not int or not (0 <= path_index < len(source_drawings)) or not _usable(polygon):
            continue
        row = source_drawings[path_index]
        if not (
            isinstance(row, Mapping)
            and is_explicit_wall_layer_name(str(row.get("layer") or ""))
            and _is_black(row.get("fill"))
            and _opaque(row)
        ):
            continue
        row_scope = _scope(row)
        if row_scope:
            # A joint declaring a viewport evaluates contact strictly against
            # wall bars in that same viewport; overlapping foreign viewports
            # neither supply flush sides nor falsely veto it.
            wall_face = _wall_face_for(row_scope)
            if wall_face is None:
                continue
        else:
            # An unscoped joint may never bridge two different declared viewports.
            touching_scopes = {
                scope
                for scope, scoped_bars in bars_by_scope.items()
                if scope and any(bar.polygon.distance(polygon) <= NOISE_PT for bar in scoped_bars)
            }
            if len(touching_scopes) > 1:
                continue
            target_scope = next(iter(touching_scopes)) if touching_scopes else ""
            if target_scope:
                # Allow compatible unscoped + single declared scope only when no other scope touches.
                combined_bars = bars_by_scope.get(target_scope, []) + bars_by_scope.get("", [])
                wall_face = _outline_segments(combined_bars)
            else:
                wall_face = _wall_face_for("")
                if wall_face is None:
                    continue
        side_count = _distinct_line_count(_flush_sides(polygon, wall_face))
        if side_count < _MIN_FLUSH_SIDES:
            continue
        outline = tuple((float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1])
        dedupe_key = (int(path_index), outline)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        selected.append(SourceWallJointPaint(
            source_path_id=int(path_index),
            outline_pdf_pts=outline,
            flush_side_count=side_count,
            page_index=page_index,
        ))
    return tuple(sorted(selected, key=lambda item: (item.source_path_id, item.outline_pdf_pts)))
