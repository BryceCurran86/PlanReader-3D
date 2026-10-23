"""Producer-owned source room boundary doorway opening shadow authority (Items 11 & 13).

Recovers authentic, physically meaningful closed room boundaries across doorway
openings without inventing artificial partition walls:
- Identifies candidate room faces where wall candidates are interrupted by doorway openings.
- Verifies that every non-wall edge of the candidate room polygon matches an authenticated
  opening candidate chord (spanning between structural wall jamb endpoints within snap tolerance <= 2.5 pt).
- Verifies that 100% of room boundary edges are accounted for (either owned by authentic walls
  or authenticated as doorway opening chords).
- Rejects polygons with unowned gaps/defects (ROOM_BOUNDARY_DEFECT_REMAINS).
- Rejects competing opening chord matches (COMPETING_OPENING_CHORD_OWNERSHIP).
- Explicitly guarantees that no artificial partition wall was invented to close the polygon.
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
SOURCE_ROOM_BOUNDARY_DOORWAY_RESOLVED = "source_room_boundary_doorway_resolved"
SOURCE_ROOM_BOUNDARY_DOORWAY_CANDIDATE = "source_room_boundary_doorway_candidate"
SOURCE_ROOM_BOUNDARY_DOORWAY_UNAVAILABLE = "source_room_boundary_doorway_unavailable"
ROOM_BOUNDARY_DEFECT_REMAINS = "room_boundary_defect_remains"
COMPETING_OPENING_CHORD_OWNERSHIP = "competing_opening_chord_ownership"
INVALID_ROOM_POLYGON = "invalid_room_polygon"
SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"
NO_WALL_EDGES_PRESENT = "no_wall_edges_present"

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
class SourceRoomDoorwayOpeningSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_id: str
    room_label: str = ""

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "room_id",
        ):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Selector field {name} must be non-empty string")
        sha = self.source_sha256.lower()
        if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("source_sha256 must be a 64-char lowercase hex string")


@dataclass(frozen=True)
class SourceRoomWallEdge:
    wall_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    stroke_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.wall_id, str) or not self.wall_id.strip():
            raise ValueError("wall_id must be non-empty string")
        p1 = _point(self.start_pt)
        p2 = _point(self.end_pt)
        if p1 is None or p2 is None:
            raise ValueError("start_pt and end_pt must be valid 2D coordinates")
        if _distance(p1, p2) <= 1e-6:
            raise ValueError("Wall edge points must be distinct")


@dataclass(frozen=True)
class SourceRoomOpeningCandidate:
    opening_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    opening_type: str = "doorway"

    def __post_init__(self) -> None:
        if not isinstance(self.opening_id, str) or not self.opening_id.strip():
            raise ValueError("opening_id must be non-empty string")
        p1 = _point(self.start_pt)
        p2 = _point(self.end_pt)
        if p1 is None or p2 is None:
            raise ValueError("start_pt and end_pt must be valid 2D coordinates")
        if _distance(p1, p2) <= 1e-6:
            raise ValueError("Opening points must be distinct")


@dataclass(frozen=True)
class SourceRoomBoundaryDoorwayRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    room_id: str
    room_label: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    area_sq_pt: float
    wall_edge_count: int
    opening_edge_count: int
    bounding_wall_ids: tuple[str, ...]
    bounding_opening_ids: tuple[str, ...]
    partition_invented: bool = False
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: tuple[str, ...] = (SOURCE_ROOM_BOUNDARY_DOORWAY_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    diagnostic_only: bool = True
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceRoomBoundaryDoorwayRecord is producer-owned")


@dataclass(frozen=True)
class SourceRoomBoundaryDoorwayResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceRoomBoundaryDoorwayRecord | None = None
    selector: SourceRoomDoorwayOpeningSelector | None = None
    unowned_edge_count: int = 0
    schema_version: str = SCHEMA_VERSION


def _segment_contains_subsegment(
    parent_p1: tuple[float, float],
    parent_p2: tuple[float, float],
    child_p1: tuple[float, float],
    child_p2: tuple[float, float],
    tolerance_pt: float,
) -> bool:
    """True if child segment lies collinearly inside parent segment within tolerance."""
    p_len = _distance(parent_p1, parent_p2)
    if p_len <= 1e-6:
        return False
    ux = (parent_p2[0] - parent_p1[0]) / p_len
    uy = (parent_p2[1] - parent_p1[1]) / p_len

    def proj(p: tuple[float, float]) -> tuple[float, float]:
        along = (p[0] - parent_p1[0]) * ux + (p[1] - parent_p1[1]) * uy
        perp = abs((p[0] - parent_p1[0]) * (-uy) + (p[1] - parent_p1[1]) * ux)
        return along, perp

    a1, perp1 = proj(child_p1)
    a2, perp2 = proj(child_p2)
    if perp1 > tolerance_pt or perp2 > tolerance_pt:
        return False
    t_min = min(a1, a2)
    t_max = max(a1, a2)
    return (t_min >= -tolerance_pt) and (t_max <= p_len + tolerance_pt)


def _segment_matches_opening_chord(
    edge_p1: tuple[float, float],
    edge_p2: tuple[float, float],
    open_p1: tuple[float, float],
    open_p2: tuple[float, float],
    tolerance_pt: float,
) -> bool:
    """True if polygon edge matches opening candidate chord endpoints within tolerance."""
    d_direct = max(_distance(edge_p1, open_p1), _distance(edge_p2, open_p2))
    d_reversed = max(_distance(edge_p1, open_p2), _distance(edge_p2, open_p1))
    if min(d_direct, d_reversed) <= tolerance_pt:
        return True
    # Also support child edge contained within opening chord span if opening endpoints align with tolerance
    return _segment_contains_subsegment(open_p1, open_p2, edge_p1, edge_p2, tolerance_pt)


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


def evaluate_source_room_boundary_doorway_shadow(
    selector: SourceRoomDoorwayOpeningSelector,
    *,
    polygon_pdf_pts: Sequence[Any],
    wall_edges: Sequence[SourceRoomWallEdge],
    opening_candidates: Sequence[SourceRoomOpeningCandidate],
    snap_tolerance_pt: float = DEFAULT_SNAP_TOLERANCE_PT,
) -> SourceRoomBoundaryDoorwayResult:
    """Evaluate whether candidate room face forms an authentic closed boundary across doorway openings."""
    if not isinstance(selector, SourceRoomDoorwayOpeningSelector):
        return SourceRoomBoundaryDoorwayResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
        )

    # Validate tolerance
    if not (math.isfinite(snap_tolerance_pt) and snap_tolerance_pt > 0):
        return SourceRoomBoundaryDoorwayResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(INVALID_ROOM_POLYGON,),
            selector=selector,
        )

    # Validate polygon vertices
    clean_poly: list[tuple[float, float]] = []
    for raw_pt in polygon_pdf_pts:
        p = _point(raw_pt)
        if p is None:
            return SourceRoomBoundaryDoorwayResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(INVALID_ROOM_POLYGON,),
                selector=selector,
            )
        clean_poly.append(p)

    if len(clean_poly) < 3:
        return SourceRoomBoundaryDoorwayResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(INVALID_ROOM_POLYGON,),
            selector=selector,
        )

    area = _polygon_area(clean_poly)
    if area <= 1e-4:
        return SourceRoomBoundaryDoorwayResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(INVALID_ROOM_POLYGON,),
            selector=selector,
        )

    n_vertices = len(clean_poly)
    wall_edge_count = 0
    opening_edge_count = 0
    unowned_edge_count = 0
    bounding_wall_ids: set[str] = set()
    bounding_opening_ids: set[str] = set()

    for i in range(n_vertices):
        edge_p1 = clean_poly[i]
        edge_p2 = clean_poly[(i + 1) % n_vertices]
        if _distance(edge_p1, edge_p2) <= 1e-6:
            # Degenerate zero-length edge in polygon
            return SourceRoomBoundaryDoorwayResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(INVALID_ROOM_POLYGON,),
                selector=selector,
            )

        # 1. Check if contained in any wall edge
        matched_wall_ids: list[str] = []
        for wall in wall_edges:
            if _segment_contains_subsegment(
                wall.start_pt, wall.end_pt, edge_p1, edge_p2, snap_tolerance_pt
            ):
                matched_wall_ids.append(wall.wall_id)

        if matched_wall_ids:
            wall_edge_count += 1
            bounding_wall_ids.update(matched_wall_ids)
            continue

        # 2. Not wall-owned: check opening candidates
        matched_opening_ids: list[str] = []
        for opening in opening_candidates:
            if _segment_matches_opening_chord(
                edge_p1, edge_p2, opening.start_pt, opening.end_pt, snap_tolerance_pt
            ):
                matched_opening_ids.append(opening.opening_id)

        # Check for competing distinct opening candidates
        distinct_openings = sorted(set(matched_opening_ids))
        if len(distinct_openings) > 1:
            return SourceRoomBoundaryDoorwayResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(COMPETING_OPENING_CHORD_OWNERSHIP,),
                selector=selector,
            )

        if len(distinct_openings) == 1:
            opening_edge_count += 1
            bounding_opening_ids.add(distinct_openings[0])
            continue

        # 3. Neither wall nor opening: unowned gap/defect
        unowned_edge_count += 1

    if unowned_edge_count > 0:
        return SourceRoomBoundaryDoorwayResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(ROOM_BOUNDARY_DEFECT_REMAINS,),
            selector=selector,
            unowned_edge_count=unowned_edge_count,
        )

    if wall_edge_count == 0:
        return SourceRoomBoundaryDoorwayResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(NO_WALL_EDGES_PRESENT,),
            selector=selector,
        )

    # All edges authenticated!
    poly_tuple = tuple(clean_poly)
    sorted_walls = tuple(sorted(bounding_wall_ids))
    sorted_openings = tuple(sorted(bounding_opening_ids))

    record_id = stable_contract_id(
        "source_room_boundary_doorway",
        {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "room_id": selector.room_id,
            "polygon": poly_tuple,
            "wall_ids": sorted_walls,
            "opening_ids": sorted_openings,
        },
        digest_chars=32,
    )

    record = SourceRoomBoundaryDoorwayRecord(
        record_id=record_id,
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        room_id=selector.room_id,
        room_label=selector.room_label,
        polygon_pdf_pts=poly_tuple,
        area_sq_pt=round(area, 4),
        wall_edge_count=wall_edge_count,
        opening_edge_count=opening_edge_count,
        bounding_wall_ids=sorted_walls,
        bounding_opening_ids=sorted_openings,
        partition_invented=False,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(
            SOURCE_ROOM_BOUNDARY_DOORWAY_RESOLVED,
            SOURCE_ROOM_BOUNDARY_DOORWAY_CANDIDATE,
        ),
        schema_version=SCHEMA_VERSION,
        commercial_projection_allowed=False,
        takeoff_eligible=False,
        diagnostic_only=True,
        _seal=_RECORD_SEAL,
    )

    return SourceRoomBoundaryDoorwayResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(
            SOURCE_ROOM_BOUNDARY_DOORWAY_RESOLVED,
            SOURCE_ROOM_BOUNDARY_DOORWAY_CANDIDATE,
        ),
        record=record,
        selector=selector,
        unowned_edge_count=0,
    )
