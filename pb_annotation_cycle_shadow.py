"""Classify exact annotation blocks and their unstroked frames.

A primitive is quarantined only when every edge of its exact-endpoint block
lies on a cycle walk around one source word, or when it is an unstroked
filled rectangle framing that proven block. A ring that leaves part of the
block uncovered is not removed. Stroke colour, stroke width, and nearness to
text are never sufficient on their own. This module does not change the snap
tolerance.

The live wall authority does not call this module. Withholding the returned
ids from live wall input rekeys W2 split edges, W3 junctions, W4 walls and
sealed room quantities, so it needs a separate authority-promotion review.

The length spans reused here are the existing motif spans. Each is one
conjunct of the proof, not a standalone rejection.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
)
from pb_physical_wall_candidate_authority import (
    _REPEATED_MOTIF_MULTI_ANGLE_SPAN_FRACTION,
    _REPEATED_MOTIF_ORTHOGONAL_SPAN_FRACTION,
)

MIN_CYCLE_EDGES = 8
MIN_DISTINCT_DIRECTED_ANGLES = 8
_COLLINEAR_TOL_PT = 1e-4
_SOLID_DASHES = ("", "[] 0", "[]")
Point = Tuple[float, float]


def _path_index(segment: Mapping[str, Any]) -> Optional[int]:
    value = segment.get("path_index")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _dash_key(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and not value:
        return "[]"
    return "pattern"


def _usable_annotation_word(word: Mapping[str, Any]) -> bool:
    if not isinstance(word, Mapping):
        return False
    text = word.get("text")
    if not isinstance(text, str) or not text.strip():
        return False
    try:
        box = tuple(float(word[key]) for key in ("x0", "y0", "x1", "y1"))
    except (KeyError, TypeError, ValueError):
        return False
    x0, y0, x1, y1 = box
    return all(math.isfinite(value) for value in box) and x0 < x1 and y0 < y1


def _numeric_width(segment: Mapping[str, Any]) -> Optional[float]:
    value = segment.get("width")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, 6)


def _colour(value: Any) -> Optional[Tuple[float, ...]]:
    if not isinstance(value, (tuple, list)):
        return None
    if not value or any(isinstance(channel, bool) or not isinstance(channel, (int, float)) for channel in value):
        return None
    return tuple(round(float(channel), 6) for channel in value)


def _eligible_block_line(segment: Mapping[str, Any], duplicate_ids: set[str]) -> bool:
    if str(segment.get("kind") or "") != "line":
        return False
    sid = str(segment.get("id") or "")
    if not sid or sid in duplicate_ids:
        return False
    try:
        coords = tuple(float(segment[key]) for key in ("x1", "y1", "x2", "y2"))
    except (KeyError, TypeError, ValueError):
        return False
    stroke = segment.get("stroke")
    if stroke is not None and _colour(stroke) is None:
        return False
    if segment.get("fill") is not None:
        return False
    width = _numeric_width(segment)
    return all(math.isfinite(value) for value in coords) and _path_index(segment) is not None and width is not None and width > 0.0


def _family(segment: Mapping[str, Any]) -> Tuple[Any, ...]:
    return (
        str(segment.get("kind") or ""),
        _numeric_width(segment),
        _colour(segment.get("stroke")),
        _colour(segment.get("fill")),
        _dash_key(segment.get("dashes")),
    )


def _viewport_owns(points: Sequence[Point], viewport_bbox: Optional[Sequence[float]]) -> bool:
    if viewport_bbox is None:
        return False
    try:
        box = tuple(float(value) for value in viewport_bbox)
    except (TypeError, ValueError):
        return False
    if len(box) != 4 or not all(math.isfinite(value) for value in box):
        return False
    x0, y0, x1, y1 = box
    if x0 > x1 or y0 > y1:
        return False
    return all(x0 <= point[0] <= x1 and y0 <= point[1] <= y1 for point in points)


def _orient(p: Point, q: Point, r: Point) -> float:
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def _edges_properly_cross(a: Point, b: Point, c: Point, d: Point) -> bool:
    return _orient(a, b, c) * _orient(a, b, d) < 0.0 and _orient(c, d, a) * _orient(c, d, b) < 0.0


def _point_in_edge_interior(point: Point, start: Point, end: Point) -> bool:
    if point == start or point == end or start == end:
        return False
    if _orient(start, end, point) != 0.0:
        return False
    if start[0] != end[0]:
        return min(start[0], end[0]) < point[0] < max(start[0], end[0])
    return min(start[1], end[1]) < point[1] < max(start[1], end[1])


def _collinear_overlap(a: Point, b: Point, c: Point, d: Point) -> bool:
    if a == b or c == d:
        return False
    if _orient(a, b, c) != 0.0 or _orient(a, b, d) != 0.0:
        return False
    if abs(a[0] - b[0]) >= abs(a[1] - b[1]):
        left = max(min(a[0], b[0]), min(c[0], d[0]))
        right = min(max(a[0], b[0]), max(c[0], d[0]))
    else:
        left = max(min(a[1], b[1]), min(c[1], d[1]))
        right = min(max(a[1], b[1]), max(c[1], d[1]))
    return right - left > 0.0


def _cycle_edges_cross(vertices: Sequence[Point]) -> bool:
    """Reject a walk that is not a simple closed boundary.

    Adjacent edges may share their endpoint. A nonadjacent edge may not
    cross, touch an interior point, or overlap.
    """
    count = len(vertices)
    if count < 3 or len(set(vertices)) != count:
        return True
    for left in range(count):
        start = vertices[left]
        end = vertices[(left + 1) % count]
        if start == end:
            return True
        for right in range(left + 1, count):
            other_start = vertices[right]
            other_end = vertices[(right + 1) % count]
            adjacent = (left + 1) % count == right or (right + 1) % count == left
            if adjacent:
                shared = end if end == other_start or end == other_end else start
                loose = [point for point in (start, end, other_start, other_end) if point != shared]
                if any(
                    _point_in_edge_interior(point, start, end)
                    or _point_in_edge_interior(point, other_start, other_end)
                    for point in loose
                ):
                    return True
                continue
            if _edges_properly_cross(start, end, other_start, other_end):
                return True
            touches = (
                _point_in_edge_interior(start, other_start, other_end)
                or _point_in_edge_interior(end, other_start, other_end)
                or _point_in_edge_interior(other_start, start, end)
                or _point_in_edge_interior(other_end, start, end)
            )
            if touches or _collinear_overlap(start, end, other_start, other_end):
                return True
    return False


def _directed_angle_deg(a: Point, b: Point) -> float:
    return round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), 1)


def _strictly_inside(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    for i, origin in enumerate(polygon):
        nxt = polygon[(i + 1) % len(polygon)]
        cross = (nxt[0] - origin[0]) * (y - origin[1]) - (nxt[1] - origin[1]) * (x - origin[0])
        length = math.hypot(nxt[0] - origin[0], nxt[1] - origin[1])
        if length > 0.0 and abs(cross) / length <= _COLLINEAR_TOL_PT:
            proj = (x - origin[0]) * (nxt[0] - origin[0]) + (y - origin[1]) * (nxt[1] - origin[1])
            if -_COLLINEAR_TOL_PT <= proj <= length * length + _COLLINEAR_TOL_PT:
                return False
    inside = False
    j = len(polygon) - 1
    for i, current in enumerate(polygon):
        xi, yi = current
        xj, yj = polygon[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def _segment_crosses_box(a: Point, b: Point, box: Sequence[float]) -> bool:
    x0, y0, x1, y1 = (float(v) for v in box)
    if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1 or max(a[1], b[1]) < y0 or min(a[1], b[1]) > y1:
        return False
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1:
        return True
    if x0 <= b[0] <= x1 and y0 <= b[1] <= y1:
        return True
    def _cross(p, q, r, s) -> bool:
        def orient(u, v, w):
            return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
        o1, o2 = orient(p, q, r), orient(p, q, s)
        o3, o4 = orient(r, s, p), orient(r, s, q)
        return o1 * o2 < 0.0 and o3 * o4 < 0.0
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    sides = ((corners[i], corners[(i + 1) % 4]) for i in range(4))
    return any(_cross(a, b, p, q) for p, q in sides)


def _word_bbox_inside(word: Mapping[str, Any], polygon: Sequence[Point]) -> bool:
    box = (float(word["x0"]), float(word["y0"]), float(word["x1"]), float(word["y1"]))
    corners = ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))
    if not all(_strictly_inside(corner, polygon) for corner in corners):
        return False
    return not any(
        _segment_crosses_box(polygon[i], polygon[(i + 1) % len(polygon)], box)
        for i in range(len(polygon))
    )


def _collinear_extension(
    origin: Point, end: Point, other: Mapping[str, Any],
) -> bool:
    ax, ay = origin
    bx, by = end
    length = math.hypot(bx - ax, by - ay)
    if length <= _COLLINEAR_TOL_PT:
        return False
    def perp(px: float, py: float) -> float:
        return abs((px - ax) * (by - ay) - (py - ay) * (bx - ax)) / length
    def proj(px: float, py: float) -> float:
        return ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / length
    points = (
        (float(other["x1"]), float(other["y1"])),
        (float(other["x2"]), float(other["y2"])),
    )
    if any(perp(px, py) > _COLLINEAR_TOL_PT for px, py in points):
        return False
    projections = sorted(proj(px, py) for px, py in points)
    return projections[0] < -_COLLINEAR_TOL_PT or projections[1] > length + _COLLINEAR_TOL_PT


def _smooth_cycles(segments: Sequence[Mapping[str, Any]]) -> List[Tuple[List[str], List[Point]]]:
    """Trace closed cycles by the smallest turn at each exact shared endpoint.

    A face walk jumps into the gap between two rings that share vertices.
    The smallest turn stays on one ring. Endpoints stay the original floats:
    rounding them together is not a connection.
    """
    incidents: Dict[Point, List[Tuple[float, Point, str]]] = defaultdict(list)
    endpoints: Dict[str, Tuple[Point, Point]] = {}
    for segment in segments:
        if str(segment.get("kind") or "") != "line":
            continue
        start = (float(segment["x1"]), float(segment["y1"]))
        end = (float(segment["x2"]), float(segment["y2"]))
        if start == end or not segment.get("id"):
            continue
        sid = str(segment["id"])
        endpoints[sid] = (start, end)
        incidents[start].append((math.atan2(end[1] - start[1], end[0] - start[0]), end, sid))
        incidents[end].append((math.atan2(start[1] - end[1], start[0] - end[0]), start, sid))
    for vertex in incidents:
        incidents[vertex].sort(key=lambda item: (item[0], item[2]))
    used: set[Tuple[Point, str]] = set()
    cycles: List[Tuple[List[str], List[Point]]] = []
    for origin in sorted(incidents):
        for _angle, _neighbour, sid in incidents[origin]:
            if (origin, sid) in used:
                continue
            current = origin
            edge = sid
            ids: List[str] = []
            vertices: List[Point] = []
            closed = False
            for _step in range(len(endpoints) + 2):
                if (current, edge) in used:
                    break
                used.add((current, edge))
                ids.append(edge)
                start, end = endpoints[edge]
                arrived = end if current == start else start
                vertices.append(arrived)
                arrival = math.atan2(arrived[1] - current[1], arrived[0] - current[0])
                best: Optional[Tuple[float, str]] = None
                best_edge = None
                for out_angle, _nxt, candidate in incidents[arrived]:
                    if candidate == edge:
                        continue
                    if (arrived, candidate) in used and (arrived, candidate) != (origin, sid):
                        continue
                    turn = abs((out_angle - arrival + math.pi) % (2.0 * math.pi) - math.pi)
                    rank = (turn, candidate)
                    if best is None or rank < best:
                        best = rank
                        best_edge = candidate
                if best_edge is None:
                    break
                if (arrived, best_edge) == (origin, sid):
                    closed = True
                    break
                current, edge = arrived, best_edge
            simple = closed and len(ids) == len(set(ids)) and len(vertices) == len(set(vertices))
            if simple and len(ids) >= 3:
                cycles.append((ids, vertices))
    return cycles


def _edge_blocks(
    segments: Sequence[Mapping[str, Any]],
) -> List[frozenset[str]]:
    """Return exact-endpoint edge blocks of at least three edges.

    A walk inside a larger block is not quarantined by itself. Endpoint
    identity is the original float, with no snap and no rounding.
    """
    graph: Dict[Point, List[Tuple[Point, str]]] = defaultdict(list)
    for segment in segments:
        sid = str(segment.get("id") or "")
        if not sid:
            continue
        start = (float(segment["x1"]), float(segment["y1"]))
        end = (float(segment["x2"]), float(segment["y2"]))
        if start == end:
            continue
        graph[start].append((end, sid))
        graph[end].append((start, sid))
    discovery: Dict[Point, int] = {}
    low: Dict[Point, int] = {}
    edge_stack: List[str] = []
    blocks: List[List[str]] = []
    clock = 0
    ordered = {
        vertex: sorted(neighbours, key=lambda item: (item[1], item[0]))
        for vertex, neighbours in graph.items()
    }
    for root in sorted(ordered):
        if root in discovery:
            continue
        clock += 1
        discovery[root] = low[root] = clock
        frames: List[Tuple[Point, Optional[str], int]] = [(root, None, 0)]
        while frames:
            vertex, parent_edge, cursor = frames[-1]
            adjacent = ordered[vertex]
            if cursor < len(adjacent):
                neighbour, edge_id = adjacent[cursor]
                frames[-1] = (vertex, parent_edge, cursor + 1)
                if edge_id == parent_edge:
                    continue
                if neighbour not in discovery:
                    edge_stack.append(edge_id)
                    clock += 1
                    discovery[neighbour] = low[neighbour] = clock
                    frames.append((neighbour, edge_id, 0))
                elif discovery[neighbour] < discovery[vertex]:
                    edge_stack.append(edge_id)
                    low[vertex] = min(low[vertex], discovery[neighbour])
                continue
            frames.pop()
            if not frames:
                continue
            parent_vertex = frames[-1][0]
            low[parent_vertex] = min(low[parent_vertex], low[vertex])
            if low[vertex] >= discovery[parent_vertex] and parent_edge is not None:
                block: List[str] = []
                while edge_stack:
                    member = edge_stack.pop()
                    block.append(member)
                    if member == parent_edge:
                        break
                blocks.append(block)
    return [frozenset(members) for members in blocks if len(members) >= 3]


def _prove_block(
    block: frozenset[str],
    members: Sequence[Mapping[str, Any]],
    *,
    page_span: float,
    path_counts: Mapping[Any, int],
    words: Sequence[Tuple[Tuple[float, float, float, float], Mapping[str, Any]]],
    outside: Any,
    viewport_bbox: Optional[Sequence[float]],
) -> Dict[str, Any]:
    """Prove a whole edge block, or withhold nothing from it.

    One source word must sit inside cycle walks that together use every edge.
    A ring that leaves part of the block uncovered does not quarantine the rest.
    ``outside`` yields only segments that pass ``_competing_stroke``.
    """
    ids = sorted(block)
    angles = []
    max_length = 0.0
    points: List[Point] = []
    for segment in members:
        start = (float(segment["x1"]), float(segment["y1"]))
        end = (float(segment["x2"]), float(segment["y2"]))
        angles.append(_directed_angle_deg(start, end))
        max_length = max(max_length, math.dist(start, end))
        points.extend((start, end))
    span_limit = float(page_span) * float(_REPEATED_MOTIF_MULTI_ANGLE_SPAN_FRACTION)
    reasons = []
    if len(ids) < MIN_CYCLE_EDGES:
        reasons.append("cycle_edge_count_below_symbol_topology")
    if len(set(angles)) < MIN_DISTINCT_DIRECTED_ANGLES:
        reasons.append("directed_angle_diversity_below_symbol_topology")
    if max_length > span_limit:
        reasons.append("cycle_edge_exceeds_existing_multi_angle_span")
    if any(_path_index(segment) is None for segment in members) or not all(
        path_counts.get(_path_index(segment), 0) == 1 for segment in members
    ):
        reasons.append("path_ancestry_not_singleton")
    if not all(_dash_key(segment.get("dashes")) in _SOLID_DASHES for segment in members):
        reasons.append("stroke_or_fill_not_a_bare_solid_mark")
    if not all(segment.get("fill") is None for segment in members):
        reasons.append("stroke_or_fill_not_a_bare_solid_mark")
    contained = []
    extensions: List[str] = []
    owned = False
    if not reasons:
        covered_by_word: Dict[Tuple[float, float, float, float], set[str]] = {}
        word_by_box = {}
        for ids_walk, vertices in _smooth_cycles(members):
            if _cycle_edges_cross(vertices):
                continue
            left = min(point[0] for point in vertices)
            right = max(point[0] for point in vertices)
            low = min(point[1] for point in vertices)
            high = max(point[1] for point in vertices)
            for box, word in words:
                if box[0] <= left or box[2] >= right or box[1] <= low or box[3] >= high:
                    continue
                if not _word_bbox_inside(word, vertices):
                    continue
                covered_by_word.setdefault(box, set()).update(ids_walk)
                word_by_box[box] = word
        contained = [
            {"text": str(word_by_box[box].get("text") or ""), "bbox": list(box)}
            for box, covered in covered_by_word.items()
            if covered == set(ids)
        ]
        if not contained:
            reasons.append("block_not_covered_by_one_source_word")
        seen: set[str] = set()
        for member in members:
            start = (float(member["x1"]), float(member["y1"]))
            end = (float(member["x2"]), float(member["y2"]))
            for segment in outside(start, end):
                sid = str(segment.get("id") or "")
                if sid in seen or sid in block:
                    continue
                if _collinear_extension(start, end, segment):
                    seen.add(sid)
                    extensions.append(sid)
        if extensions:
            reasons.append("competing_structural_continuation")
        owned = _viewport_owns(points, viewport_bbox)
        if not owned:
            reasons.append("viewport_partition_ownership_unproven")
    proven = not reasons
    return {
        "primitive_ids": ids,
        "path_indexes": sorted(
            {index for index in (_path_index(segment) for segment in members) if index is not None}
        ),
        "contained_source_text": contained,
        "competing_continuation_primitive_ids": sorted(extensions),
        "max_edge_length_pt": round(max_length, 6),
        "existing_multi_angle_span_limit_pt": round(span_limit, 6),
        "distinct_directed_angles": len(set(angles)),
        "viewport_partition_owned": owned,
        "status": "source_proven_annotation_cycle" if proven else "annotation_cycle_not_proven",
        "failed_gates": reasons,
        "structural_wall_role_authenticated": False,
        "quantity_or_metric_area_published": False,
        "diagnostic_only": True,
    }



def _competing_stroke(segment: Mapping[str, Any], span_limit: float) -> bool:
    if not str(segment.get("id") or ""):
        return False
    if _colour(segment.get("stroke")) is None or not (_numeric_width(segment) or 0.0) > 0.0:
        return False
    length = math.hypot(
        float(segment["x2"]) - float(segment["x1"]),
        float(segment["y2"]) - float(segment["y1"]),
    )
    return length > span_limit


def _nearby_segments(segments: Sequence[Mapping[str, Any]]):
    cell = 25.0
    grid: Dict[Tuple[int, int], List[Mapping[str, Any]]] = defaultdict(list)
    for segment in segments:
        xs = (float(segment["x1"]), float(segment["x2"]))
        ys = (float(segment["y1"]), float(segment["y2"]))
        for ix in range(math.floor(min(xs) / cell), math.floor(max(xs) / cell) + 1):
            for iy in range(math.floor(min(ys) / cell), math.floor(max(ys) / cell) + 1):
                grid[(ix, iy)].append(segment)

    def nearby(start: Point, end: Point):
        found: Dict[int, Mapping[str, Any]] = {}
        pad = 1.0
        xs = (start[0], end[0])
        ys = (start[1], end[1])
        for ix in range(math.floor((min(xs) - pad) / cell), math.floor((max(xs) + pad) / cell) + 1):
            for iy in range(math.floor((min(ys) - pad) / cell), math.floor((max(ys) + pad) / cell) + 1):
                for segment in grid.get((ix, iy), ()):
                    found[id(segment)] = segment
        return found.values()

    return nearby


def _undirected_edge(start: Point, end: Point) -> Tuple[Point, Point]:
    return (start, end) if start <= end else (end, start)


def _rectangle_side(start: Point, end: Point, bounds: Tuple[float, float, float, float]) -> Optional[str]:
    min_x, min_y, max_x, max_y = bounds
    x1, y1 = start
    x2, y2 = end
    if y1 == y2 == min_y and {x1, x2} == {min_x, max_x}:
        return "bottom"
    if y1 == y2 == max_y and {x1, x2} == {min_x, max_x}:
        return "top"
    if x1 == x2 == min_x and {y1, y2} == {min_y, max_y}:
        return "left"
    if x1 == x2 == max_x and {y1, y2} == {min_y, max_y}:
        return "right"
    return None


def _one_closed_rectangle(edges: Sequence[Mapping[str, Any]], limit: float) -> bool:
    """Four distinct sides, one per rectangle edge, joined at the original corners."""
    if len(edges) != 4:
        return False
    parsed: List[Tuple[Point, Point, str]] = []
    undirected = set()
    for edge in edges:
        start = (float(edge["x1"]), float(edge["y1"]))
        end = (float(edge["x2"]), float(edge["y2"]))
        if start == end:
            return False
        if start[0] != end[0] and start[1] != end[1]:
            return False
        if math.hypot(end[0] - start[0], end[1] - start[1]) > limit:
            return False
        key = _undirected_edge(start, end)
        if key in undirected:
            return False
        undirected.add(key)
        parsed.append((start, end, str(edge.get("id") or "")))
    if len(undirected) != 4:
        return False
    xs = [value for start, end, _sid in parsed for value in (start[0], end[0])]
    ys = [value for start, end, _sid in parsed for value in (start[1], end[1])]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if min_x == max_x or min_y == max_y:
        return False
    bounds = (min_x, min_y, max_x, max_y)
    sides: Dict[str, Tuple[Point, Point]] = {}
    for start, end, _sid in parsed:
        side = _rectangle_side(start, end, bounds)
        if side is None or side in sides:
            return False
        sides[side] = (start, end)
    if set(sides) != {"top", "bottom", "left", "right"}:
        return False
    corners = {
        (min_x, min_y): 0, (max_x, min_y): 0,
        (max_x, max_y): 0, (min_x, max_y): 0,
    }
    for start, end in sides.values():
        if start not in corners or end not in corners:
            return False
        corners[start] += 1
        corners[end] += 1
    return all(count == 2 for count in corners.values())


def _unstroked_frames_around_proven_cycles(
    segments: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    *,
    page_span: float,
) -> List[str]:
    """Return unstroked rectangle edges that frame a proven annotation cycle.

    The rectangle must be the only content of one path: four axis-aligned
    edges of one item, with fill and no stroke. Each side stays within the
    existing orthogonal motif span, and a proven cycle's source word box lies
    strictly inside. Colour is not used.
    """
    words = [
        {
            "x0": float(text["bbox"][0]), "y0": float(text["bbox"][1]),
            "x1": float(text["bbox"][2]), "y1": float(text["bbox"][3]),
        }
        for record in records
        if record["status"] == "source_proven_annotation_cycle"
        for text in record["contained_source_text"]
    ]
    if not words:
        return []
    limit = float(page_span) * float(_REPEATED_MOTIF_ORTHOGONAL_SPAN_FRACTION)
    path_totals: Dict[int, int] = defaultdict(int)
    for segment in segments:
        index = _path_index(segment)
        if index is not None:
            path_totals[index] += 1
    groups: Dict[Any, List[Mapping[str, Any]]] = defaultdict(list)
    for segment in segments:
        if str(segment.get("kind") or "") != "rect_edge" or not segment.get("id"):
            continue
        try:
            coords = tuple(float(segment[key]) for key in ("x1", "y1", "x2", "y2"))
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in coords):
            continue
        if segment.get("stroke") is not None or segment.get("fill") is None:
            continue
        if segment.get("width") not in (None, 0, 0.0):
            continue
        index = _path_index(segment)
        if index is None:
            continue
        groups[index].append(segment)
    found: List[str] = []
    for index, edges in groups.items():
        if path_totals[index] != len(edges):
            continue
        if len({repr(edge.get("item_index")) for edge in edges}) != 1:
            continue
        if not _one_closed_rectangle(edges, limit):
            continue
        xs = [float(value) for edge in edges for value in (edge["x1"], edge["x2"])]
        ys = [float(value) for edge in edges for value in (edge["y1"], edge["y2"])]
        polygon = (
            (min(xs), min(ys)), (max(xs), min(ys)),
            (max(xs), max(ys)), (min(xs), max(ys)),
        )
        if any(_word_bbox_inside(word, polygon) for word in words):
            found.extend(str(edge["id"]) for edge in edges)
    return sorted(set(found))


def classify_exact_annotation_cycles(
    segments: Sequence[Mapping[str, Any]],
    words: Sequence[Mapping[str, Any]],
    *,
    page_span: float,
    viewport_bbox: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Return source-proven annotation cycles. Unproven cycles are not quarantined."""
    try:
        span = float(page_span)
    except (TypeError, ValueError) as error:
        raise ValueError("annotation cycle classification requires a positive page span") from error
    if not math.isfinite(span) or span <= 0.0:
        raise ValueError("annotation cycle classification requires a positive page span")
    segments = [segment for segment in segments if isinstance(segment, Mapping)]
    words = [word for word in words if _usable_annotation_word(word)]
    id_counts: Dict[str, int] = defaultdict(int)
    for segment in segments:
        sid = str(segment.get("id") or "")
        if sid:
            id_counts[sid] += 1
    duplicate_ids = {sid for sid, count in id_counts.items() if count > 1}
    by_id = {
        str(segment["id"]): segment
        for segment in segments
        if _eligible_block_line(segment, duplicate_ids)
    }
    path_counts: Dict[int, int] = defaultdict(int)
    for segment in segments:
        index = _path_index(segment)
        if index is not None:
            path_counts[index] += 1
    families: Dict[Tuple[Any, ...], List[Mapping[str, Any]]] = defaultdict(list)
    for segment in by_id.values():
        families[_family(segment)].append(segment)
    records = []
    span_limit = span * float(_REPEATED_MOTIF_MULTI_ANGLE_SPAN_FRACTION)
    competitors = []
    for segment in segments:
        try:
            coords = tuple(float(segment[key]) for key in ("x1", "y1", "x2", "y2"))
        except (KeyError, TypeError, ValueError):
            continue
        if all(math.isfinite(value) for value in coords) and _competing_stroke(segment, span_limit):
            competitors.append(segment)
    nearby = _nearby_segments(competitors)
    word_boxes = [
        ((float(word["x0"]), float(word["y0"]), float(word["x1"]), float(word["y1"])), word)
        for word in words
    ]
    for family_segments in families.values():
        for block in _edge_blocks(family_segments):
            members = [by_id[sid] for sid in block]
            records.append(_prove_block(
                block, members, page_span=float(page_span), path_counts=path_counts,
                words=word_boxes, outside=nearby, viewport_bbox=viewport_bbox,
            ))
    records.sort(key=lambda record: (record["status"], record["primitive_ids"]))
    frames = _unstroked_frames_around_proven_cycles(
        segments, records, page_span=float(page_span),
    )
    quarantined = sorted({
        sid
        for record in records
        if record["status"] == "source_proven_annotation_cycle"
        for sid in record["primitive_ids"]
    } | set(frames))
    return {
        "cycles": records,
        "quarantined_primitive_ids": quarantined,
        "frame_primitive_ids": frames,
        "structural_wall_role_authenticated": False,
        "quantity_or_metric_area_published": False,
        "diagnostic_only": True,
    }


