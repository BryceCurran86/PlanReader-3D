"""Bound original native figure ink to one independently drawn physical footprint.

This authority receives independently authenticated source dimensions and a
label path roster. It accepts either genuinely joined four-edge rectangles, or
open-air structural bays only when native source-post squares connect the right
edge gaps and same-alignment wall spans bridge BOTH left-side gaps. Four
disconnected long edges alone NEVER authenticate a footprint. Reference truth,
project name, hardcoded dimensions and scoring tolerances are not inputs.
Incomplete, ambiguous and rival physical owners ABSTAIN.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

SOURCE_PRIMITIVE_CAP = 20000
SOURCE_SNAP_TOL_PT = 2.5
SOURCE_ASPECT_TOL_FRACTION = 0.01


@dataclass(frozen=True)
class SourceNativePhysicalFootprint:
    boundary_source_path_ids: tuple[int, int, int, int]
    label_source_path_ids: tuple[int, ...]
    native_bounds_pts: tuple[float, float, float, float]
    figured_width_mm: int
    figured_depth_mm: int
    status: str = "CORROBORATED"
    physical_scope: str = "source_labeled_exterior_architectural_footprint"
    boundary_model: str = "continuous_closed_outline"
    connector_source_path_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class _Edge:
    path_id: int
    at: float
    start: float
    end: float
    stroke_width: float


def _finite_rect(raw: Any) -> tuple[float, float, float, float] | None:
    try:
        rect = raw.get("rect")
        values = tuple(float(v) for v in (rect.x0, rect.y0, rect.x1, rect.y1))
    except (AttributeError, ValueError, TypeError, OverflowError):
        return None
    if (
        len(values) != 4
        or not all(math.isfinite(v) for v in values)
        or values[0] > values[2]
        or values[1] > values[3]
    ):
        return None
    return values


def _black_source_stroke(raw: Any) -> bool:
    if type(raw) is not dict or raw.get("type") != "s":
        return False
    color, width = raw.get("color"), raw.get("width")
    return (
        type(color) in (tuple, list)
        and tuple(color) == (0.0, 0.0, 0.0)
        and type(width) in (int, float)
        and math.isfinite(width)
        and 0.2 <= width <= 1.5
        and _finite_rect(raw) is not None
    )


def _source_edges(drawings: list[dict[str, Any]], excluded: frozenset[int]):
    horizontal: list[_Edge] = []
    vertical: list[_Edge] = []
    examined = 0
    for path_id, raw in enumerate(drawings):
        if path_id in excluded or not _black_source_stroke(raw):
            continue
        strokes = raw.get("items")
        if type(strokes) not in (tuple, list) or len(strokes) > 512:
            continue
        for item in strokes:
            if type(item) not in (tuple, list) or len(item) < 3 or item[0] != "l":
                continue
            try:
                a, b = item[1], item[2]
                x0, y0, x1, y1 = float(a.x), float(a.y), float(b.x), float(b.y)
            except (AttributeError, TypeError, ValueError, OverflowError):
                continue
            if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                continue
            if abs(y0 - y1) <= 0.1 and abs(x1 - x0) > 20.0:
                horizontal.append(_Edge(
                    path_id, (y0 + y1) / 2.0, min(x0, x1),
                    max(x0, x1), float(raw["width"]),
                ))
                examined += 1
            elif abs(x0 - x1) <= 0.1 and abs(y1 - y0) > 20.0:
                vertical.append(_Edge(
                    path_id, (x0 + x1) / 2.0, min(y0, y1),
                    max(y0, y1), float(raw["width"]),
                ))
                examined += 1
            if examined > SOURCE_PRIMITIVE_CAP:
                return None
    return horizontal, vertical


def _square_post_boxes(
    drawings: list[dict[str, Any]], excluded: frozenset[int],
) -> tuple[tuple[int, tuple[float, float, float, float]], ...] | None:
    """Only native drawn square post/quads; never bbox-only ink or labels."""
    posts = []
    for path_id, raw in enumerate(drawings):
        if path_id in excluded or not _black_source_stroke(raw):
            continue
        items = raw.get("items")
        if type(items) not in (list, tuple) or len(items) != 1 or items[0][0] != "qu":
            continue
        if len(items[0]) < 2:
            continue
        box = _finite_rect(raw)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        width, height = x1 - x0, y1 - y0
        if (
            width <= SOURCE_SNAP_TOL_PT or height <= SOURCE_SNAP_TOL_PT
            or abs(width - height) > SOURCE_SNAP_TOL_PT
        ):
            continue
        try:
            quad = items[0][1]
            points = tuple((float(p.x), float(p.y)) for p in (
                quad.ul, quad.ur, quad.ll, quad.lr,
            ))
        except (TypeError, AttributeError, ValueError, OverflowError):
            continue
        if len(set(points)) != 4 or not all(
            math.isfinite(v) for point in points for v in point
        ):
            continue
        corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
        if any(not any(
            abs(px - cx) <= SOURCE_SNAP_TOL_PT
            and abs(py - cy) <= SOURCE_SNAP_TOL_PT
            for px, py in points
        ) for cx, cy in corners):
            continue
        posts.append((path_id, box))
        if len(posts) > SOURCE_PRIMITIVE_CAP:
            return None
    return tuple(posts)


def _post_bounded_wall_connectors(
    top: _Edge, bottom: _Edge, left: _Edge, right: _Edge,
    source_vertical: Sequence[_Edge],
    posts: Sequence[tuple[int, tuple[float, float, float, float]]],
) -> tuple[int, int, int, int] | None:
    """Bridge ALL four disjoint corners through original physical members.

    The long strokes alone are NOT a closed floor perimeter. Right-side square
    post symbols and left-side contiguous building-wall continuations are
    independently sourced structural support for an open-air footprint.
    """
    tol = SOURCE_SNAP_TOL_PT
    height = bottom.at - top.at
    if (
        not tol < left.start - top.at < 0.25 * height
        or not tol < bottom.at - left.end < 0.25 * height
        or not tol < right.start - top.at < 0.25 * height
        or not tol < bottom.at - right.end < 0.25 * height
        or not tol < right.at - top.end < 0.25 * height
    ):
        return None

    def wall(path: _Edge, upper: bool) -> bool:
        return (
            path.path_id not in {
                top.path_id, bottom.path_id, left.path_id, right.path_id,
            }
            and abs(path.at - left.at) <= tol
            and abs(path.at - top.start) <= tol
            and abs(path.at - bottom.start) <= tol
            and (
                path.start <= top.at + tol
                and path.end >= left.start - tol
                if upper else
                path.start <= left.end + tol
                and path.end >= bottom.at - tol
            )
        )

    upper_wall = {path.path_id for path in source_vertical if wall(path, True)}
    lower_wall = {path.path_id for path in source_vertical if wall(path, False)}
    if len(upper_wall) != 1 or len(lower_wall) != 1:
        return None

    def post_matches(
        box: tuple[float, float, float, float], upper: bool,
    ) -> bool:
        target = (
            (top.end, top.at, right.at, right.start) if upper else
            (bottom.end, right.end, right.at, bottom.at)
        )
        return all(abs(a - b) <= tol for a, b in zip(box, target))

    upper_post = {path for path, box in posts if post_matches(box, True)}
    lower_post = {path for path, box in posts if post_matches(box, False)}
    if len(upper_post) != 1 or len(lower_post) != 1:
        return None

    witnesses = (
        next(iter(upper_wall)), next(iter(lower_wall)),
        next(iter(upper_post)), next(iter(lower_post)),
    )
    return witnesses if len(set(witnesses)) == 4 else None


def _continuous_rectangle_corners(
    top: _Edge, bottom: _Edge, left: _Edge, right: _Edge,
) -> bool:
    """Endpoint-connected means within 2.5pt at EACH of four corners."""
    t = SOURCE_SNAP_TOL_PT
    return all((
        abs(left.at - top.start) <= t,
        abs(left.at - bottom.start) <= t,
        abs(right.at - top.end) <= t,
        abs(right.at - bottom.end) <= t,
        abs(left.start - top.at) <= t,
        abs(right.start - top.at) <= t,
        abs(left.end - bottom.at) <= t,
        abs(right.end - bottom.at) <= t,
    ))


def corroborate_source_labeled_rectangular_footprint(
    drawings: list[dict[str, Any]],
    *,
    source_label_path_ids: Sequence[int],
    figured_width_mm: int,
    figured_depth_mm: int,
    excluded_source_path_ids: Sequence[int] = (),
) -> SourceNativePhysicalFootprint | None:
    """Prove one native closed outline OR source post/wall-bounded open bay.

    Source geometry proves physical ownership/aspect, never converts PDF
    points into customer square meters; independent printed figures do that.
    Four nonintersecting arbitrary strokes cannot authorize a physical area.
    """
    if type(drawings) is not list or not 0 < len(drawings) <= SOURCE_PRIMITIVE_CAP:
        return None
    if (
        type(figured_width_mm) is not int or type(figured_depth_mm) is not int
        or not 100 <= figured_width_mm <= 50000
        or not 100 <= figured_depth_mm <= 50000
    ):
        return None
    if type(source_label_path_ids) not in (tuple, list):
        return None
    label_ids = tuple(source_label_path_ids)
    if (
        not 1 < len(label_ids) <= 200
        or any(type(i) is not int or i < 0 or i >= len(drawings) for i in label_ids)
        or len(label_ids) != len(set(label_ids))
    ):
        return None
    if type(excluded_source_path_ids) not in (tuple, list):
        return None
    exclusions = tuple(excluded_source_path_ids)
    if (
        any(type(i) is not int or i < 0 or i >= len(drawings) for i in exclusions)
    ):
        return None
    label_bounds: list[tuple[float, float, float, float]] = []
    for index in label_ids:
        raw = drawings[index]
        if not _black_source_stroke(raw):
            return None
        bbox = _finite_rect(raw)
        if bbox is None:
            return None
        label_bounds.append(bbox)
    lx0, ly0 = min(x[0] for x in label_bounds), min(x[1] for x in label_bounds)
    lx1, ly1 = max(x[2] for x in label_bounds), max(x[3] for x in label_bounds)
    label_width = lx1 - lx0
    if label_width <= SOURCE_SNAP_TOL_PT or ly1 <= ly0:
        return None
    excluded = frozenset((*label_ids, *exclusions))
    raw_edges = _source_edges(drawings, excluded)
    posts = _square_post_boxes(drawings, excluded)
    if raw_edges is None or posts is None:
        return None
    source_h, source_v = raw_edges
    center_x, center_y = (lx0 + lx1) / 2.0, (ly0 + ly1) / 2.0
    region = 4.0 * label_width

    hs = [
        edge for edge in source_h
        if edge.start < lx0 - SOURCE_SNAP_TOL_PT
        and edge.end > lx1
        and abs(edge.at - center_y) < region
    ]
    vs = [
        edge for edge in source_v
        if edge.start < ly0 - SOURCE_SNAP_TOL_PT
        and edge.end > ly1
        and abs(edge.at - center_x) < region
    ]
    # Stop rival-heavy ink; do not resolve by choosing the nearest rectangle.
    if len(hs) > 128 or len(vs) > 128:
        return None

    figured_ratio = figured_width_mm / figured_depth_mm
    matched: dict[tuple[int, int, int, int], SourceNativePhysicalFootprint] = {}
    for top in hs:
        if top.at >= ly0 - SOURCE_SNAP_TOL_PT:
            continue
        for bottom in hs:
            if (
                bottom.at <= ly1 + SOURCE_SNAP_TOL_PT
                or bottom.at <= top.at + SOURCE_SNAP_TOL_PT
                or abs(top.start - bottom.start) > SOURCE_SNAP_TOL_PT
                or abs(top.end - bottom.end) > SOURCE_SNAP_TOL_PT
                or abs(top.stroke_width - bottom.stroke_width) > 0.05
                or top.path_id == bottom.path_id
            ):
                continue
            panel_height = bottom.at - top.at
            for left in vs:
                if (
                    left.at >= lx0
                    or abs(left.at - top.start) > SOURCE_SNAP_TOL_PT
                    or abs(left.stroke_width - top.stroke_width) > 0.05
                    or left.start < top.at
                    or left.start > top.at + 0.20 * panel_height
                    or left.end > bottom.at
                    or left.end < bottom.at - 0.25 * panel_height
                    or left.end - left.start < 0.55 * panel_height
                ):
                    continue
                for right in vs:
                    if (
                        right.at <= lx1
                        or right.at <= top.end + SOURCE_SNAP_TOL_PT
                        or right.at >= top.end + 0.20 * panel_height
                        or abs(right.stroke_width - top.stroke_width) > 0.05
                        or right.start < top.at
                        or right.start > top.at + 0.20 * panel_height
                        or right.end > bottom.at
                        or right.end < bottom.at - 0.25 * panel_height
                        or right.end - right.start < 0.55 * panel_height
                    ):
                        continue
                    ids = (top.path_id, bottom.path_id, left.path_id, right.path_id)
                    if len(set(ids)) != 4:
                        continue
                    panel_width = right.at - left.at
                    if panel_width <= SOURCE_SNAP_TOL_PT:
                        continue
                    if abs(panel_width / panel_height - figured_ratio) > (
                        SOURCE_ASPECT_TOL_FRACTION * figured_ratio
                    ):
                        continue
                    if _continuous_rectangle_corners(top, bottom, left, right):
                        model = "continuous_closed_outline"
                        connectors = ()
                    else:
                        connected = _post_bounded_wall_connectors(
                            top, bottom, left, right, source_v, posts,
                        )
                        if connected is None:
                            continue
                        model = "source_post_bounded_open_bay"
                        connectors = connected
                    matched[ids] = SourceNativePhysicalFootprint(
                        boundary_source_path_ids=ids,
                        label_source_path_ids=label_ids,
                        native_bounds_pts=(left.at, top.at, right.at, bottom.at),
                        figured_width_mm=figured_width_mm,
                        figured_depth_mm=figured_depth_mm,
                        boundary_model=model,
                        connector_source_path_ids=connectors,
                    )
                    if len(matched) > 1:
                        return None
    return next(iter(matched.values())) if len(matched) == 1 else None
