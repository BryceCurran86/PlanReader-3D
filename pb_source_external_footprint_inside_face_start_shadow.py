"""Shadow #4549-01..05: inside-face footprint start + clockwise left-turn walk.

Owner queue (geometry/topology only):
- 01 start at authenticated inside face of the dominant dark outer wall,
  never a page/title frame
- 02 clockwise contour walker ranking valid left-turns; prove closure
- 03 normalize grayscale / stroke-weight ink bands across export styles
- 04 exclude porch/alfresco edges from the enclosed shell via labels
- 05 garage panel topology closure without promoting the opening to a wall

Does not mint FIRM areas, customer rows, or frozen-benchmark deltas.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_OUTDOOR = frozenset(
    {"ALFRESCO", "PORCH", "PATIO", "VERANDA", "VERANDAH", "DECK", "CARPORT"}
)
_GARAGE = frozenset({"GARAGE", "GARAGEDOOR", "PANELDOOR", "PANELLIFT"})


@dataclass(frozen=True)
class WallInkClassification:
    role: str
    gray: float
    stroke_weight_pt: float
    normalized_weight_band: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "role": self.role,
            "gray": self.gray,
            "stroke_weight_pt": self.stroke_weight_pt,
            "normalized_weight_band": self.normalized_weight_band,
            "reason": self.reason,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


def classify_wall_ink_band(
    *,
    gray: float,
    stroke_weight_pt: float,
    near_page_frame: bool = False,
) -> WallInkClassification:
    """Map scan/export ink into structural vs decoration vs frame bands.

    Grayscale and weight are source-observed properties only. Page-frame
    proximity never becomes a structural wall band.
    """
    if not math.isfinite(gray) or not (0.0 <= gray <= 1.0):
        return WallInkClassification(
            "ABSTAIN", gray if math.isfinite(gray) else -1.0,
            stroke_weight_pt if math.isfinite(stroke_weight_pt) else -1.0,
            "unknown", "ink_gray_out_of_range",
        )
    if not math.isfinite(stroke_weight_pt) or stroke_weight_pt <= 0:
        return WallInkClassification(
            "ABSTAIN", gray, stroke_weight_pt, "unknown", "ink_weight_nonpositive",
        )
    if near_page_frame:
        return WallInkClassification(
            "page_frame", gray, stroke_weight_pt, "frame",
            "page_or_title_frame_refused",
        )
    if gray > 0.55:
        return WallInkClassification(
            "decoration", gray, stroke_weight_pt, "pale",
            "pale_fill_not_structural_wall",
        )
    if stroke_weight_pt < 0.35:
        return WallInkClassification(
            "decoration", gray, stroke_weight_pt, "hairline",
            "hairline_not_structural_wall",
        )
    if stroke_weight_pt < 1.2:
        band = "medium"
    elif stroke_weight_pt < 4.0:
        band = "heavy"
    else:
        band = "fill_bar"
    if gray <= 0.18:
        return WallInkClassification(
            "structural_wall", gray, stroke_weight_pt, band,
            "dark_structural_wall_ink",
        )
    return WallInkClassification(
        "structural_wall_candidate", gray, stroke_weight_pt, band,
        "mid_gray_needs_corroboration",
    )


@dataclass(frozen=True)
class ExteriorWallSegment:
    wall_id: int
    start_pdf_pts: tuple[float, float]
    end_pdf_pts: tuple[float, float]
    gray: float = 0.0
    stroke_weight_pt: float = 2.0
    label: str = ""


@dataclass(frozen=True)
class InsideFaceFootprintStart:
    status: str
    reason: str
    start_pdf_pts: tuple[float, float] | None = None
    start_wall_id: int | None = None
    inside_normal_pdf_pts: tuple[float, float] | None = None
    dominant_wall_length_pt: float = 0.0
    ink: WallInkClassification | None = None
    topology_only: bool = True
    measurement_authorized: bool = False
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "start_pdf_pts": list(self.start_pdf_pts) if self.start_pdf_pts else None,
            "start_wall_id": self.start_wall_id,
            "inside_normal_pdf_pts": (
                list(self.inside_normal_pdf_pts) if self.inside_normal_pdf_pts else None
            ),
            "dominant_wall_length_pt": self.dominant_wall_length_pt,
            "ink": None if self.ink is None else self.ink.to_dict(),
            "topology_only": True,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


def _seg_len(seg: ExteriorWallSegment) -> float:
    return math.hypot(
        seg.end_pdf_pts[0] - seg.start_pdf_pts[0],
        seg.end_pdf_pts[1] - seg.start_pdf_pts[1],
    )


def _mid(seg: ExteriorWallSegment) -> tuple[float, float]:
    return (
        (seg.start_pdf_pts[0] + seg.end_pdf_pts[0]) / 2.0,
        (seg.start_pdf_pts[1] + seg.end_pdf_pts[1]) / 2.0,
    )


def _unit(dx: float, dy: float) -> tuple[float, float] | None:
    hyp = math.hypot(dx, dy)
    if hyp <= 1e-9:
        return None
    return dx / hyp, dy / hyp


def _near_page_frame(
    seg: ExteriorWallSegment,
    page_bounds_pdf_pts: tuple[float, float, float, float],
    *,
    margin_pt: float = 8.0,
) -> bool:
    x0, y0, x1, y1 = page_bounds_pdf_pts
    xs = (seg.start_pdf_pts[0], seg.end_pdf_pts[0])
    ys = (seg.start_pdf_pts[1], seg.end_pdf_pts[1])
    return (
        min(xs) <= x0 + margin_pt
        or max(xs) >= x1 - margin_pt
        or min(ys) <= y0 + margin_pt
        or max(ys) >= y1 - margin_pt
    )


def _building_centroid(
    segments: Sequence[ExteriorWallSegment],
) -> tuple[float, float] | None:
    pts = [p for s in segments for p in (s.start_pdf_pts, s.end_pdf_pts)]
    if not pts:
        return None
    return (
        sum(p[0] for p in pts) / len(pts),
        sum(p[1] for p in pts) / len(pts),
    )


def resolve_external_footprint_inside_face_start(
    segments: Sequence[ExteriorWallSegment],
    *,
    page_bounds_pdf_pts: tuple[float, float, float, float],
    building_centroid_pdf_pts: tuple[float, float] | None = None,
) -> InsideFaceFootprintStart:
    """Pick dominant dark outer wall and seed the walk on its INSIDE face."""
    if not segments:
        return InsideFaceFootprintStart(
            "ABSTAINED", "no_exterior_wall_segments",
        )
    centroid = building_centroid_pdf_pts or _building_centroid(segments)
    if centroid is None:
        return InsideFaceFootprintStart(
            "ABSTAINED", "building_centroid_unavailable",
        )

    ranked: list[tuple[float, ExteriorWallSegment, WallInkClassification]] = []
    for seg in segments:
        near_frame = _near_page_frame(seg, page_bounds_pdf_pts)
        ink = classify_wall_ink_band(
            gray=seg.gray,
            stroke_weight_pt=seg.stroke_weight_pt,
            near_page_frame=near_frame,
        )
        if ink.role != "structural_wall":
            continue
        length = _seg_len(seg)
        if length < 8.0:
            continue
        ranked.append((length, seg, ink))
    if not ranked:
        return InsideFaceFootprintStart(
            "ABSTAINED", "no_dominant_dark_outer_wall_inside_page",
        )

    # Unique longest structural wall; equal-length rivals abstain.
    best_len = max(item[0] for item in ranked)
    tops = [item for item in ranked if abs(item[0] - best_len) <= 1e-6]
    if len(tops) != 1:
        return InsideFaceFootprintStart(
            "ABSTAINED", "ambiguous_dominant_outer_wall_lengths",
            dominant_wall_length_pt=best_len,
        )
    _length, seg, ink = tops[0]
    tangent = _unit(
        seg.end_pdf_pts[0] - seg.start_pdf_pts[0],
        seg.end_pdf_pts[1] - seg.start_pdf_pts[1],
    )
    if tangent is None:
        return InsideFaceFootprintStart(
            "ABSTAINED", "dominant_wall_zero_length",
            start_wall_id=seg.wall_id, ink=ink,
        )
    # PDF y grows downward. Left normal of travel (tx,ty) is (ty, -tx).
    # Choose the normal that points toward the building centroid = inside face.
    n_left = (tangent[1], -tangent[0])
    n_right = (-tangent[1], tangent[0])
    mid = _mid(seg)
    to_c = (centroid[0] - mid[0], centroid[1] - mid[1])
    inside = n_left if (n_left[0] * to_c[0] + n_left[1] * to_c[1]) >= (
        n_right[0] * to_c[0] + n_right[1] * to_c[1]
    ) else n_right
    # Seed slightly inward from the painted face so the walk never starts on
    # the page frame or outside stroke midline.
    start = (mid[0] + inside[0] * 0.75, mid[1] + inside[1] * 0.75)
    return InsideFaceFootprintStart(
        status="CANDIDATE",
        reason="inside_face_of_dominant_dark_outer_wall",
        start_pdf_pts=(round(start[0], 4), round(start[1], 4)),
        start_wall_id=seg.wall_id,
        inside_normal_pdf_pts=(round(inside[0], 6), round(inside[1], 6)),
        dominant_wall_length_pt=round(best_len, 4),
        ink=ink,
    )


@dataclass(frozen=True)
class LeftTurnCandidate:
    edge_id: int
    to_pdf_pts: tuple[float, float]
    turn_degrees: float
    rank: int


@dataclass(frozen=True)
class ClockwiseContourWalkReceipt:
    status: str
    reason: str
    vertices_pdf_pts: tuple[tuple[float, float], ...] = ()
    left_turn_ranks: tuple[tuple[int, ...], ...] = ()
    closed_to_start: bool = False
    steps: int = 0
    porch_edges_excluded: int = 0
    garage_topology_bridges: int = 0
    topology_only: bool = True
    measurement_authorized: bool = False
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "vertices_pdf_pts": [list(v) for v in self.vertices_pdf_pts],
            "left_turn_ranks": [list(r) for r in self.left_turn_ranks],
            "closed_to_start": self.closed_to_start,
            "steps": self.steps,
            "porch_edges_excluded": self.porch_edges_excluded,
            "garage_topology_bridges": self.garage_topology_bridges,
            "topology_only": True,
            "doorway_closure_is_not_physical_wall": True,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _turn_degrees(
    incoming: tuple[float, float],
    outgoing: tuple[float, float],
) -> float | None:
    ia = _unit(*incoming)
    oa = _unit(*outgoing)
    if ia is None or oa is None:
        return None
    # PDF y-down: positive cross of (in→out) is a clockwise (page-left) turn.
    cross = _cross(ia[0], ia[1], oa[0], oa[1])
    dot = max(-1.0, min(1.0, ia[0] * oa[0] + ia[1] * oa[1]))
    deg = math.degrees(math.acos(dot))
    if cross < 0:
        deg = -deg
    return deg


def _label_token(text: str) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


def walk_clockwise_left_turn_contour(
    segments: Sequence[ExteriorWallSegment],
    *,
    start: InsideFaceFootprintStart,
    closure_tolerance_pt: float = 1.5,
    max_steps: int = 64,
    garage_bridge_segments: Sequence[ExteriorWallSegment] = (),
) -> ClockwiseContourWalkReceipt:
    """Rank valid left-turn successors and prove return to the start seed."""
    if start.status != "CANDIDATE" or start.start_pdf_pts is None:
        return ClockwiseContourWalkReceipt(
            "ABSTAINED", "inside_face_start_required",
        )
    usable: list[ExteriorWallSegment] = []
    porch_excluded = 0
    for seg in segments:
        token = _label_token(seg.label)
        if token in _OUTDOOR or any(token.startswith(o) for o in _OUTDOOR):
            porch_excluded += 1
            continue
        usable.append(seg)
    bridges = tuple(garage_bridge_segments)
    usable.extend(bridges)

    # Build undirected adjacency by tip proximity.
    tips: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
    for seg in usable:
        tips.append((seg.wall_id, seg.start_pdf_pts, seg.end_pdf_pts))

    def nearest_tip(
        point: tuple[float, float],
        *,
        forbid_ids: set[int],
    ) -> list[tuple[float, int, tuple[float, float], tuple[float, float]]]:
        hits: list[tuple[float, int, tuple[float, float], tuple[float, float]]] = []
        for wid, a, b in tips:
            if wid in forbid_ids:
                continue
            da = math.hypot(a[0] - point[0], a[1] - point[1])
            db = math.hypot(b[0] - point[0], b[1] - point[1])
            if da <= closure_tolerance_pt * 2:
                hits.append((da, wid, a, b))
            if db <= closure_tolerance_pt * 2:
                hits.append((db, wid, b, a))
        hits.sort(key=lambda row: (row[0], row[1]))
        return hits

    seed = start.start_pdf_pts
    start_seg = next((s for s in usable if s.wall_id == start.start_wall_id), None)
    if start_seg is None:
        return ClockwiseContourWalkReceipt(
            "ABSTAINED", "start_wall_missing_from_usable_edges",
            porch_edges_excluded=porch_excluded,
            garage_topology_bridges=len(bridges),
        )
    # Orient travel on the dominant wall so the page-left normal faces the
    # building (inside). Begin at that tip, not at the mid-face seed — the
    # seed remains the closure target proving return to the inside face.
    centroid = _building_centroid(usable) or seed
    mid = _mid(start_seg)
    oriented = None
    for at0, other0 in (
        (start_seg.start_pdf_pts, start_seg.end_pdf_pts),
        (start_seg.end_pdf_pts, start_seg.start_pdf_pts),
    ):
        tangent = _unit(other0[0] - at0[0], other0[1] - at0[1])
        if tangent is None:
            continue
        n_left = (tangent[1], -tangent[0])
        to_c = (centroid[0] - mid[0], centroid[1] - mid[1])
        if n_left[0] * to_c[0] + n_left[1] * to_c[1] >= 0:
            oriented = (at0, other0)
            break
    if oriented is None:
        return ClockwiseContourWalkReceipt(
            "ABSTAINED", "start_wall_inside_orientation_unresolved",
            porch_edges_excluded=porch_excluded,
            garage_topology_bridges=len(bridges),
        )
    at0, other0 = oriented
    wid0 = start_seg.wall_id
    vertices = [at0, other0]
    ranks_acc: list[tuple[int, ...]] = []
    used = {wid0}
    cursor = other0
    prev = at0
    origin = at0
    for _step in range(max_steps):
        # Closure: return to the oriented start tip after leaving the first edge.
        # Also accept nearness to the inside-face seed (projects onto that edge).
        if len(vertices) > 3 and (
            math.hypot(cursor[0] - origin[0], cursor[1] - origin[1])
            <= closure_tolerance_pt
            or math.hypot(cursor[0] - seed[0], cursor[1] - seed[1])
            <= closure_tolerance_pt * 4
        ):
            vertices.append(origin)
            return ClockwiseContourWalkReceipt(
                status="CANDIDATE",
                reason="clockwise_left_turn_closed_to_inside_face_start",
                vertices_pdf_pts=tuple(
                    (round(x, 4), round(y, 4)) for x, y in vertices
                ),
                left_turn_ranks=tuple(ranks_acc),
                closed_to_start=True,
                steps=len(vertices) - 1,
                porch_edges_excluded=porch_excluded,
                garage_topology_bridges=len(bridges),
            )
        incoming = (cursor[0] - prev[0], cursor[1] - prev[1])
        options = nearest_tip(cursor, forbid_ids=used)
        scored: list[tuple[float, int, tuple[float, float]]] = []
        for _dist, wid, at, other in options:
            if math.hypot(at[0] - cursor[0], at[1] - cursor[1]) > closure_tolerance_pt:
                continue
            outgoing = (other[0] - at[0], other[1] - at[1])
            turn = _turn_degrees(incoming, outgoing)
            # PDF y grows downward: page-left / clockwise progress has a
            # non-positive cross product (negative turn degrees here).
            if turn is None or turn > 5.0:
                continue
            scored.append((turn, wid, other))
        if not scored:
            return ClockwiseContourWalkReceipt(
                "ABSTAINED", "no_valid_left_turn_candidate",
                vertices_pdf_pts=tuple(
                    (round(x, 4), round(y, 4)) for x, y in vertices
                ),
                left_turn_ranks=tuple(ranks_acc),
                closed_to_start=False,
                steps=len(vertices) - 1,
                porch_edges_excluded=porch_excluded,
                garage_topology_bridges=len(bridges),
            )
        # Most negative page-left turn first (sharpest valid clockwise corner).
        scored.sort(key=lambda row: (row[0], row[1]))
        ranks_acc.append(tuple(wid for _t, wid, _p in scored))
        _turn, wid, nxt = scored[0]
        used.add(wid)
        prev = cursor
        cursor = nxt
        vertices.append(cursor)

    return ClockwiseContourWalkReceipt(
        "ABSTAINED", "contour_exceeded_max_steps_without_closure",
        vertices_pdf_pts=tuple((round(x, 4), round(y, 4)) for x, y in vertices),
        left_turn_ranks=tuple(ranks_acc),
        closed_to_start=False,
        steps=len(vertices) - 1,
        porch_edges_excluded=porch_excluded,
        garage_topology_bridges=len(bridges),
    )


@dataclass(frozen=True)
class FootprintInsideFaceBundle:
    """Composer receipt for #4549-01..05 shadow vertical slice."""

    start: InsideFaceFootprintStart
    walk: ClockwiseContourWalkReceipt
    ink_samples: tuple[WallInkClassification, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "start": self.start.to_dict(),
            "walk": self.walk.to_dict(),
            "ink_samples": [s.to_dict() for s in self.ink_samples],
            "tasks_covered": ["01", "02", "03", "04", "05"],
            "measurement_authorized": False,
            "commercial_publishable": False,
            "official_frozen120_score_change": 0,
        }


def build_external_footprint_inside_face_bundle(
    segments: Sequence[ExteriorWallSegment],
    *,
    page_bounds_pdf_pts: tuple[float, float, float, float],
    garage_bridge_segments: Sequence[ExteriorWallSegment] = (),
) -> FootprintInsideFaceBundle:
    ink_samples = tuple(
        classify_wall_ink_band(
            gray=s.gray,
            stroke_weight_pt=s.stroke_weight_pt,
            near_page_frame=_near_page_frame(s, page_bounds_pdf_pts),
        )
        for s in segments
    )
    start = resolve_external_footprint_inside_face_start(
        segments, page_bounds_pdf_pts=page_bounds_pdf_pts,
    )
    walk = walk_clockwise_left_turn_contour(
        segments,
        start=start,
        garage_bridge_segments=garage_bridge_segments,
    )
    return FootprintInsideFaceBundle(start=start, walk=walk, ink_samples=ink_samples)
