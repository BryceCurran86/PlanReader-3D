"""Classify exact closed annotation stroke cycles and their unstroked frames.

A primitive is quarantined only when a whole cycle proves every gate, or when
it is an unstroked filled rectangle framing such a cycle. Stroke colour,
stroke width, and nearness to text are never sufficient on their own. This
module does not change the snap tolerance. A caller may drop the returned
ids before building the wall graph.

The length spans reused here are the existing motif spans. Each is one
conjunct of the proof, not a standalone rejection.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from pb_physical_wall_candidate_authority import (
    _REPEATED_MOTIF_MULTI_ANGLE_SPAN_FRACTION,
    _REPEATED_MOTIF_ORTHOGONAL_SPAN_FRACTION,
)

EXACT_ENDPOINT_DECIMALS = 6
MIN_CYCLE_EDGES = 8
MIN_DISTINCT_DIRECTED_ANGLES = 8
_COLLINEAR_TOL_PT = 1e-4
_SOLID_DASHES = ("", "[] 0", "[]")
Point = Tuple[float, float]


def _endpoint_key(x: float, y: float) -> Point:
    return (round(float(x), EXACT_ENDPOINT_DECIMALS), round(float(y), EXACT_ENDPOINT_DECIMALS))


def _family(segment: Mapping[str, Any]) -> Tuple[Any, ...]:
    stroke = segment.get("stroke")
    if isinstance(stroke, tuple):
        stroke = tuple(round(float(v), 6) for v in stroke)
    else:
        stroke = None
    fill = segment.get("fill")
    if isinstance(fill, tuple):
        fill = tuple(round(float(v), 6) for v in fill)
    width = segment.get("width")
    try:
        width = round(float(width), 6)
    except (TypeError, ValueError):
        width = None
    return (
        str(segment.get("kind") or ""),
        width,
        stroke,
        fill,
        str(segment.get("dashes") or ""),
    )


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
    The smallest turn stays on one ring. This does not join nearby endpoints.
    """
    incidents: Dict[Point, List[Tuple[float, Point, str]]] = defaultdict(list)
    endpoints: Dict[str, Tuple[Point, Point]] = {}
    for segment in segments:
        if str(segment.get("kind") or "") != "line":
            continue
        start = _endpoint_key(float(segment["x1"]), float(segment["y1"]))
        end = _endpoint_key(float(segment["x2"]), float(segment["y2"]))
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