def segments_without_proven_annotation_cycles(
    segments: Sequence[Mapping[str, Any]],
    words: Sequence[Mapping[str, Any]],
    *,
    page_span: float,
    viewport_bbox: Optional[Sequence[float]],
) -> tuple:
    """Drop only primitives that belong to a fully proven annotation cycle.

    No words, no viewport, or no proven cycle leaves the input unchanged.
    This does not change snap tolerance or classify a stroke by colour alone.
    """
    if not words or viewport_bbox is None:
        return tuple(segments)
    classified = classify_exact_annotation_cycles(
        segments, words, page_span=page_span, viewport_bbox=viewport_bbox,
    )
    withheld = set(classified["quarantined_primitive_ids"])
    if not withheld:
        return tuple(segments)
    return tuple(
        segment for segment in segments
        if str(segment.get("id") or "") not in withheld
    )


_UNTRUSTED_WORD_REASONS = frozenset({
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    TEXT_CLIP_STATE_UNRESOLVED,
})


def annotation_words_from_text_receipts(
    receipts: Optional[Sequence[object]],
) -> Tuple[Dict[str, Any], ...]:
    """Word boxes from producer text receipts that may prove an annotation cycle.

    Decoded text is not used, so an unverified glyph mapping or an unresolved
    clip state does not exclude a word. Any other integrity reason, such as an
    invisible render mode, zero opacity, hidden optional content, a clip that
    removes the word, or later paint covering it, does.
    """
    words = []
    for receipt in receipts or ():
        if not bool(getattr(receipt, "trusted", False)):
            reasons = getattr(receipt, "reason_codes", ()) or ()
            if not isinstance(reasons, (tuple, list)):
                continue
            if not reasons or not set(reasons) <= _UNTRUSTED_WORD_REASONS:
                continue
        text = getattr(receipt, "raw_text", "")
        geometry = getattr(receipt, "geometry", None)
        if not isinstance(text, str) or not text.strip() or geometry is None:
            continue
        try:
            box = tuple(float(value) for value in geometry)
        except (TypeError, ValueError):
            continue
        if len(box) != 4 or not all(math.isfinite(value) for value in box):
            continue
        if not (box[0] < box[2] and box[1] < box[3]):
            continue
        words.append({
            "text": text, "x0": box[0], "y0": box[1], "x1": box[2], "y1": box[3],
        })
    return tuple(words)


