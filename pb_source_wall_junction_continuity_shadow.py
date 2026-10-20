"""Producer-owned source wall junction continuity and through-wall ownership shadow authority (Workstream A, Items 2 & 4).

Recovers physical wall junctions and establishes continuous wall ownership:
- Resolves T-junctions: through-wall maintains continuous wall ownership across the junction node,
  while the abutting stem wall terminates cleanly without splitting through-wall continuity.
- Resolves L-corners: two edges meeting at a corner bend establish corner wall continuity.
- Resolves Collinear continuations: through-wall continuation across degree-2 nodes.
- Resolves X-crossings: two independent through-wall runs crossing at a 4-way node.
- Fails closed on irregular or ambiguous multi-way meetings (JUNCTION_CONTINUITY_AMBIGUOUS).
- Rejects unaligned endpoints exceeding snap tolerance <= 2.5 pt (JUNCTION_ENDPOINT_UNALIGNED).
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
SOURCE_WALL_JUNCTION_CONTINUITY_RESOLVED = "source_wall_junction_continuity_resolved"
SOURCE_WALL_JUNCTION_CONTINUITY_CANDIDATE = "source_wall_junction_continuity_candidate"
CONTINUOUS_THROUGH_WALL_RESOLVED = "continuous_through_wall_resolved"
ABUTTING_STEM_WALL_TERMINATES = "abutting_stem_wall_terminates"
CORNER_WALL_BEND_RESOLVED = "corner_wall_bend_resolved"
COLLINEAR_THROUGH_CONTINUATION_RESOLVED = "collinear_through_continuation_resolved"
TWO_WAY_THROUGH_CROSSING_RESOLVED = "two_way_through_crossing_resolved"
JUNCTION_CONTINUITY_AMBIGUOUS = "junction_continuity_ambiguous"
JUNCTION_ENDPOINT_UNALIGNED = "junction_endpoint_unaligned"
SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"
EMPTY_INCIDENT_EDGES = "empty_incident_edges"

# Junction Types
JUNCTION_TYPE_T_JUNCTION = "t_junction"
JUNCTION_TYPE_L_CORNER = "l_corner"
JUNCTION_TYPE_COLLINEAR = "collinear_continuation"
JUNCTION_TYPE_X_CROSSING = "x_crossing"
JUNCTION_TYPE_AMBIGUOUS = "ambiguous_junction"

DEFAULT_SNAP_TOLERANCE_PT = 2.5
DEFAULT_COLLINEAR_ANGLE_TOL_DEG = 3.0

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
class SourceWallJunctionContinuitySelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    junction_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "junction_id",
        ):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Selector field {name} must be non-empty string")
        sha = self.source_sha256.lower()
        if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("source_sha256 must be a 64-char lowercase hex string")


@dataclass(frozen=True)
class SourceIncidentWallEdge:
    edge_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    parent_wall_id: str = ""
    stroke_width: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.edge_id, str) or not self.edge_id.strip():
            raise ValueError("edge_id must be non-empty string")
        p1 = _point(self.start_pt)
        p2 = _point(self.end_pt)
        if p1 is None or p2 is None:
            raise ValueError("start_pt and end_pt must be valid coordinates")
        if _distance(p1, p2) <= 1e-6:
            raise ValueError("Segment points must be distinct")


@dataclass(frozen=True)
class SourceWallJunctionContinuityRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    junction_id: str
    junction_pt: tuple[float, float]
    junction_type: str
    through_wall_edge_ids: tuple[str, ...]
    abutting_wall_edge_ids: tuple[str, ...]
    all_incident_edge_ids: tuple[str, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: tuple[str, ...] = (SOURCE_WALL_JUNCTION_CONTINUITY_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    diagnostic_only: bool = True
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceWallJunctionContinuityRecord is producer-owned")


@dataclass(frozen=True)
class SourceWallJunctionContinuityResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceWallJunctionContinuityRecord | None = None
    selector: SourceWallJunctionContinuitySelector | None = None
    schema_version: str = SCHEMA_VERSION


def _angular_difference_deg(a1: float, a2: float) -> float:
    diff = abs(a1 - a2) % 360.0
    return min(diff, 360.0 - diff)


def evaluate_source_wall_junction_continuity_shadow(
    selector: SourceWallJunctionContinuitySelector,
    *,
    junction_pt: tuple[float, float],
    incident_edges: Sequence[SourceIncidentWallEdge],
    snap_tolerance_pt: float = DEFAULT_SNAP_TOLERANCE_PT,
    collinear_angle_tolerance_deg: float = DEFAULT_COLLINEAR_ANGLE_TOL_DEG,
) -> SourceWallJunctionContinuityResult:
    """Evaluate continuous through-wall and abutting stem relationships at a wall junction."""
    if not isinstance(selector, SourceWallJunctionContinuitySelector):
        return SourceWallJunctionContinuityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
        )

    jpt = _point(junction_pt)
    if jpt is None:
        return SourceWallJunctionContinuityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
            selector=selector,
        )

    if not incident_edges:
        return SourceWallJunctionContinuityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(EMPTY_INCIDENT_EDGES,),
            selector=selector,
        )

    # Validate that every incident edge connects to the junction point
    edge_departures: list[tuple[SourceIncidentWallEdge, float]] = []
    for edge in incident_edges:
        d_start = _distance(edge.start_pt, jpt)
        d_end = _distance(edge.end_pt, jpt)
        if min(d_start, d_end) > snap_tolerance_pt:
            return SourceWallJunctionContinuityResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(JUNCTION_ENDPOINT_UNALIGNED,),
                selector=selector,
            )
        # Vector points away from junction
        if d_start <= d_end:
            near, far = edge.start_pt, edge.end_pt
        else:
            near, far = edge.end_pt, edge.start_pt

        dx = far[0] - near[0]
        dy = far[1] - near[1]
        angle = math.degrees(math.atan2(dy, dx)) % 360.0
        edge_departures.append((edge, angle))

    degree = len(edge_departures)
    all_edge_ids = tuple(sorted(e.edge_id for e, _ in edge_departures))

    # Identify collinear pairs (angle diff ~ 180 degrees)
    paired_indices: set[int] = set()
    pairs: list[tuple[SourceIncidentWallEdge, SourceIncidentWallEdge]] = []

    for i in range(degree):
        if i in paired_indices:
            continue
        e1, a1 = edge_departures[i]
        for j in range(i + 1, degree):
            if j in paired_indices:
                continue
            e2, a2 = edge_departures[j]
            diff = _angular_difference_deg(a1, a2)
            if abs(diff - 180.0) <= collinear_angle_tolerance_deg:
                paired_indices.add(i)
                paired_indices.add(j)
                pairs.append((e1, e2))
                break

    singles = [
        edge_departures[k][0]
        for k in range(degree)
        if k not in paired_indices
    ]

    n_pairs = len(pairs)
    n_singles = len(singles)

    # Classify junction continuity
    if degree == 2 and n_pairs == 1 and n_singles == 0:
        # Collinear through-continuation
        jtype = JUNCTION_TYPE_COLLINEAR
        through_edges = (pairs[0][0].edge_id, pairs[0][1].edge_id)
        abutting_edges: tuple[str, ...] = ()
        specific_reasons = (
            SOURCE_WALL_JUNCTION_CONTINUITY_RESOLVED,
            COLLINEAR_THROUGH_CONTINUATION_RESOLVED,
        )

    elif degree == 2 and n_pairs == 0 and n_singles == 2:
        # L-Corner
        jtype = JUNCTION_TYPE_L_CORNER
        through_edges = (singles[0].edge_id, singles[1].edge_id)
        abutting_edges = ()
        specific_reasons = (
            SOURCE_WALL_JUNCTION_CONTINUITY_RESOLVED,
            CORNER_WALL_BEND_RESOLVED,
        )

    elif degree == 3 and n_pairs == 1 and n_singles == 1:
        # T-Junction: exactly 1 continuous through-pair and 1 abutting stem!
        jtype = JUNCTION_TYPE_T_JUNCTION
        through_edges = tuple(sorted((pairs[0][0].edge_id, pairs[0][1].edge_id)))
        abutting_edges = (singles[0].edge_id,)
        specific_reasons = (
            SOURCE_WALL_JUNCTION_CONTINUITY_RESOLVED,
            CONTINUOUS_THROUGH_WALL_RESOLVED,
            ABUTTING_STEM_WALL_TERMINATES,
        )

    elif degree == 4 and n_pairs == 2 and n_singles == 0:
        # 2-way X-Crossing: 2 through pairs
        jtype = JUNCTION_TYPE_X_CROSSING
        through_edges = tuple(
            sorted(
                [pairs[0][0].edge_id, pairs[0][1].edge_id]
                + [pairs[1][0].edge_id, pairs[1][1].edge_id]
            )
        )
        abutting_edges = ()
        specific_reasons = (
            SOURCE_WALL_JUNCTION_CONTINUITY_RESOLVED,
            TWO_WAY_THROUGH_CROSSING_RESOLVED,
        )

    else:
        # Ambiguous / irregular meeting
        return SourceWallJunctionContinuityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(JUNCTION_CONTINUITY_AMBIGUOUS,),
            selector=selector,
        )

    record_id = stable_contract_id(
        "source_wall_junction_continuity",
        {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "junction_id": selector.junction_id,
            "junction_type": jtype,
            "through_edges": sorted(through_edges),
            "abutting_edges": sorted(abutting_edges),
        },
        digest_chars=32,
    )

    record = SourceWallJunctionContinuityRecord(
        record_id=record_id,
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        junction_id=selector.junction_id,
        junction_pt=jpt,
        junction_type=jtype,
        through_wall_edge_ids=tuple(sorted(through_edges)),
        abutting_wall_edge_ids=tuple(sorted(abutting_edges)),
        all_incident_edge_ids=all_edge_ids,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(*specific_reasons, SOURCE_WALL_JUNCTION_CONTINUITY_CANDIDATE),
        schema_version=SCHEMA_VERSION,
        commercial_projection_allowed=False,
        takeoff_eligible=False,
        diagnostic_only=True,
        _seal=_RECORD_SEAL,
    )

    return SourceWallJunctionContinuityResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(*specific_reasons, SOURCE_WALL_JUNCTION_CONTINUITY_CANDIDATE),
        record=record,
        selector=selector,
    )
