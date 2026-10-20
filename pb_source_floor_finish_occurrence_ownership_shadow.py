"""Producer-owned source floor finish occurrence and physical floor ownership shadow authority (Item 14).

Resolves FT2 and FT3 drawing occurrences and exact physical floor ownership:
- Validates authentic native material marks inside candidate room boundaries.
- Enforces the construction rule: floor finishes terminate at internal wall faces, not beneath walls.
- Validates doorway threshold transitions: finish terminates at the physical doorway or entrance transition stroke.
- Rejects competing finish codes inside the same room boundary (COMPETING_FINISH_CODES_IN_ROOM).
- Rejects duplicate unzoned marks of the same code (COMPETING_FINISH_MARKS_IN_ROOM).
- Rejects marks outside the room polygon or too close to wall faces (boundary clearance < 2.5 pt).
- Strictly non-publishing in shadow mode (status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False).
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
SOURCE_FLOOR_FINISH_OWNERSHIP_RESOLVED = "source_floor_finish_ownership_resolved"
SOURCE_FLOOR_FINISH_OWNERSHIP_CANDIDATE = "source_floor_finish_ownership_candidate"
SOURCE_FLOOR_FINISH_OWNERSHIP_UNAVAILABLE = "source_floor_finish_ownership_unavailable"
FINISH_MATERIAL_CODE_MISMATCH = "finish_material_code_mismatch"
MARK_NOT_IN_ROOM_POLYGON = "mark_not_in_room_polygon"
MARK_TOO_CLOSE_TO_WALL_FACE = "mark_too_close_to_wall_face"
COMPETING_FINISH_CODES_IN_ROOM = "competing_finish_codes_in_room"
COMPETING_FINISH_MARKS_IN_ROOM = "competing_finish_marks_in_room"
INVALID_ROOM_POLYGON = "invalid_room_polygon"
SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"
DOORWAY_TRANSITION_MISALIGNED = "doorway_transition_misaligned"

DEFAULT_CLEARANCE_TOLERANCE_PT = 2.5
DEFAULT_SNAP_TOLERANCE_PT = 2.5

_RECORD_SEAL = object()


def _clean(val: Any) -> str:
    return str(val or "").strip()


def _point(val: Any) -> tuple[float, float] | None:
    if type(val) not in (tuple, list) or len(val) != 2:
        return None
    try:
        x, y = float(val[0]), float(val[1])
    except (TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return (x, y)


def _distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


@dataclass(frozen=True)
class SourceFloorFinishOwnershipSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_id: str
    material_code: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "room_id",
            "material_code",
        ):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Selector field {name} must be non-empty string")
        sha = self.source_sha256.lower()
        if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("source_sha256 must be a 64-char lowercase hex string")


@dataclass(frozen=True)
class SourceFloorFinishMark:
    occurrence_id: str
    page_id: str
    material_code: str
    mark_center_pt: tuple[float, float]
    source_word_address: tuple[int, int, int] = (0, 0, 0)

    def __post_init__(self) -> None:
        if not isinstance(self.occurrence_id, str) or not self.occurrence_id.strip():
            raise ValueError("occurrence_id must be non-empty string")
        if not isinstance(self.material_code, str) or not self.material_code.strip():
            raise ValueError("material_code must be non-empty string")
        p = _point(self.mark_center_pt)
        if p is None:
            raise ValueError("mark_center_pt must be a valid 2D coordinate")


@dataclass(frozen=True)
class SourceDoorwayThreshold:
    threshold_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]

    def __post_init__(self) -> None:
        if not isinstance(self.threshold_id, str) or not self.threshold_id.strip():
            raise ValueError("threshold_id must be non-empty string")
        p1 = _point(self.start_pt)
        p2 = _point(self.end_pt)
        if p1 is None or p2 is None:
            raise ValueError("start_pt and end_pt must be valid 2D coordinates")
        if _distance(p1, p2) <= 1e-6:
            raise ValueError("Threshold endpoints must be distinct")


@dataclass(frozen=True)
class SourceFloorFinishOwnershipRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_id: str
    material_code: str
    occurrence_id: str
    finish_boundary_polygon_pdf_pts: tuple[tuple[float, float], ...]
    internal_floor_area_sq_pt: float
    terminates_at_internal_faces: bool = True
    under_wall_finish_excluded: bool = True
    doorway_transition_authenticated: bool = False
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: tuple[str, ...] = (SOURCE_FLOOR_FINISH_OWNERSHIP_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    diagnostic_only: bool = True
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceFloorFinishOwnershipRecord is producer-owned")


@dataclass(frozen=True)
class SourceFloorFinishOwnershipResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceFloorFinishOwnershipRecord | None = None
    selector: SourceFloorFinishOwnershipSelector | None = None
    schema_version: str = SCHEMA_VERSION


def _point_in_polygon(pt: tuple[float, float], poly: Sequence[tuple[float, float]]) -> bool:
    """Standard ray-casting algorithm for point-in-polygon test."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
    return inside