def scope_segments_without_proven_annotation_cycles(
    segments: Sequence[Mapping[str, Any]],
    *,
    classification_segments: Sequence[Mapping[str, Any]],
    text_receipts: Optional[Sequence[object]],
    page_width: float,
    page_height: float,
    viewport_bbox: Optional[Sequence[float]] = None,
) -> tuple:
    """Replay one wall scope's graph input with proven annotation cycles withheld.

    The cycle is proved on the scope segments before the motif filter, so a
    bubble whose other chords were already removed still identifies the chords
    that remain. No admissible word, an unreadable page size or a malformed
    viewport leaves the input unchanged. No viewport means the page box.
    """
    words = annotation_words_from_text_receipts(text_receipts)
    if not words:
        return tuple(segments)
    try:
        width = float(page_width)
        height = float(page_height)
    except (TypeError, ValueError):
        return tuple(segments)
    span = min(width, height)
    if not math.isfinite(width) or not math.isfinite(height) or span <= 0.0:
        return tuple(segments)
    raw_box = (0.0, 0.0, width, height) if viewport_bbox is None else viewport_bbox
    try:
        bbox = tuple(float(value) for value in raw_box)
    except (TypeError, ValueError):
        return tuple(segments)
    if len(bbox) != 4 or not all(math.isfinite(value) for value in bbox):
        return tuple(segments)
    if bbox[0] > bbox[2] or bbox[1] > bbox[3]:
        return tuple(segments)
    classified = classify_exact_annotation_cycles(
        classification_segments, words, page_span=span, viewport_bbox=bbox,
    )
    withheld = set(classified["quarantined_primitive_ids"])
    if not withheld:
        return tuple(segments)
    return tuple(
        segment for segment in segments
        if not isinstance(segment, Mapping) or str(segment.get("id") or "") not in withheld
    )


