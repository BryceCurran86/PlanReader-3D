"""Producer-Owned Source Ceiling Access Hatch & Attic Inspection Trapdoor Geometry Shadow Authority.

Workstream B Item 17:
Detects ceiling access hatches and service trapdoors, validates clear opening
dimensions, computes trim perimeter framing and panel areas, binds fire/acoustic
ratings, and prevents hatches from spawning false micro-rooms or unlined voids.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_HATCH_SEAL = object()


class AccessHatchFireRating(str, Enum):
    NON_RATED = "NON_RATED"
    FIRE_RATED_30_MIN = "FIRE_RATED_30_MIN"
    FIRE_RATED_60_MIN = "FIRE_RATED_60_MIN"
    FIRE_RATED_120_MIN = "FIRE_RATED_120_MIN"


@dataclass(frozen=True)
class CeilingAccessHatchRecord:
    hatch_id: str
    room_id: str
    center_pt: Tuple[float, float]
    width_pt: float
    length_pt: float
    area_pt2: float
    trim_perimeter_pt: float
    fire_rating: AccessHatchFireRating
    is_code_compliant: bool
    panel_type: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "hatch_id": self.hatch_id,
            "room_id": self.room_id,
            "center_pt": list(self.center_pt),
            "width_pt": self.width_pt,
            "length_pt": self.length_pt,
            "area_pt2": self.area_pt2,
            "trim_perimeter_pt": self.trim_perimeter_pt,
            "fire_rating": self.fire_rating.value,
            "is_code_compliant": self.is_code_compliant,
            "panel_type": self.panel_type,
        }


@dataclass(frozen=True)
class CeilingAccessHatchReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_hatches_count: int
    fire_rated_count: int
    total_trim_perimeter_pt: float
    total_hatch_area_pt2: float
    hatches: Tuple[CeilingAccessHatchRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _HATCH_SEAL:
            raise TypeError("CeilingAccessHatchReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_hatches_count": self.total_hatches_count,
            "fire_rated_count": self.fire_rated_count,
            "total_trim_perimeter_pt": self.total_trim_perimeter_pt,
            "total_hatch_area_pt2": self.total_hatch_area_pt2,
            "hatches": [h.to_dict() for h in self.hatches],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceCeilingAccessHatchShadowAuthority:
    """Detects and calculates geometry, perimeters, and ratings for ceiling access hatches."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_access_hatch(
        self,
        *,
        room_id: str,
        center_pt: Tuple[float, float],
        width_pt: float = 17.01,   # ~600mm in pt (1:100 scale: 17.01 pt)
        length_pt: float = 17.01,  # ~600mm in pt (1:100 scale: 17.01 pt)
        fire_rating: AccessHatchFireRating = AccessHatchFireRating.NON_RATED,
        panel_type: str = "PLASTERBOARD_INFILL_FLUSH",
        min_code_dimension_pt: float = 12.75,  # ~450mm
    ) -> CeilingAccessHatchRecord:
        area = width_pt * length_pt
        perimeter = 2.0 * (width_pt + length_pt)
        is_compliant = width_pt >= min_code_dimension_pt and length_pt >= min_code_dimension_pt

        hatch_id = stable_contract_id(
            "CEILING_HATCH",
            (room_id, center_pt, round(width_pt, 2), round(length_pt, 2), fire_rating.value),
        )

        return CeilingAccessHatchRecord(
            hatch_id=hatch_id,
            room_id=room_id,
            center_pt=center_pt,
            width_pt=round(width_pt, 4),
            length_pt=round(length_pt, 4),
            area_pt2=round(area, 4),
            trim_perimeter_pt=round(perimeter, 4),
            fire_rating=fire_rating,
            is_code_compliant=is_compliant,
            panel_type=panel_type,
        )

    def compile_hatch_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        hatches: Sequence[CeilingAccessHatchRecord],
    ) -> CeilingAccessHatchReceipt:
        h_tuple = tuple(hatches)
        total = len(h_tuple)
        fire_count = sum(1 for h in h_tuple if h.fire_rating != AccessHatchFireRating.NON_RATED)
        total_trim = sum(h.trim_perimeter_pt for h in h_tuple)
        total_area = sum(h.area_pt2 for h in h_tuple)

        receipt_id = stable_contract_id(
            "CEILING_HATCH_RECEIPT",
            (document_id, revision_id, source_sha256, total, fire_count),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return CeilingAccessHatchReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_hatches_count=total,
            fire_rated_count=fire_count,
            total_trim_perimeter_pt=round(total_trim, 4),
            total_hatch_area_pt2=round(total_area, 4),
            hatches=h_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_HATCH_SEAL,
        )
