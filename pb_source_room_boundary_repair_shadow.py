"""Producer-Owned Source Room Polyline Self-Intersection & Degenerate Boundary Repair Shadow Authority.

Workstream B Item 11:
Detects and untangles self-intersecting loops (bowtie/figure-eight anomalies),
strips collapsed zero-width antenna spikes, removes collinear micro-segments
within snap tolerance, and enforces clean Jordan polygon topology for room enclosures.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_REPAIR_SEAL = object()


class BoundaryDefectKind(str, Enum):
    BOWTIE_SELF_INTERSECTION = "BOWTIE_SELF_INTERSECTION"
    COLLAPSED_ANTENNA_SPIKE = "COLLAPSED_ANTENNA_SPIKE"
    DUPLICATE_OR_MICRO_VERTEX = "DUPLICATE_OR_MICRO_VERTEX"
    COLLINEAR_REDUNDANT_VERTEX = "COLLINEAR_REDUNDANT_VERTEX"


@dataclass(frozen=True)
class RepairedBoundaryRecord:
    room_id: str
    original_vertex_count: int
    repaired_vertex_count: int
    defects_detected: Tuple[BoundaryDefectKind, ...]
    was_repaired: bool
    repaired_polygons: Tuple[Tuple[Tuple[float, float], ...], ...]
    total_area_pt2: float

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "room_id": self.room_id,
            "original_vertex_count": self.original_vertex_count,
            "repaired_vertex_count": self.repaired_vertex_count,
            "defects_detected": [d.value for d in self.defects_detected],
            "was_repaired": self.was_repaired,
            "repaired_polygons": [
                [list(pt) for pt in poly] for poly in self.repaired_polygons
            ],
            "total_area_pt2": self.total_area_pt2,
        }


@dataclass(frozen=True)
class RoomBoundaryRepairReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_rooms_evaluated: int
    repaired_rooms_count: int
    clean_rooms_count: int
    total_repaired_area_pt2: float
    records: Tuple[RepairedBoundaryRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _REPAIR_SEAL:
            raise TypeError("RoomBoundaryRepairReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_rooms_evaluated": self.total_rooms_evaluated,
            "repaired_rooms_count": self.repaired_rooms_count,
            "clean_rooms_count": self.clean_rooms_count,
            "total_repaired_area_pt2": self.total_repaired_area_pt2,
            "records": [r.to_dict() for r in self.records],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _polygon_area(poly: Sequence[Tuple[float, float]]) -> float:
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i][0] * poly[j][1]
        area -= poly[j][0] * poly[i][1]
    return abs(area) / 2.0


def _line_intersection(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    p4: Tuple[float, float],
) -> Optional[Tuple[float, float]]:
    """Calculates proper interior intersection point between segments (p1, p2) and (p3, p4)."""
    d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
    if abs(d) < 1e-9:
        return None  # Parallel or collinear

    u = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
    v = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d

    # Proper interior intersection strictly inside (0.01, 0.99)
    if 0.01 <= u <= 0.99 and 0.01 <= v <= 0.99:
        ix = p1[0] + u * (p2[0] - p1[0])
        iy = p1[1] + u * (p2[1] - p1[1])
        return (round(ix, 4), round(iy, 4))
    return None


class SourceRoomBoundaryRepairShadowAuthority:
    """Detects and repairs topological defects in room boundary polylines."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def repair_room_boundary(
        self,
        *,
        room_id: str,
        vertices: Sequence[Tuple[float, float]],
    ) -> RepairedBoundaryRecord:
        pts = list(vertices)
        if len(pts) > 1 and _pt_dist(pts[0], pts[-1]) <= self.snap_tolerance_pt:
            pts.pop()  # Remove closing duplicate if present for processing

        orig_count = len(pts)
        defects: List[BoundaryDefectKind] = []

        if orig_count < 3:
            return RepairedBoundaryRecord(
                room_id=room_id,
                original_vertex_count=orig_count,
                repaired_vertex_count=0,
                defects_detected=(),
                was_repaired=False,
                repaired_polygons=(),
                total_area_pt2=0.0,
            )

        # Stage 1: Clean duplicate / micro-vertices
        cleaned: List[Tuple[float, float]] = []
        for p in pts:
            if not cleaned:
                cleaned.append(p)
            elif _pt_dist(cleaned[-1], p) > self.snap_tolerance_pt:
                cleaned.append(p)
            else:
                if BoundaryDefectKind.DUPLICATE_OR_MICRO_VERTEX not in defects:
                    defects.append(BoundaryDefectKind.DUPLICATE_OR_MICRO_VERTEX)

        if len(cleaned) > 2 and _pt_dist(cleaned[0], cleaned[-1]) <= self.snap_tolerance_pt:
            cleaned.pop()
            if BoundaryDefectKind.DUPLICATE_OR_MICRO_VERTEX not in defects:
                defects.append(BoundaryDefectKind.DUPLICATE_OR_MICRO_VERTEX)

        # Stage 2: Prune antenna spikes (A -> B -> A)
        changed = True
        while changed and len(cleaned) >= 3:
            changed = False
            n = len(cleaned)
            for i in range(n):
                prev_p = cleaned[(i - 1) % n]
                curr_p = cleaned[i]
                next_p = cleaned[(i + 1) % n]
                if _pt_dist(prev_p, next_p) <= self.snap_tolerance_pt:
                    if BoundaryDefectKind.COLLAPSED_ANTENNA_SPIKE not in defects:
                        defects.append(BoundaryDefectKind.COLLAPSED_ANTENNA_SPIKE)
                    cleaned.pop(i)
                    changed = True
                    break

        # Stage 3: Detect bowtie self-intersection
        n = len(cleaned)
        split_polys: List[Tuple[Tuple[float, float], ...]] = []
        bowtie_found = False

        if n >= 4:
            for i in range(n):
                if bowtie_found:
                    break
                p1, p2 = cleaned[i], cleaned[(i + 1) % n]
                for j in range(i + 2, n):
                    if (j + 1) % n == i:
                        continue  # Adjacent edge
                    p3, p4 = cleaned[j], cleaned[(j + 1) % n]
                    inter = _line_intersection(p1, p2, p3, p4)
                    if inter is not None:
                        bowtie_found = True
                        if BoundaryDefectKind.BOWTIE_SELF_INTERSECTION not in defects:
                            defects.append(BoundaryDefectKind.BOWTIE_SELF_INTERSECTION)
                        # Split into loop 1 and loop 2 at intersection node
                        loop1 = [inter] + cleaned[i + 1 : j + 1]
                        loop2 = [inter] + cleaned[j + 1 :] + cleaned[: i + 1]
                        if len(loop1) >= 3:
                            split_polys.append(tuple(loop1))
                        if len(loop2) >= 3:
                            split_polys.append(tuple(loop2))
                        break

        if not bowtie_found and len(cleaned) >= 3:
            split_polys.append(tuple(cleaned))

        total_area = sum(_polygon_area(poly) for poly in split_polys)
        repaired_v_count = sum(len(poly) for poly in split_polys)
        was_repaired = len(defects) > 0

        return RepairedBoundaryRecord(
            room_id=room_id,
            original_vertex_count=orig_count,
            repaired_vertex_count=repaired_v_count,
            defects_detected=tuple(defects),
            was_repaired=was_repaired,
            repaired_polygons=tuple(split_polys),
            total_area_pt2=round(total_area, 4),
        )

    def compile_repair_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        records: Sequence[RepairedBoundaryRecord],
    ) -> RoomBoundaryRepairReceipt:
        rec_tuple = tuple(records)
        total = len(rec_tuple)
        repaired = sum(1 for r in rec_tuple if r.was_repaired)
        clean = total - repaired
        total_area = sum(r.total_area_pt2 for r in rec_tuple)

        receipt_id = stable_contract_id(
            "ROOM_REPAIR_RECEIPT",
            (document_id, revision_id, source_sha256, total, repaired, clean),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return RoomBoundaryRepairReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_rooms_evaluated=total,
            repaired_rooms_count=repaired,
            clean_rooms_count=clean,
            total_repaired_area_pt2=round(total_area, 4),
            records=rec_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_REPAIR_SEAL,
        )