def without_proven_annotation_cycles_for_scope(
    segments: Sequence[Mapping[str, Any]],
    *,
    classification_segments: Sequence[Mapping[str, Any]],
    text_receipts: Optional[Sequence[object]],
    page_width: float,
    page_height: float,
    viewport: Any = None,
) -> tuple:
    """Diagnostic replay using a viewport object. Not a live wall-authority call.

    Production must not import this helper. A viewport without a bounding box
    uses the page box, matching the former unwired production adapter.
    """
    bbox = None
    if viewport is not None and getattr(viewport, "bounding_box", None) is not None:
        bbox = viewport.bounding_box
    return scope_segments_without_proven_annotation_cycles(
        segments,
        classification_segments=classification_segments,
        text_receipts=text_receipts,
        page_width=page_width,
        page_height=page_height,
        viewport_bbox=bbox,
    )


# Diagnostic alias kept for existing shadow tests. Not a production import.
_without_proven_annotation_cycles = without_proven_annotation_cycles_for_scope


def _lineage_ids(edge: Mapping[str, Any]) -> Tuple[str, ...]:
    payload = edge.get("primitive_lineage") or {}
    return tuple(sorted(str(item) for item in payload.get("source_primitive_ids") or ()))


def shadow_annotation_cycle_topology(
    segments: Sequence[Mapping[str, Any]],
    words: Sequence[Mapping[str, Any]],
    *,
    page_span: float,
    viewport_bbox: Sequence[float],
    document_id: str,
    page_id: str,
    viewport_id: str,
) -> Dict[str, Any]:
    """Replay W2, W3, and W4 with proven annotation cycles withheld from the snap input.

    The withheld primitives stay in this report. Production graph functions are
    called on copies and are not modified.
    """
    from pb_wall_room_topology_junction_classifier import classify_junctions
    from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
    from pb_wall_room_topology_wall_assembly import assemble_wall_candidates

    classification = classify_exact_annotation_cycles(
        segments, words, page_span=page_span, viewport_bbox=viewport_bbox,
    )
    quarantined = set(classification["quarantined_primitive_ids"])
    baseline_input = [dict(segment) for segment in segments]
    shadow_input = [dict(segment) for segment in segments if str(segment.get("id")) not in quarantined]
    baseline = build_wall_graph_for_viewport(baseline_input)
    shadow = build_wall_graph_for_viewport(shadow_input)

    def unaffected(graph: Mapping[str, Any]) -> List[Tuple[Tuple[str, ...], Tuple[float, ...]]]:
        rows = []
        for edge in graph["edges"]:
            if edge.get("_removed"):
                continue
            parents = _lineage_ids(edge)
            if quarantined.intersection(parents):
                continue
            geometry = tuple(round(float(edge[key]), 6) for key in ("x1", "y1", "x2", "y2"))
            rows.append((parents, geometry))
        return sorted(rows)

    def stage(graph: Mapping[str, Any]) -> Dict[str, Any]:
        junctions, relationships = classify_junctions(
            graph, document_id=document_id, page_id=page_id, viewport_id=viewport_id,
        )
        walls, _mapping = assemble_wall_candidates(
            graph, junctions, relationships, viewport_id=viewport_id,
        )
        edge_lineage = {
            str(edge["id"]): _lineage_ids(edge)
            for edge in graph["edges"]
            if not edge.get("_removed")
        }
        return {
            "w2_edge_count": sum(1 for edge in graph["edges"] if not edge.get("_removed")),
            "w2_nodes": [
                {
                    "x": round(float(node["x"]), 9),
                    "y": round(float(node["y"]), 9),
                    "samples": node.get("samples"),
                    "degree": node.get("degree"),
                }
                for node in graph["nodes"]
            ],
            "w3": [
                {
                    "junction_type": item.junction_type.value,
                    "status": item.status.value,
                    "incident_edge_ids": list(item.incident_wall_candidate_ids),
                }
                for item in junctions
            ],
            "w4_centerlines": [
                [list(point) for point in wall.centerline_pts]
                for wall in walls
            ],
            "w4_source_primitive_ids": [
                sorted({
                    sid
                    for edge_id in wall.face_a_segment_ids
                    for sid in edge_lineage.get(str(edge_id), ())
                })
                for wall in walls
            ],
        }

    baseline_stage = stage(baseline)
    shadow_stage = stage(shadow)
    return {
        "classification": classification,
        "baseline": baseline_stage,
        "shadow_with_proven_cycles_withheld_from_snap_input": shadow_stage,
        "unaffected_non_annotation_edge_geometry_unchanged": (
            unaffected(baseline) == unaffected(shadow)
        ),
        "structural_wall_role_authenticated": False,
        "quantity_or_metric_area_published": False,
        "diagnostic_only": True,
    }


