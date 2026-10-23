"""Producer-owned source open passage and connected space shadow authority (Items 12 & 20).

Preserves genuine open passages and connected room connections:
- Identifies authentic structural wall terminations (jambs/pier ends) framing open passages.
- Verifies that no physical structural wall candidate exists across the passage.
- Handles finish continuity:
  * Physical doorway transition mark present: validates finish transition at the threshold line.
  * Shared finish code between adjoining spaces: validates continuous finish flow.
  * Differing finishes without a transition mark: fails closed (UNPARTITIONED_FINISH_CONFLICT).
- Explicitly guarantees that no partition wall was invented to artificially close a polygon.
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
SOURCE_OPEN_PASSAGE_RESOLVED = "source_open_passage_resolved"
SOURCE_OPEN_PASSAGE_CANDIDATE = "source_open_passage_candidate"
SOURCE_OPEN_PASSAGE_UNAVAILABLE = "source_open_passage_unavailable"
PASSAGE_ENDPOINTS_UNALIGNED_WITH_WALLS = "passage_endpoints_unaligned_with_walls"
OPEN_PASSAGE_OBSTRUCTED_BY_WALL = "open_passage_obstructed_by_wall"
UNPARTITIONED_FINISH_CONFLICT = "unpartitioned_finish_conflict"
FINISH_EVIDENCE_UNAVAILABLE = "finish_evidence_unavailable"
INVALID_PASSAGE_GEOMETRY = "invalid_passage_geometry"
SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"

TRANSITION_PHYSICAL_STROKE = "physical_transition_stroke"
TRANSITION_CONTIGUOUS_FLOW = "contiguous_finish_flow"

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
class SourceOpenPassageSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    primary_room_id: str
    connected_room_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "primary_room_id",
            "connected_room_id",
        ):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Selector field {name} must be non-empty string")
        sha = self.source_sha256.lower()
        if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("source_sha256 must be a 64-char lowercase hex string")
        if self.primary_room_id == self.connected_room_id:
            raise ValueError("primary_room_id and connected_room_id must be distinct")


@dataclass(frozen=True)
class SourcePassageWallEdge:
    wall_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    stroke_id: str = ""


@dataclass(frozen=True)
class SourceOpenPassageRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    primary_room_id: str
    connected_room_id: str
    passage_endpoints_pt: tuple[tuple[float, float], tuple[float, float]]
    clear_width_pt: float
    transition_type: str
    transition_stroke_geometry: tuple[tuple[float, float], tuple[float, float]] | None
    primary_finish_code: str | None
    connected_finish_code: str | None
    partition_invented: bool = False
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: tuple[str, ...] = (SOURCE_OPEN_PASSAGE_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    diagnostic_only: bool = True
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceOpenPassageRecord is producer-owned")


@dataclass(frozen=True)
class SourceOpenPassageResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceOpenPassageRecord | None = None
    selector: SourceOpenPassageSelector | None = None
    schema_version: str = SCHEMA_VERSION


def _point_matches_wall_endpoints(
    pt: tuple[float, float],
    edges: Sequence[SourcePassageWallEdge],
    tolerance_pt: float,
) -> bool:
    for edge in edges:
        for endp in (edge.start_pt, edge.end_pt):
            if _distance(pt, endp) <= tolerance_pt:
                return True
    return False


def _segment_intersects_passage(
    seg_start: tuple[float, float],
    seg_end: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    tolerance_pt: float,
) -> bool:
    """Check if a wall candidate segment obstructs, crosses, or runs along the passage line."""
    p_len = _distance(p1, p2)
    if p_len <= 1e-6:
        return False
    # Unit vector of passage
    ux = (p2[0] - p1[0]) / p_len
    uy = (p2[1] - p1[1]) / p_len

    def proj(p: tuple[float, float]) -> tuple[float, float]:
        along = (p[0] - p1[0]) * ux + (p[1] - p1[1]) * uy
        perp = abs((p[0] - p1[0]) * (-uy) + (p[1] - p1[1]) * ux)
        return along, perp

    a1, perp1 = proj(seg_start)
    a2, perp2 = proj(seg_end)

    # 1. Collinear overlap: wall runs along the passage opening
    if perp1 <= tolerance_pt and perp2 <= tolerance_pt:
        overlap = min(max(a1, a2), p_len) - max(min(a1, a2), 0.0)
        if overlap > tolerance_pt:
            return True
        return False

    # 2. Transverse intersection: wall crosses through the passage
    def ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    d1 = ccw(p1, p2, seg_start)
    d2 = ccw(p1, p2, seg_end)
    d3 = ccw(seg_start, seg_end, p1)
    d4 = ccw(seg_start, seg_end, p2)

    # Strict transversal crossing interior to both segments
    if ((d1 > 1e-5 and d2 < -1e-5) or (d1 < -1e-5 and d2 > 1e-5)) and \
       ((d3 > 1e-5 and d4 < -1e-5) or (d3 < -1e-5 and d4 > 1e-5)):
        return True

    # 3. Endpoint intrusion: wall terminates strictly inside the opening span
    for a, perp in ((a1, perp1), (a2, perp2)):
        if perp <= tolerance_pt and (tolerance_pt < a < (p_len - tolerance_pt)):
            return True

    return False


def evaluate_source_open_passage_connection_shadow(
    selector: SourceOpenPassageSelector,
    *,
    passage_endpoints: tuple[tuple[float, float], tuple[float, float]],
    primary_wall_edges: Sequence[SourcePassageWallEdge],
    connected_wall_edges: Sequence[SourcePassageWallEdge],
    transition_mark_geometry: tuple[tuple[float, float], tuple[float, float]]
    | None = None,
    primary_finish_code: str | None = None,
    connected_finish_code: str | None = None,
    existing_wall_candidates: Sequence[Any] = (),
    snap_tolerance_pt: float = DEFAULT_SNAP_TOLERANCE_PT,
) -> SourceOpenPassageResult:
    """Evaluate whether an open passage authentically connects two spaces."""
    if not isinstance(selector, SourceOpenPassageSelector):
        return SourceOpenPassageResult(
            EvidenceResolutionStatus.ABSTAINED,
            (SOURCE_LINEAGE_MISMATCH,),
            selector=selector,
        )

    if type(passage_endpoints) not in (tuple, list) or len(passage_endpoints) != 2:
        return SourceOpenPassageResult(
            EvidenceResolutionStatus.ABSTAINED,
            (INVALID_PASSAGE_GEOMETRY,),
            selector=selector,
        )

    p1 = _point(passage_endpoints[0])
    p2 = _point(passage_endpoints[1])
    if p1 is None or p2 is None:
        return SourceOpenPassageResult(
            EvidenceResolutionStatus.ABSTAINED,
            (INVALID_PASSAGE_GEOMETRY,),
            selector=selector,
        )

    width = _distance(p1, p2)
    if width <= snap_tolerance_pt or not math.isfinite(width):
        return SourceOpenPassageResult(
            EvidenceResolutionStatus.ABSTAINED,
            (INVALID_PASSAGE_GEOMETRY,),
            selector=selector,
        )

    # Verify both endpoints align with wall terminations from either room's boundary edges
    all_edges = list(primary_wall_edges) + list(connected_wall_edges)
    if not (
        _point_matches_wall_endpoints(p1, all_edges, snap_tolerance_pt)
        and _point_matches_wall_endpoints(p2, all_edges, snap_tolerance_pt)
    ):
        return SourceOpenPassageResult(
            EvidenceResolutionStatus.ABSTAINED,
            (PASSAGE_ENDPOINTS_UNALIGNED_WITH_WALLS,),
            selector=selector,
        )

    # Verify no structural wall candidate obstructs the passage opening
    for cand in existing_wall_candidates:
        c_pts = getattr(cand, "endpoints_pt", None) or getattr(cand, "geometry", None)
        if type(c_pts) in (tuple, list) and len(c_pts) == 2:
            cp1 = _point(c_pts[0])
            cp2 = _point(c_pts[1])
            if (
                cp1 is not None
                and cp2 is not None
                and _segment_intersects_passage(cp1, cp2, p1, p2, snap_tolerance_pt)
            ):
                return SourceOpenPassageResult(
                    EvidenceResolutionStatus.ABSTAINED,
                    (OPEN_PASSAGE_OBSTRUCTED_BY_WALL,),
                    selector=selector,
                )

    # Determine finish transition semantics
    trans_stroke = None
    if (
        transition_mark_geometry is not None
        and type(transition_mark_geometry) in (tuple, list)
        and len(transition_mark_geometry) == 2
    ):
        tp1 = _point(transition_mark_geometry[0])
        tp2 = _point(transition_mark_geometry[1])
        if tp1 is not None and tp2 is not None:
            # Must align with the passage span
            d1 = min(
                _distance(tp1, p1) + _distance(tp2, p2),
                _distance(tp1, p2) + _distance(tp2, p1),
            )
            if d1 <= 2.0 * snap_tolerance_pt:
                trans_stroke = (tp1, tp2)

    norm_primary = _clean(primary_finish_code).upper() if primary_finish_code else None
    norm_conn = _clean(connected_finish_code).upper() if connected_finish_code else None

    if trans_stroke is not None:
        transition_type = TRANSITION_PHYSICAL_STROKE
    elif not norm_primary or not norm_conn:
        return SourceOpenPassageResult(
            EvidenceResolutionStatus.ABSTAINED,
            (FINISH_EVIDENCE_UNAVAILABLE,),
            selector=selector,
        )
    elif norm_primary == norm_conn:
        transition_type = TRANSITION_CONTIGUOUS_FLOW
    else:
        # Differing finishes without an authenticated threshold line -> conflict
        return SourceOpenPassageResult(
            EvidenceResolutionStatus.CONFLICT,
            (UNPARTITIONED_FINISH_CONFLICT,),
            selector=selector,
        )

    sorted_endpoints = tuple(sorted((p1, p2)))

    record_payload = {
        "document_id": selector.document_id,
        "revision_id": selector.revision_id,
        "source_sha256": selector.source_sha256,
        "snapshot_id": selector.snapshot_id,
        "page_id": selector.page_id,
        "primary_room_id": selector.primary_room_id,
        "connected_room_id": selector.connected_room_id,
        "passage_endpoints": sorted_endpoints,
        "transition_type": transition_type,
    }
    record_id = stable_contract_id(
        "source_open_passage_record", record_payload, digest_chars=32
    )

    record = SourceOpenPassageRecord(
        record_id=record_id,
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        primary_room_id=selector.primary_room_id,
        connected_room_id=selector.connected_room_id,
        passage_endpoints_pt=sorted_endpoints,
        clear_width_pt=round(width, 4),
        transition_type=transition_type,
        transition_stroke_geometry=trans_stroke,
        primary_finish_code=norm_primary,
        connected_finish_code=norm_conn,
        partition_invented=False,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(SOURCE_OPEN_PASSAGE_CANDIDATE,),
        commercial_projection_allowed=False,
        takeoff_eligible=False,
        diagnostic_only=True,
        _seal=_RECORD_SEAL,
    )

    return SourceOpenPassageResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(SOURCE_OPEN_PASSAGE_RESOLVED,),
        record=record,
        selector=selector,
    )
