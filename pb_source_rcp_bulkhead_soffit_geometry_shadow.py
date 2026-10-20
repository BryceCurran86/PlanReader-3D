"""Producer-Owned Source Reflected Ceiling Plan Bulkhead & Soffit Stepped Geometry Shadow Authority.

Workstream B Item 16:
Extracts multi-level ceiling boundaries, stepped bulkheads, perimeter soffits,
and dropped ceiling zones from RCP sheets. Calculates vertical fascia drop
surface areas (delta H x step length) and partitions room ceiling planes into
tiered horizontal zones.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_BULKHEAD_SEAL = object()


@dataclass(frozen=True)
class BulkheadStepRecord:
    bulkhead_id: str
    room_id: str
    high_level_pt: float
    low_level_pt: float
    step_height_pt: float
    step_length_pt: float
    fascia_area_pt2: float
    soffit_area_pt2: float
    bulkhead_polygon: Tuple[Tuple[float, float], ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "bulkhead_id": self.bulkhead_id,
            "room_id": self.room_id,
            "high_level_pt": self.high_level_pt,
            "low_level_pt": self.low_level_pt,
            "step_height_pt": self.step_height_pt,
            "step_length_pt": self.step_length_pt,
            "fascia_area_pt2": self.fascia_area_pt2,
            "soffit_area_pt2": self.soffit_area_pt2,
            "bulkhead_polygon": [list(pt) for pt in self.bulkhead_polygon],
        }


@dataclass(frozen=True)
class CeilingBulkheadSoffitReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_bulkheads_count: int
    total_fascia_area_pt2: float
    total_soffit_area_pt2: float
    bulkheads: Tuple[BulkheadStepRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _BULKHEAD_SEAL:
            raise TypeError("CeilingBulkheadSoffitReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_bulkheads_count": self.total_bulkheads_count,
            "total_fascia_area_pt2": self.total_fascia_area_pt2,
            "total_soffit_area_pt2": self.total_soffit_area_pt2,
            "bulkheads": [b.to_dict() for b in self.bulkheads],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


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


class SourceRcpBulkheadSoffitGeometryShadowAuthority:
    """Calculates stepped ceiling geometry and vertical fascia drop surface areas."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_bulkhead_step(
        self,
        *,
        bulkhead_id: str,
        room_id: str,
        high_level_pt: float,
        low_level_pt: float,
        step_length_pt: float,
        soffit_polygon: Sequence[Tuple[float, float]],
    ) -> BulkheadStepRecord:
        poly_tuple = tuple(soffit_polygon)
        soffit_area = _polygon_area(poly_tuple)
        step_h = max(0.0, high_level_pt - low_level_pt)
        fascia_area = step_length_pt * step_h

        return BulkheadStepRecord(
            bulkhead_id=bulkhead_id,
            room_id=room_id,
            high_level_pt=round(high_level_pt, 4),
            low_level_pt=round(low_level_pt, 4),
            step_height_pt=round(step_h, 4),
            step_length_pt=round(step_length_pt, 4),
            fascia_area_pt2=round(fascia_area, 4),
            soffit_area_pt2=round(soffit_area, 4),
            bulkhead_polygon=poly_tuple,
        )

    def compile_bulkhead_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        bulkheads: Sequence[BulkheadStepRecord],
    ) -> CeilingBulkheadSoffitReceipt:
        b_tuple = tuple(bulkheads)
        total = len(b_tuple)
        total_fascia = sum(b.fascia_area_pt2 for b in b_tuple)
        total_soffit = sum(b.soffit_area_pt2 for b in b_tuple)

        receipt_id = stable_contract_id(
            "BULKHEAD_RECEIPT",
            (document_id, revision_id, source_sha256, total, round(total_fascia, 2)),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return CeilingBulkheadSoffitReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_bulkheads_count=total,
            total_fascia_area_pt2=round(total_fascia, 4),
            total_soffit_area_pt2=round(total_soffit, 4),
            bulkheads=b_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_BULKHEAD_SEAL,
        )
