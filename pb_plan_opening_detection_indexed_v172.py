"""Equivalence-preserving broad-phase indexes for legacy plan opening geometry.

The legacy v171 detector remains the semantic oracle. These functions reproduce
its exact predicates and output order while replacing page-wide nested candidate
enumeration with conservative indexes. They do not alter opening identity,
closure, confidence, tolerances, or publication.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

import pb_plan_opening_detection_v171 as legacy

Segment = legacy.Segment
WallLine = legacy.WallLine
TextWord = legacy.TextWord
DoorCandidate = legacy.DoorCandidate
GapCandidate = legacy.GapCandidate


def _angle_delta_deg(a: float, b: float) -> float:
    delta = abs((float(a) - float(b)) % 180.0)
    return min(delta, 180.0 - delta)


def _angle_bucket(angle: float, width: float, count: int) -> int:
    return int(math.floor((float(angle) % 180.0) / width)) % count


def _angle_index(
    segments: Sequence[Segment],
    *,
    width: float,
) -> tuple[dict[int, list[int]], int]:
    count = max(1, int(math.ceil(180.0 / width)))
    buckets: dict[int, list[int]] = defaultdict(list)
    for index, segment in enumerate(segments):
        buckets[_angle_bucket(segment.angle_deg, width, count)].append(index)
    return buckets, count


def _near_angle_indexes(
    buckets: dict[int, list[int]],
    *,
    angle: float,
    width: float,
    count: int,
    tolerance: float,
) -> tuple[int, ...]:
    center = _angle_bucket(angle, width, count)
    radius = max(1, int(math.ceil(tolerance / width)))
    found: set[int] = set()
    for offset in range(-radius, radius + 1):
        found.update(buckets.get((center + offset) % count, ()))
    return tuple(sorted(found))


def _endpoint_wall_pair_candidates(
    wall_lines: Sequence[WallLine],
    *,
    max_endpoint_distance: float,
) -> tuple[tuple[int, int], ...]:
    """Conservative wall-pair superset for finite discontinuity gaps.

    Any accepted legacy gap has two projected terminal endpoints separated by at
    most MAX_GAP and perpendicular offset <= COLLINEAR_OFFSET, hence Euclidean
    endpoint distance <= hypot(MAX_GAP, COLLINEAR_OFFSET). A cell at least that
    large makes the same/neighbor-cell query a safe broad phase.
    """
    if len(wall_lines) < 2:
        return ()
    cell = max(float(max_endpoint_distance), 1e-9)
    endpoint_cells: dict[tuple[int, int], list[int]] = defaultdict(list)

    def cell_of(x: float, y: float) -> tuple[int, int]:
        return (math.floor(float(x) / cell), math.floor(float(y) / cell))

    for index, wall_line in enumerate(wall_lines):
        segment = wall_line.segment
        for x, y in ((segment.x1, segment.y1), (segment.x2, segment.y2)):
            endpoint_cells[cell_of(x, y)].append(index)

    pairs: set[tuple[int, int]] = set()
    for index, wall_line in enumerate(wall_lines):
        segment = wall_line.segment
        nearby: set[int] = set()
        for x, y in ((segment.x1, segment.y1), (segment.x2, segment.y2)):
            cx, cy = cell_of(x, y)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nearby.update(endpoint_cells.get((cx + dx, cy + dy), ()))
        for other in nearby:
            if other <= index:
                continue
            a = segment
            b = wall_lines[other].segment
            endpoint_distance = min(
                math.hypot(ax - bx, ay - by)
                for ax, ay in ((a.x1, a.y1), (a.x2, a.y2))
                for bx, by in ((b.x1, b.y1), (b.x2, b.y2))
            )
            if endpoint_distance <= max_endpoint_distance + 1e-9:
                pairs.add((index, other))
    return tuple(sorted(pairs))


def _midpoint_grid_candidates(
    segments: Sequence[Segment],
    candidate_indexes: Sequence[int],
    wall: Segment,
    *,
    radius: float,
) -> tuple[int, ...]:
    cell = max(float(radius), 1e-9)
    grid: dict[tuple[int, int], list[int]] = defaultdict(list)

    def cell_of(x: float, y: float) -> tuple[int, int]:
        return (math.floor(float(x) / cell), math.floor(float(y) / cell))

    for index in candidate_indexes:
        segment = segments[index]
        grid[cell_of(segment.cx, segment.cy)].append(index)

    min_x = min(wall.x1, wall.x2) - radius
    max_x = max(wall.x1, wall.x2) + radius
    min_y = min(wall.y1, wall.y2) - radius
    max_y = max(wall.y1, wall.y2) + radius
    x0, y0 = cell_of(min_x, min_y)
    x1, y1 = cell_of(max_x, max_y)
    found: set[int] = set()
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            found.update(grid.get((x, y), ()))
    return tuple(sorted(found))


def detect_door_candidates_indexed(
    segments: Sequence[Segment],
    wall_lines: Sequence[WallLine],
    words: Sequence[TextWord],
    scale_info=None,
    scale_px_per_m: float = 0.0,
    page_no: int = 0,
) -> list[DoorCandidate]:
    candidates: list[DoorCandidate] = []
    pt_per_m, m_per_pt = legacy._resolve_scale(scale_info, scale_px_per_m)
    min_leaf = legacy._physical_pt(0.3, pt_per_m, 25.0)
    max_leaf = legacy._physical_pt(1.5, pt_per_m, 150.0)
    proximity = legacy._physical_pt(0.6, pt_per_m, 30.0)
    tag_radius = legacy._physical_pt(0.6, pt_per_m, 120.0)

    candidate_leaf_indexes = tuple(
        index
        for index, segment in enumerate(segments)
        if min_leaf <= segment.length <= max_leaf
    )

    local_by_wall: list[tuple[int, ...]] = []
    wall_local_parallel: set[int] = set()
    for wall_line in wall_lines:
        wall = wall_line.segment
        spatial = _midpoint_grid_candidates(
            segments,
            candidate_leaf_indexes,
            wall,
            radius=proximity,
        )
        local = tuple(
            index
            for index in spatial
            if segments[index] is not wall
            and legacy._segments_perpendicular(wall, segments[index])
            and legacy._point_segment_distance(
                segments[index].cx, segments[index].cy, wall
            ) <= proximity
        )
        local_by_wall.append(local)
        for left_pos, left_index in enumerate(local):
            left = segments[left_index]
            for right_index in local[left_pos + 1 :]:
                right = segments[right_index]
                if (
                    legacy._segments_parallel(left, right)
                    and legacy._segment_distance(left, right)
                    <= legacy._physical_pt(2.0, pt_per_m, 100.0)
                ):
                    wall_local_parallel.add(id(left))
                    wall_local_parallel.add(id(right))

    for wall_pos, wall_line in enumerate(wall_lines):
        wall = wall_line.segment
        wall_dx, wall_dy, wall_ox, wall_oy = legacy._canonical_wall_direction(wall)
        wall_len = math.hypot(wall_dx, wall_dy)
        if wall_len < 1e-9:
            continue

        for index in local_by_wall[wall_pos]:
            segment = segments[index]
            if id(segment) in wall_local_parallel:
                continue

            tag, tag_cls = legacy._find_tag_near(
                segment.cx, segment.cy, words, max_dist_pt=tag_radius
            )
            assigned_tag = tag if tag and tag_cls == "door" else ""
            width_m = legacy._pt_to_m(segment.length, m_per_pt)
            pos_pt = (
                (segment.cx - wall_ox) * wall_dx
                + (segment.cy - wall_oy) * wall_dy
            ) / wall_len
            pos_m = legacy._pt_to_m(pos_pt, m_per_pt)

            geom_conf = 0.45
            if width_m is not None and 0.6 <= width_m <= 1.2:
                geom_conf = 0.60
            assoc_conf = 0.70 if wall_line.wall_ref else 0.30
            sem_conf = 0.0
            if tag and tag_cls == "door":
                sem_conf = 0.95
            elif tag and tag_cls == "window":
                sem_conf = 0.30
            elif tag:
                sem_conf = 0.60

            evidence = [
                f"jamb_leaf: {segment.length:.1f}pt perpendicular to wall"
            ]
            if assigned_tag:
                evidence.append(f"tag: {tag} (door-compatible)")
            elif tag:
                evidence.append(
                    f"tag: {tag} (conflicting — not assigned as type_mark)"
                )

            candidates.append(
                DoorCandidate(
                    wall_ref=wall_line.wall_ref or "",
                    wall_segment=wall,
                    position_along_wall_m=pos_m,
                    width_m=width_m,
                    jamb_segment=segment,
                    tag=assigned_tag,
                    geometry_confidence=geom_conf,
                    association_confidence=assoc_conf,
                    semantic_confidence=sem_conf,
                    evidence=evidence,
                    page_no=page_no,
                )
            )
    return candidates


def detect_gap_candidates_indexed(
    segments: Sequence[Segment],
    wall_lines: Sequence[WallLine],
    words: Sequence[TextWord],
    scale_info=None,
    scale_px_per_m: float = 0.0,
    page_no: int = 0,
) -> list[GapCandidate]:
    candidates: list[GapCandidate] = []
    pt_per_m, m_per_pt = legacy._resolve_scale(scale_info, scale_px_per_m)
    min_gap = legacy._physical_pt(0.5, pt_per_m, 30.0)
    max_gap = legacy._physical_pt(2.0, pt_per_m, 200.0)
    tag_radius = legacy._physical_pt(0.6, pt_per_m, 120.0)
    collinear_tol_deg = 10.0
    collinear_offset = 15.0
    endpoint_proximity = 5.0

    pair_radius = math.hypot(max_gap, collinear_offset)
    wall_pairs = _endpoint_wall_pair_candidates(
        wall_lines,
        max_endpoint_distance=pair_radius,
    )
    angle_buckets, angle_bucket_count = _angle_index(
        segments, width=collinear_tol_deg
    )

    for i, j in wall_pairs:
        wall_a = wall_lines[i]
        wall_b = wall_lines[j]
        a = wall_a.segment
        b = wall_b.segment
        if not legacy._segments_parallel(a, b, tol=collinear_tol_deg):
            continue
        perp_dist = legacy._line_perp_distance(b.cx, b.cy, a)
        if perp_dist > collinear_offset:
            continue
        gap_wall_ref = legacy._resolve_wall_ref(wall_a, wall_b)
        angle = a.angle_deg
        cos_a = math.cos(math.radians(angle))
        sin_a = math.sin(math.radians(angle))
        a_starts = [a.x1 * cos_a + a.y1 * sin_a, a.x2 * cos_a + a.y2 * sin_a]
        b_starts = [b.x1 * cos_a + b.y1 * sin_a, b.x2 * cos_a + b.y2 * sin_a]
        shared_min_t = min(a_starts + b_starts)
        shared_origin_x = shared_min_t * cos_a
        shared_origin_y = shared_min_t * sin_a
        wall_dx = cos_a
        wall_dy = sin_a
        wall_ox = shared_origin_x
        wall_oy = shared_origin_y
        wall_len = a.length + b.length

        def project(segment: Segment):
            t1 = (
                (segment.x1 - wall_ox) * wall_dx
                + (segment.y1 - wall_oy) * wall_dy
            ) / wall_len
            t2 = (
                (segment.x2 - wall_ox) * wall_dx
                + (segment.y2 - wall_oy) * wall_dy
            ) / wall_len
            return (t1 * wall_len, t2 * wall_len)

        a_proj = project(a)
        b_proj = project(b)
        a_min, a_max = min(a_proj), max(a_proj)
        b_min, b_max = min(b_proj), max(b_proj)
        if a_max < b_min:
            gap_start = a_max
            gap_end = b_min
        elif b_max < a_min:
            gap_start = b_max
            gap_end = a_min
        else:
            continue
        gap_len = gap_end - gap_start
        if gap_len < min_gap or gap_len > max_gap:
            continue

        gap_filled = False
        for segment_index in _near_angle_indexes(
            angle_buckets,
            angle=a.angle_deg,
            width=collinear_tol_deg,
            count=angle_bucket_count,
            tolerance=collinear_tol_deg,
        ):
            segment = segments[segment_index]
            if segment is a or segment is b:
                continue
            if legacy._segments_parallel(a, segment, tol=collinear_tol_deg):
                seg_proj = project(segment)
                seg_min, seg_max = min(seg_proj), max(seg_proj)
                if (
                    seg_min <= gap_start + endpoint_proximity
                    and seg_max >= gap_end - endpoint_proximity
                ):
                    gap_filled = True
                    break
        if gap_filled:
            continue

        if a_max < b_min:
            a_end = max(a_proj)
            b_end = min(b_proj)
        else:
            a_end = min(a_proj)
            b_end = max(b_proj)

        def interp(segment: Segment, target: float):
            t1 = (
                (segment.x1 - shared_origin_x) * cos_a
                + (segment.y1 - shared_origin_y) * sin_a
            )
            t2 = (
                (segment.x2 - shared_origin_x) * cos_a
                + (segment.y2 - shared_origin_y) * sin_a
            )
            if abs(t2 - t1) < 1e-9:
                return (segment.cx, segment.cy)
            fraction = (target - t1) / (t2 - t1)
            fraction = max(0.0, min(1.0, fraction))
            return (
                segment.x1 + fraction * (segment.x2 - segment.x1),
                segment.y1 + fraction * (segment.y2 - segment.y1),
            )

        end_a = interp(a, a_end)
        end_b = interp(b, b_end)
        mid_cx = (end_a[0] + end_b[0]) / 2.0
        mid_cy = (end_a[1] + end_b[1]) / 2.0
        width_m = legacy._pt_to_m(gap_len, m_per_pt)
        mid_pt = (gap_start + gap_end) / 2.0
        pos_m = legacy._pt_to_m(mid_pt, m_per_pt)
        tag, _tag_cls = legacy._find_tag_near(
            mid_cx, mid_cy, words, max_dist_pt=tag_radius
        )
        geom_conf = 0.75
        assoc_conf = 0.70 if gap_wall_ref else 0.30
        sem_conf = 0.80 if tag else 0.0
        evidence = [
            f"wall_discontinuity: {gap_len:.1f}pt gap between collinear wall segments"
        ]
        if tag:
            evidence.append(f"tag: {tag} (semantic evidence)")
        candidates.append(
            GapCandidate(
                wall_ref=gap_wall_ref,
                wall_segments=(a, b),
                position_along_wall_m=pos_m,
                width_m=width_m,
                tag=tag or "",
                geometry_confidence=geom_conf,
                association_confidence=assoc_conf,
                semantic_confidence=sem_conf,
                evidence=evidence,
                page_no=page_no,
                centroid_x=mid_cx,
                centroid_y=mid_cy,
            )
        )

    return candidates