def _point_to_segment_distance(
    pt: tuple[float, float],
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
) -> float:
    px, py = pt
    x1, y1 = seg_start
    x2, y2 = seg_end
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def _min_distance_to_boundary(
    pt: tuple[float, float],
    poly: Sequence[tuple[float, float]],
) -> float:
    n = len(poly)
    min_dist = float("inf")
    for i in range(n):
        d = _point_to_segment_distance(pt, poly[i], poly[(i + 1) % n])
        if d < min_dist:
            min_dist = d
    return min_dist


def _point_distance_to_segment(
    pt: tuple[float, float],
    s1: tuple[float, float],
    s2: tuple[float, float],
) -> float:
    """Distance from point to line segment s1-s2."""
    dx = s2[0] - s1[0]
    dy = s2[1] - s1[1]
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return _distance(pt, s1)
    t = max(0.0, min(1.0, ((pt[0] - s1[0]) * dx + (pt[1] - s1[1]) * dy) / seg_len_sq))
    proj_x = s1[0] + t * dx
    proj_y = s1[1] + t * dy
    return math.hypot(pt[0] - proj_x, pt[1] - proj_y)


def _point_distance_to_polygon_boundary(
    pt: tuple[float, float],
    poly: Sequence[tuple[float, float]],
) -> float:
    n = len(poly)
    if n < 2:
        return float("inf")
    return min(
        _point_distance_to_segment(pt, poly[i], poly[(i + 1) % n])
        for i in range(n)
    )


def _threshold_aligns_with_polygon_boundary(
    threshold: SourceDoorwayThreshold,
    poly: Sequence[tuple[float, float]],
    tolerance_pt: float,
) -> bool:
    """Check if doorway threshold endpoints lie on or near the room polygon boundary."""
    p1 = threshold.start_pt
    p2 = threshold.end_pt
    d1 = _point_distance_to_polygon_boundary(p1, poly)
    d2 = _point_distance_to_polygon_boundary(p2, poly)
    return d1 <= tolerance_pt and d2 <= tolerance_pt


def _polygon_area(poly: Sequence[tuple[float, float]]) -> float:
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def evaluate_source_floor_finish_ownership_shadow(
    selector: SourceFloorFinishOwnershipSelector,
    *,
    finish_mark: SourceFloorFinishMark,
    internal_face_polygon_pdf_pts: Sequence[Any],
    other_finish_marks: Sequence[SourceFloorFinishMark] = (),
    doorway_transitions: Sequence[SourceDoorwayThreshold] = (),
    clearance_tolerance_pt: float = DEFAULT_CLEARANCE_TOLERANCE_PT,
    snap_tolerance_pt: float = DEFAULT_SNAP_TOLERANCE_PT,
) -> SourceFloorFinishOwnershipResult:
    """Evaluate whether an authentic floor finish occurrence owns an exact physical floor space."""
    if not isinstance(selector, SourceFloorFinishOwnershipSelector):
        return SourceFloorFinishOwnershipResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
        )

    if not isinstance(finish_mark, SourceFloorFinishMark):
        return SourceFloorFinishOwnershipResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
            selector=selector,
        )

    # 1. Material code check
    if finish_mark.material_code.strip().upper() != selector.material_code.strip().upper():
        return SourceFloorFinishOwnershipResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(FINISH_MATERIAL_CODE_MISMATCH,),
            selector=selector,
        )

    # 2. Polygon verification
    clean_poly: list[tuple[float, float]] = []
    for raw_pt in internal_face_polygon_pdf_pts:
        p = _point(raw_pt)
        if p is None:
            return SourceFloorFinishOwnershipResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(INVALID_ROOM_POLYGON,),
                selector=selector,
            )
        clean_poly.append(p)

    if len(clean_poly) < 3:
        return SourceFloorFinishOwnershipResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(INVALID_ROOM_POLYGON,),
            selector=selector,
        )

    area = _polygon_area(clean_poly)
    if area <= 1e-4:
        return SourceFloorFinishOwnershipResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(INVALID_ROOM_POLYGON,),
            selector=selector,
        )

    # 3. Mark geometric enclosure
    mark_pt = finish_mark.mark_center_pt
    if not _point_in_polygon(mark_pt, clean_poly):
        return SourceFloorFinishOwnershipResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(MARK_NOT_IN_ROOM_POLYGON,),
            selector=selector,
        )

    dist_to_wall = _min_distance_to_boundary(mark_pt, clean_poly)
    if dist_to_wall < clearance_tolerance_pt:
        return SourceFloorFinishOwnershipResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(MARK_TOO_CLOSE_TO_WALL_FACE,),
            selector=selector,
        )

    # 4. Check competing finish marks inside the same polygon
    for other in other_finish_marks:
        if other.occurrence_id == finish_mark.occurrence_id:
            continue
        if _point_in_polygon(other.mark_center_pt, clean_poly):
            if other.material_code.strip().upper() != selector.material_code.strip().upper():
                # Different material code competing for the same room!
                return SourceFloorFinishOwnershipResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(COMPETING_FINISH_CODES_IN_ROOM,),
                    selector=selector,
                )
            else:
                # Duplicate mark of same code in same space without zoning
                return SourceFloorFinishOwnershipResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(COMPETING_FINISH_MARKS_IN_ROOM,),
                    selector=selector,
                )

    # 5. Check doorway threshold transitions: must align with polygon boundary
    doorway_authenticated = False
    for thresh in doorway_transitions:
        if _threshold_aligns_with_polygon_boundary(thresh, clean_poly, snap_tolerance_pt):
            doorway_authenticated = True
            break

    poly_tuple = tuple(clean_poly)
    record_id = stable_contract_id(
        "source_floor_finish_ownership",
        {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "room_id": selector.room_id,
            "material_code": selector.material_code.strip().upper(),
            "occurrence_id": finish_mark.occurrence_id,
            "polygon": poly_tuple,
        },
        digest_chars=32,
    )

    record = SourceFloorFinishOwnershipRecord(
        record_id=record_id,
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        room_id=selector.room_id,
        material_code=selector.material_code.strip().upper(),
        occurrence_id=finish_mark.occurrence_id,
        finish_boundary_polygon_pdf_pts=poly_tuple,
        internal_floor_area_sq_pt=round(area, 4),
        terminates_at_internal_faces=True,
        under_wall_finish_excluded=True,
        doorway_transition_authenticated=doorway_authenticated,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(
            SOURCE_FLOOR_FINISH_OWNERSHIP_RESOLVED,
            SOURCE_FLOOR_FINISH_OWNERSHIP_CANDIDATE,
        ),
        schema_version=SCHEMA_VERSION,
        commercial_projection_allowed=False,
        takeoff_eligible=False,
        diagnostic_only=True,
        _seal=_RECORD_SEAL,
    )

    return SourceFloorFinishOwnershipResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(
            SOURCE_FLOOR_FINISH_OWNERSHIP_RESOLVED,
            SOURCE_FLOOR_FINISH_OWNERSHIP_CANDIDATE,
        ),
        record=record,
        selector=selector,
    )