def wall_annotation_ancestry(
    source_primitive_ids: Sequence[str],
    quarantined_primitive_ids: Sequence[str],
) -> str:
    """Classify one minted wall's source lineage against proven annotation ids.

    A wall with no lineage cannot be dropped. A wall whose every source
    primitive is quarantined is annotation-only after identity minting. A
    mixed ancestor set must be retained: dropping any shared primitive
    remumbers ordinal W2/W3 ids for the surviving wall.
    """
    source = {str(sid) for sid in source_primitive_ids if sid}
    quarantined = {str(sid) for sid in quarantined_primitive_ids if sid}
    if not source:
        return "no_source_lineage"
    if source <= quarantined:
        return "annotation_only"
    if source & quarantined:
        return "mixed_annotation_ancestry"
    return "no_annotation_ancestry"


def shadow_annotation_cycle_post_identity_report(
    segments: Sequence[Mapping[str, Any]],
    words: Sequence[Mapping[str, Any]],
    *,
    page_span: float,
    viewport_bbox: Sequence[float],
    document_id: str,
    page_id: str,
    viewport_id: str,
) -> Dict[str, Any]:
    """Mint W2/W3/W4 on the full primitive set, then flag annotation-only walls.

    OBSERVED: live pre-snap withhold remumbers ordinal W2 split-edge ids and
    W3 junction ids. Maryborough CI rekeyed COLD ROOM
    ``floor_area_quantity_6b28b3abaedf519631ed`` to
    ``floor_area_quantity_ed0dc95147b9485a6009`` while the physical floor id
    and 43 wall evidence ids stayed. INFERENCE: room-face and quantity
    identity consume those ordinal ids. PROPOSED: do not drop primitives
    before snap; flag walls whose source lineage is entirely quarantined
    after identities exist. BENCHMARK scores, project names, and expected
    BOQ values must not set this filter. No quantity is published.
    """
    from pb_wall_room_topology_junction_classifier import classify_junctions
    from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
    from pb_wall_room_topology_wall_assembly import assemble_wall_candidates

    classification = classify_exact_annotation_cycles(
        segments, words, page_span=page_span, viewport_bbox=viewport_bbox,
    )
    quarantined = tuple(classification["quarantined_primitive_ids"])
    quarantined_set = set(quarantined)
    baseline_input = [dict(segment) for segment in segments]
    graph = build_wall_graph_for_viewport(baseline_input)
    junctions, relationships = classify_junctions(
        graph, document_id=document_id, page_id=page_id, viewport_id=viewport_id,
    )
    walls, _mapping = assemble_wall_candidates(
        graph, junctions, relationships, viewport_id=viewport_id,
    )
    edge_lineage = {
        str(edge["id"]): _lineage_ids(edge)
        for edge in graph["edges"]
        if not edge.get("_removed")
    }
    minted = []
    for wall in walls:
        source_ids = sorted({
            sid
            for edge_id in wall.face_a_segment_ids
            for sid in edge_lineage.get(str(edge_id), ())
        })
        minted.append({
            "candidate_id": wall.candidate_id,
            "face_a_segment_ids": list(wall.face_a_segment_ids),
            "source_primitive_ids": source_ids,
            "ancestry": wall_annotation_ancestry(source_ids, quarantined),
        })
    minted.sort(key=lambda row: row["candidate_id"])
    withheld_input = [
        dict(segment) for segment in segments
        if str(segment.get("id") or "") not in quarantined_set
    ]
    withheld_graph = build_wall_graph_for_viewport(withheld_input)
    withheld_edges = sorted(
        str(edge["id"])
        for edge in withheld_graph["edges"]
        if not edge.get("_removed")
    )
    baseline_edges = sorted(
        str(edge["id"])
        for edge in graph["edges"]
        if not edge.get("_removed")
    )
    return {
        "classification": classification,
        "minted_walls": minted,
        "annotation_only_wall_ids": [
            row["candidate_id"] for row in minted if row["ancestry"] == "annotation_only"
        ],
        "mixed_annotation_wall_ids": [
            row["candidate_id"]
            for row in minted
            if row["ancestry"] == "mixed_annotation_ancestry"
        ],
        "surviving_wall_ids": [
            row["candidate_id"]
            for row in minted
            if row["ancestry"] in {
                "no_annotation_ancestry",
                "mixed_annotation_ancestry",
                "no_source_lineage",
            }
        ],
        "pre_snap_withhold_changes_ordinal_w2_edge_ids": withheld_edges != baseline_edges,
        "structural_wall_role_authenticated": False,
        "quantity_or_metric_area_published": False,
        "diagnostic_only": True,
    }
