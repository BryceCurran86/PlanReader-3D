"""Shadow-only rejection of unsupported rectangular boundary detours.

Owner defect #4443: morphological / approximated exterior contours sometimes
insert two box-shaped excursions where one continuous source wall face exists.
Antenna-spike pruning alone cannot remove a wider rectangular U-detour.

This module collapses an axis-aligned rectangular detour only when the three
outer sides lack continuous source wall-ink coverage. Genuine alcoves whose
paired faces are painted in the original remain. Candidate/ABSTAIN only —
never FIRM, never customer area, never a second scale resolver.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

Point = Tuple[float, float]
Segment = Tuple[float, float, float, float]


@dataclass(frozen=True)
class RectangularDetourCollapseReceipt:
    original_vertex_count: int
    repaired_vertex_count: int
    collapsed_detour_count: int
    polygon_pdf_pts: Tuple[Point, ...]
    reason_codes: Tuple[str, ...]
    commercial_publishable: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> Mapping[str, object]:
        return {
            "original_vertex_count": self.original_vertex_count,
            "repaired_vertex_count": self.repaired_vertex_count,
            "collapsed_detour_count": self.collapsed_detour_count,
            "polygon_pdf_pts": [list(p) for p in self.polygon_pdf_pts],
            "reason_codes": list(self.reason_codes),
            "commercial_publishable": False,
            "measurement_authorized": False,
        }


def _dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _axis_aligned(a: Point, b: Point, tol: float) -> bool:
    return abs(a[0] - b[0]) <= tol or abs(a[1] - b[1]) <= tol


def _segment_covered_by_wall_ink(
    a: Point,
    b: Point,
    members: Sequence[Segment],
    *,
    alignment_tolerance_pt: float,
) -> bool:
    """True when original wall strokes continuously occupy the full segment face."""
    ax, ay = a
    bx, by = b
    vx, vy = bx - ax, by - ay
    length = math.hypot(vx, vy)
    if not math.isfinite(length) or length <= 0.0:
        return False
    ux, uy = vx / length, vy / length
    intervals: list[tuple[float, float]] = []
    for x1, y1, x2, y2 in members:
        offsets = (
            abs((x1 - ax) * uy - (y1 - ay) * ux),
            abs((x2 - ax) * uy - (y2 - ay) * ux),
        )
        if max(offsets) > alignment_tolerance_pt:
            continue
        p, q = sorted(
            (
                (x1 - ax) * ux + (y1 - ay) * uy,
                (x2 - ax) * ux + (y2 - ay) * uy,
            )
        )
        lo, hi = max(0.0, p), min(length, q)
        if hi > lo:
            intervals.append((lo, hi))
    if not intervals:
        return False
    intervals.sort()
    start, stop = intervals[0]
    for lo, hi in intervals[1:]:
        if lo > stop + alignment_tolerance_pt:
            if start <= alignment_tolerance_pt and stop >= length - alignment_tolerance_pt:
                return True
            start, stop = lo, hi
        else:
            stop = max(stop, hi)
    return start <= alignment_tolerance_pt and stop >= length - alignment_tolerance_pt


def _is_axis_aligned_u_detour(
    a: Point,
    b: Point,
    c: Point,
    d: Point,
    *,
    snap_pt: float,
    min_depth_pt: float,
    min_width_pt: float,
) -> bool:
    """Detect A-B-C-D as an axis-aligned rectangular U (out, across, back)."""
    if not (
        _axis_aligned(a, b, snap_pt)
        and _axis_aligned(b, c, snap_pt)
        and _axis_aligned(c, d, snap_pt)
    ):
        return False
    # Sides a-b and c-d must be parallel and opposite the across edge b-c.
    ab_vert = abs(a[0] - b[0]) <= snap_pt
    cd_vert = abs(c[0] - d[0]) <= snap_pt
    bc_horiz = abs(b[1] - c[1]) <= snap_pt
    if ab_vert and cd_vert and bc_horiz:
        # Vertical returns + horizontal far face; base a-d lies on one horizontal face.
        if abs(a[1] - d[1]) > snap_pt * 2:
            return False
        if abs(a[0] - b[0]) > snap_pt or abs(d[0] - c[0]) > snap_pt:
            return False
        depth = abs(((b[1] + c[1]) * 0.5) - ((a[1] + d[1]) * 0.5))
        width = abs(a[0] - d[0])
        return depth >= min_depth_pt and width >= min_width_pt
    ab_horiz = abs(a[1] - b[1]) <= snap_pt
    cd_horiz = abs(c[1] - d[1]) <= snap_pt
    bc_vert = abs(b[0] - c[0]) <= snap_pt
    if ab_horiz and cd_horiz and bc_vert:
        # Horizontal returns + vertical far face; base a-d lies on one vertical face.
        if abs(a[0] - d[0]) > snap_pt * 2:
            return False
        if abs(a[1] - b[1]) > snap_pt or abs(d[1] - c[1]) > snap_pt:
            return False
        depth = abs(((b[0] + c[0]) * 0.5) - ((a[0] + d[0]) * 0.5))
        width = abs(a[1] - d[1])
        return depth >= min_depth_pt and width >= min_width_pt
    return False


def _detour_supported_by_wall_ink(
    a: Point,
    b: Point,
    c: Point,
    d: Point,
    members: Sequence[Segment],
    *,
    alignment_tolerance_pt: float,
) -> bool:
    """Genuine alcove: at least the two side faces (or far face + one side) painted."""
    sides = (
        _segment_covered_by_wall_ink(a, b, members, alignment_tolerance_pt=alignment_tolerance_pt),
        _segment_covered_by_wall_ink(b, c, members, alignment_tolerance_pt=alignment_tolerance_pt),
        _segment_covered_by_wall_ink(c, d, members, alignment_tolerance_pt=alignment_tolerance_pt),
    )
    # Paired wall faces for a real recess: both returns, or far face with either return.
    return (sides[0] and sides[2]) or (sides[1] and (sides[0] or sides[2]))


def wall_ink_segments_from_drawings(
    drawings: Sequence[Mapping[str, object]],
) -> Tuple[Segment, ...]:
    """Extract axis-ish dark/wall-layer line endpoints for face-coverage proofs."""
    from pb_layered_wall_doorway_room_ring_shadow import (
        _source_wall_ink_candidate_drawings,
    )

    filtered, _count, _green = _source_wall_ink_candidate_drawings(drawings)
    out: list[Segment] = []
    for row in filtered:
        for item in row.get("items", ()) or ():
            if not item or item[0] != "l":
                continue
            p, q = item[1], item[2]
            try:
                x1, y1 = float(p.x), float(p.y)
                x2, y2 = float(q.x), float(q.y)
            except (AttributeError, TypeError, ValueError):
                continue
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                continue
            if math.hypot(x2 - x1, y2 - y1) < 1e-6:
                continue
            out.append((x1, y1, x2, y2))
    return tuple(out)


def _polygon_bbox(pts: Sequence[Point]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def collapse_unsupported_rectangular_detours(
    vertices: Sequence[Point],
    wall_segments: Sequence[Segment],
    *,
    snap_tolerance_pt: float = 2.5,
    alignment_tolerance_pt: float = 0.5,
    min_depth_pt: float = 8.0,
    min_width_pt: float = 8.0,
    max_depth_fraction: float = 0.28,
    max_width_fraction: float = 0.35,
) -> RectangularDetourCollapseReceipt:
    """Replace unsupported A-B-C-D rectangular boxes with the base chord A-D.

    Also collapses zero-width antenna spikes (A -> tip -> A') already within snap.
    Does not invent walls; does not authorize measurement.
    """
    pts = [(float(x), float(y)) for x, y in vertices]
    if len(pts) > 1 and _dist(pts[0], pts[-1]) <= snap_tolerance_pt:
        pts = pts[:-1]
    original = len(pts)
    if original < 4:
        return RectangularDetourCollapseReceipt(
            original_vertex_count=original,
            repaired_vertex_count=original,
            collapsed_detour_count=0,
            polygon_pdf_pts=tuple(pts),
            reason_codes=("contour_too_small_for_detour_audit",),
        )

    reasons: list[str] = []
    collapsed = 0
    changed = True
    minx, miny, maxx, maxy = _polygon_bbox(pts)
    bbox_w = max(maxx - minx, 1.0)
    bbox_h = max(maxy - miny, 1.0)
    # Iterate until stable: collapsing one box can expose another.
    while changed and len(pts) >= 4:
        changed = False
        n = len(pts)
        # Pass 1: antenna spikes (prev ≈ next).
        for i in range(n):
            prev_p = pts[(i - 1) % n]
            curr_p = pts[i]
            next_p = pts[(i + 1) % n]
            if _dist(prev_p, next_p) <= snap_tolerance_pt and _dist(prev_p, curr_p) > snap_tolerance_pt:
                pts.pop(i)
                collapsed += 1
                reasons.append("collapsed_antenna_spike_without_base_separation")
                changed = True
                break
        if changed:
            continue
        # Pass 2: rectangular U-detours lacking wall-ink support.
        n = len(pts)
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            c = pts[(i + 2) % n]
            d = pts[(i + 3) % n]
            if not _is_axis_aligned_u_detour(
                a, b, c, d,
                snap_pt=snap_tolerance_pt,
                min_depth_pt=min_depth_pt,
                min_width_pt=min_width_pt,
            ):
                continue
            # Local excursions only — never collapse a whole envelope face-triple.
            depth = max(
                abs(((b[0] + c[0]) * 0.5) - ((a[0] + d[0]) * 0.5)),
                abs(((b[1] + c[1]) * 0.5) - ((a[1] + d[1]) * 0.5)),
            )
            width = max(abs(a[0] - d[0]), abs(a[1] - d[1]))
            if depth > max_depth_fraction * max(bbox_w, bbox_h):
                continue
            if width > max_width_fraction * max(bbox_w, bbox_h):
                continue
            if _detour_supported_by_wall_ink(
                a, b, c, d, wall_segments,
                alignment_tolerance_pt=alignment_tolerance_pt,
            ):
                continue
            # Drop b and c; keep a and d as the continuous base face.
            # Delete higher index first when they wrap.
            idxs = sorted({(i + 1) % n, (i + 2) % n}, reverse=True)
            for idx in idxs:
                pts.pop(idx)
            collapsed += 1
            reasons.append("collapsed_unsupported_rectangular_detour")
            changed = True
            break

    if collapsed and "exterior_contour_candidate_only" not in reasons:
        reasons.append("exterior_contour_candidate_only")
    if not reasons:
        reasons.append("no_unsupported_rectangular_detour")
    return RectangularDetourCollapseReceipt(
        original_vertex_count=original,
        repaired_vertex_count=len(pts),
        collapsed_detour_count=collapsed,
        polygon_pdf_pts=tuple(
            (round(x, 3), round(y, 3)) for x, y in pts
        ),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )
