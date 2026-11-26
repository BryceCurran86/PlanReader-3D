"""Generic multi-wall room-face composition shadow for open-plan / non-single-path rooms.

Shadow-only, default-off source-evidence module. Composes a closed room-face
polygon from authentic structural wall segments plus explicitly witnessed
opening or finish-transition threshold chords. Never invents dividing walls,
never accepts unwitnessed chords, and never grants commercial authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Sequence

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

SHADOW_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class SourceWallSegmentInput:
    segment_id: str
    p1_pts: tuple[float, float]
    p2_pts: tuple[float, float]
    stroke_width_pt: float
    source_sha256: str
    page_id: str
    viewport_id: str


@dataclass(frozen=True)
class MarkedOpeningOrFinishThresholdInput:
    threshold_id: str
    kind: str  # "opening_span" | "finish_transition"
    p1_pts: tuple[float, float]
    p2_pts: tuple[float, float]
    witness_record_id: str
    source_sha256: str
    page_id: str
    viewport_id: str


@dataclass(frozen=True)
class MultiWallOpenRoomFaceResult:
    status: str
    resolved: bool
    source_sha256: str
    page_id: str
    viewport_id: str
    room_label: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    area_pts2: float | None
    area_m2_non_commercial: float | None
    contributing_wall_segment_ids: tuple[str, ...]
    contributing_threshold_ids: tuple[str, ...]
    wall_perimeter_fraction: float
    face_digest_sha256: str | None
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION


_ALLOWED_THRESHOLD_KINDS = frozenset({"opening_span", "finish_transition"})


def _seg_len(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(float(p2[0]) - float(p1[0]), float(p2[1]) - float(p1[1]))


def compose_multi_wall_open_room_face_shadow(
    *,
    wall_segments: Sequence[SourceWallSegmentInput],
    thresholds: Sequence[MarkedOpeningOrFinishThresholdInput],
    room_label: str,
    room_label_anchor_pts: tuple[float, float],
    source_sha256: str,
    page_id: str,
    viewport_id: str,
    mm_per_pt_x: float | None = None,
    mm_per_pt_y: float | None = None,
    min_wall_perimeter_fraction: float = 0.45,
    endpoint_snap_pt: float = 0.5,
) -> MultiWallOpenRoomFaceResult:
    """Compose a closed room face from authentic walls + witnessed threshold chords."""
    clean_label = str(room_label or "").strip()
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256.strip()) < 16
        or not str(page_id or "").strip()
        or not str(viewport_id or "").strip()
        or not clean_label
    ):
        return _abstain(
            source_sha256=str(source_sha256 or ""),
            page_id=str(page_id or ""),
            viewport_id=str(viewport_id or ""),
            room_label=clean_label,
            reasons=("source_provenance_incomplete",),
        )

    if not wall_segments:
        return _abstain(
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            room_label=clean_label,
            reasons=("wall_boundary_support_insufficient",),
        )

    # Validate lineage consistency across all walls & thresholds (fail closed on mixing)
    for w in wall_segments:
        if (
            w.source_sha256 != source_sha256
            or w.page_id != page_id
            or w.viewport_id != viewport_id
        ):
            return _abstain(
                source_sha256=source_sha256,
                page_id=page_id,
                viewport_id=viewport_id,
                room_label=clean_label,
                reasons=("lineage_mismatch_rejected",),
            )
    for t in thresholds:
        if (
            t.source_sha256 != source_sha256
            or t.page_id != page_id
            or t.viewport_id != viewport_id
        ):
            return _abstain(
                source_sha256=source_sha256,
                page_id=page_id,
                viewport_id=viewport_id,
                room_label=clean_label,
                reasons=("lineage_mismatch_rejected",),
            )
        if t.kind not in _ALLOWED_THRESHOLD_KINDS or not str(t.witness_record_id or "").strip():
            return _abstain(
                source_sha256=source_sha256,
                page_id=page_id,
                viewport_id=viewport_id,
                room_label=clean_label,
                reasons=("unwitnessed_threshold_chord_rejected",),
            )

    # Quantize endpoints gently only at sub-point CAD rounding (endpoint_snap_pt <= 1.0)
    snap = min(max(float(endpoint_snap_pt), 0.05), 1.0)

    def _q(pt: tuple[float, float]) -> tuple[float, float]:
        return (round(float(pt[0]) / snap) * snap, round(float(pt[1]) / snap) * snap)

    wall_lines: list[tuple[str, LineString]] = []
    for w in wall_segments:
        p1, p2 = _q(w.p1_pts), _q(w.p2_pts)
        if _seg_len(p1, p2) > 0.1:
            wall_lines.append((w.segment_id, LineString([p1, p2])))

    thresh_lines: list[tuple[str, LineString]] = []
    for t in thresholds:
        p1, p2 = _q(t.p1_pts), _q(t.p2_pts)
        if _seg_len(p1, p2) > 0.1:
            thresh_lines.append((t.threshold_id, LineString([p1, p2])))

    all_lines = [ls for _, ls in wall_lines] + [ls for _, ls in thresh_lines]
    if len(all_lines) < 3:
        return _abstain(
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            room_label=clean_label,
            reasons=("open_room_boundary_unclosed",),
        )

    noded = unary_union(all_lines)
    faces = [poly for poly in polygonize(noded) if isinstance(poly, Polygon) and poly.is_valid and poly.area > 1.0]
    anchor = Point(float(room_label_anchor_pts[0]), float(room_label_anchor_pts[1]))
    enclosing = [poly for poly in faces if poly.contains(anchor)]

    if not enclosing:
        return _abstain(
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            room_label=clean_label,
            reasons=("open_room_boundary_unclosed",),
        )

    # Choose strictly smallest enclosing face; abstain if two distinct faces tie within 1%
    enclosing.sort(key=lambda poly: poly.area)
    if len(enclosing) > 1 and abs(enclosing[1].area - enclosing[0].area) <= 0.01 * enclosing[0].area:
        return _abstain(
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            room_label=clean_label,
            reasons=("ambiguous_competing_room_faces",),
        )

    chosen = enclosing[0]
    boundary = chosen.exterior
    perim = float(boundary.length)
    if perim <= 0.0:
        return _abstain(
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            room_label=clean_label,
            reasons=("open_room_boundary_unclosed",),
        )

    # Compute exact contributing wall vs threshold lengths along the chosen face boundary
    contrib_walls: list[str] = []
    wall_shared_len = 0.0
    for wid, ls in wall_lines:
        inter = boundary.intersection(ls.buffer(snap * 0.5))
        if inter.length > 0.25:
            contrib_walls.append(wid)
            wall_shared_len += float(inter.length)

    contrib_thresh: list[str] = []
    for tid, ls in thresh_lines:
        inter = boundary.intersection(ls.buffer(snap * 0.5))
        if inter.length > 0.25:
            contrib_thresh.append(tid)

    wall_frac = min(1.0, wall_shared_len / perim)
    if wall_frac < min_wall_perimeter_fraction or not contrib_walls:
        return _abstain(
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            room_label=clean_label,
            reasons=("wall_boundary_support_insufficient",),
        )

    coords = tuple((round(float(x), 4), round(float(y), 4)) for x, y in boundary.coords[:-1])
    area_pts2 = round(float(chosen.area), 4)
    area_m2: float | None = None
    if (
        isinstance(mm_per_pt_x, (int, float))
        and isinstance(mm_per_pt_y, (int, float))
        and float(mm_per_pt_x) > 0.0
        and float(mm_per_pt_y) > 0.0
    ):
        area_m2 = round(area_pts2 * float(mm_per_pt_x) * float(mm_per_pt_y) / 1_000_000.0, 6)

    digest_payload = {
        "source_sha256": source_sha256,
        "page_id": page_id,
        "viewport_id": viewport_id,
        "room_label": clean_label,
        "coords": coords,
        "walls": sorted(set(contrib_walls)),
        "thresholds": sorted(set(contrib_thresh)),
    }
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True).encode("utf-8")).hexdigest()

    return MultiWallOpenRoomFaceResult(
        status="CANDIDATE_MULTI_WALL_ROOM_FACE_COMPOSED",
        resolved=True,
        source_sha256=source_sha256,
        page_id=page_id,
        viewport_id=viewport_id,
        room_label=clean_label,
        polygon_pdf_pts=coords,
        area_pts2=area_pts2,
        area_m2_non_commercial=area_m2,
        contributing_wall_segment_ids=tuple(sorted(set(contrib_walls))),
        contributing_threshold_ids=tuple(sorted(set(contrib_thresh))),
        wall_perimeter_fraction=round(wall_frac, 4),
        face_digest_sha256=digest,
        reason_codes=("multi_wall_open_room_face_composed_shadow",),
    )


def _abstain(
    *,
    source_sha256: str,
    page_id: str,
    viewport_id: str,
    room_label: str,
    reasons: tuple[str, ...],
) -> MultiWallOpenRoomFaceResult:
    return MultiWallOpenRoomFaceResult(
        status="ABSTAINED",
        resolved=False,
        source_sha256=source_sha256,
        page_id=page_id,
        viewport_id=viewport_id,
        room_label=room_label,
        polygon_pdf_pts=(),
        area_pts2=None,
        area_m2_non_commercial=None,
        contributing_wall_segment_ids=(),
        contributing_threshold_ids=(),
        wall_perimeter_fraction=0.0,
        face_digest_sha256=None,
        reason_codes=reasons,
    )