def _cycle_record(
    ids: Sequence[str],
    polygon: Sequence[Point],
    by_id: Mapping[str, Mapping[str, Any]],
    *,
    page_span: float,
    path_counts: Mapping[Any, int],
    words: Sequence[Mapping[str, Any]],
    outside: Any,
    viewport_bbox: Optional[Sequence[float]],
) -> Dict[str, Any]:
    members = [by_id[sid] for sid in ids]
    ring = list(polygon)
    angles = [
        _directed_angle_deg(ring[index], ring[(index + 1) % len(ring)])
        for index in range(len(ring))
    ]
    max_length = max(
        math.dist(ring[index], ring[(index + 1) % len(ring)])
        for index in range(len(ring))
    )
    path_ids = sorted({int(segment["path_index"]) for segment in members})
    span_limit = float(page_span) * float(_REPEATED_MOTIF_MULTI_ANGLE_SPAN_FRACTION)
    singleton = all(
        path_counts.get(segment.get("path_index"), 0) == 1 for segment in members
    )
    solid = all(str(segment.get("dashes") or "") in _SOLID_DASHES for segment in members)
    unfilled = all(segment.get("fill") is None for segment in members)
    reasons = []
    if len(ring) != len(ids):
        reasons.append("cycle_walk_not_continuous")
    if len(ids) < MIN_CYCLE_EDGES:
        reasons.append("cycle_edge_count_below_symbol_topology")
    if len(set(angles)) < MIN_DISTINCT_DIRECTED_ANGLES:
        reasons.append("directed_angle_diversity_below_symbol_topology")
    if max_length > span_limit:
        reasons.append("cycle_edge_exceeds_existing_multi_angle_span")
    if not singleton:
        reasons.append("path_ancestry_not_singleton")
    if not solid or not unfilled:
        reasons.append("stroke_or_fill_not_a_bare_solid_mark")
    contained = []
    extensions: list[str] = []
    owned = False
    if not reasons:
        if len(ring) >= 3:
            contained = [
                {
                    "text": str(word.get("text") or ""),
                    "bbox": [float(word["x0"]), float(word["y0"]), float(word["x1"]), float(word["y1"])],
                }
                for word in words
                if _word_bbox_inside(word, ring)
            ]
        if not contained:
            reasons.append("no_source_text_bbox_contained")
        seen: set[str] = set()
        for member in members:
            start = _endpoint_key(float(member["x1"]), float(member["y1"]))
            end = _endpoint_key(float(member["x2"]), float(member["y2"]))
            for segment in outside(start, end):
                sid = str(segment.get("id") or "")
                if not sid or sid in seen or sid in ids:
                    continue
                if segment.get("stroke") is None or not segment.get("width"):
                    continue
                other_length = math.hypot(
                    float(segment["x2"]) - float(segment["x1"]),
                    float(segment["y2"]) - float(segment["y1"]),
                )
                if other_length <= span_limit:
                    continue
                if _collinear_extension(start, end, segment):
                    seen.add(sid)
                    extensions.append(sid)
        if extensions:
            reasons.append("competing_structural_continuation")
        if viewport_bbox is None:
            owned = False
            reasons.append("viewport_partition_ownership_unproven")
        else:
            x0, y0, x1, y1 = (float(value) for value in viewport_bbox)
            owned = all(x0 <= point[0] <= x1 and y0 <= point[1] <= y1 for point in ring)
            if not owned:
                reasons.append("viewport_partition_ownership_unproven")
    proven = not reasons
    return {
        "primitive_ids": list(ids),
        "path_indexes": path_ids,
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


def _unstroked_frames_around_proven_cycles(
    segments: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    *,
    page_span: float,
) -> List[str]:
    """Return unstroked rectangle edges that frame a proven annotation cycle.

    The rectangle must be four axis-aligned edges of one path, with fill and
    no stroke. Each side stays within the existing orthogonal motif span, and
    a proven cycle's source word box lies strictly inside. Colour is not used.
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
    groups: Dict[Any, List[Mapping[str, Any]]] = defaultdict(list)
    for segment in segments:
        if str(segment.get("kind") or "") != "rect_edge" or not segment.get("id"):
            continue
        if segment.get("stroke") is not None or segment.get("width") or segment.get("fill") is None:
            continue
        groups[segment.get("path_index")].append(segment)
    found: List[str] = []
    for edges in groups.values():
        if len(edges) != 4:
            continue
        xs: List[float] = []
        ys: List[float] = []
        short_axis_aligned = True
        for edge in edges:
            x1, y1 = float(edge["x1"]), float(edge["y1"])
            x2, y2 = float(edge["x2"]), float(edge["y2"])
            axis_aligned = abs(x1 - x2) <= 1e-4 or abs(y1 - y2) <= 1e-4
            if not axis_aligned or math.hypot(x2 - x1, y2 - y1) > limit:
                short_axis_aligned = False
                break
            xs.extend((x1, x2))
            ys.extend((y1, y2))
        if not short_axis_aligned:
            continue
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
    if not math.isfinite(float(page_span)) or float(page_span) <= 0.0:
        raise ValueError("annotation cycle classification requires a positive page span")
    by_id = {str(segment["id"]): segment for segment in segments if segment.get("id")}
    path_counts: Dict[Any, int] = defaultdict(int)
    for segment in segments:
        path_counts[segment.get("path_index")] += 1
    families: Dict[Tuple[Any, ...], List[Mapping[str, Any]]] = defaultdict(list)
    for segment in segments:
        if str(segment.get("kind") or "") == "line" and segment.get("id"):
            families[_family(segment)].append(segment)
    records = []
    nearby = _nearby_segments(list(by_id.values()))
    for family_segments in families.values():
        seen_cycles: set[frozenset[str]] = set()
        for ids, vertices in _smooth_cycles(family_segments):
            identity = frozenset(ids)
            if identity in seen_cycles:
                continue
            seen_cycles.add(identity)
            ordered = list(ids)
            record = _cycle_record(
                ordered, vertices, by_id, page_span=float(page_span), path_counts=path_counts,
                words=words, outside=nearby, viewport_bbox=viewport_bbox,
            )
            record["primitive_ids"] = sorted(record["primitive_ids"])
            records.append(record)
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
