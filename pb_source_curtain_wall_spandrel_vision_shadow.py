"""Producer-Owned Source Curtain Wall Spandrel Panel & Vision Glazing Partition Shadow Authority.

Workstream A Item 10 / Workstream B Item 13:
Partitions commercial curtain wall envelopes into transparent vision glazing bays
and opaque insulated spandrel panels, models shadowbox/backpan insulation,
and evaluates perimeter slab edge firestops.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_SPANDREL_SEAL = object()


@dataclass(frozen=True)
class CurtainWallBayRecord:
    bay_id: str
    wall_id: str
    bay_width_pt: float
    story_height_pt: float
    vision_sill_height_pt: float
    vision_head_height_pt: float
    vision_area_pt2: float
    spandrel_area_pt2: float
    spandrel_insulation_volume_pt3: float
    slab_edge_firestop_length_pt: float
    spandrel_glass_finish: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "bay_id": self.bay_id,
            "wall_id": self.wall_id,
            "bay_width_pt": self.bay_width_pt,
            "story_height_pt": self.story_height_pt,
            "vision_sill_height_pt": self.vision_sill_height_pt,
            "vision_head_height_pt": self.vision_head_height_pt,
            "vision_area_pt2": self.vision_area_pt2,
            "spandrel_area_pt2": self.spandrel_area_pt2,
            "spandrel_insulation_volume_pt3": self.spandrel_insulation_volume_pt3,
            "slab_edge_firestop_length_pt": self.slab_edge_firestop_length_pt,
            "spandrel_glass_finish": self.spandrel_glass_finish,
        }


@dataclass(frozen=True)
class CurtainWallSpandrelVisionReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_bays_count: int
    total_vision_area_pt2: float
    total_spandrel_area_pt2: float
    total_spandrel_insulation_volume_pt3: float
    bays: Tuple[CurtainWallBayRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _SPANDREL_SEAL:
            raise TypeError("CurtainWallSpandrelVisionReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_bays_count": self.total_bays_count,
            "total_vision_area_pt2": self.total_vision_area_pt2,
            "total_spandrel_area_pt2": self.total_spandrel_area_pt2,
            "total_spandrel_insulation_volume_pt3": self.total_spandrel_insulation_volume_pt3,
            "bays": [b.to_dict() for b in self.bays],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceCurtainWallSpandrelVisionShadowAuthority:
    """Partitions curtain wall bays into vision glazing, spandrel panels, and firestop seals."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_curtain_wall_bay(
        self,
        *,
        bay_id: str,
        wall_id: str,
        bay_width_pt: float = 0.0,
        story_height_pt: float = 0.0,
        vision_sill_height_pt: float = 0.0,
        vision_head_height_pt: float = 0.0,
        spandrel_insulation_thickness_pt: float = 0.0,
        spandrel_finish: str = "",
    ) -> CurtainWallBayRecord:
        clamped_sill = max(0.0, min(vision_sill_height_pt, story_height_pt))
        clamped_head = max(clamped_sill, min(vision_head_height_pt, story_height_pt))

        vision_h = clamped_head - clamped_sill
        spandrel_h = clamped_sill + (story_height_pt - clamped_head)

        vision_area = bay_width_pt * vision_h
        spandrel_area = bay_width_pt * spandrel_h
        insul_vol = spandrel_area * spandrel_insulation_thickness_pt

        return CurtainWallBayRecord(
            bay_id=bay_id,
            wall_id=wall_id,
            bay_width_pt=round(bay_width_pt, 4),
            story_height_pt=round(story_height_pt, 4),
            vision_sill_height_pt=round(clamped_sill, 4),
            vision_head_height_pt=round(clamped_head, 4),
            vision_area_pt2=round(vision_area, 4),
            spandrel_area_pt2=round(spandrel_area, 4),
            spandrel_insulation_volume_pt3=round(insul_vol, 4),
            slab_edge_firestop_length_pt=round(bay_width_pt, 4),
            spandrel_glass_finish=spandrel_finish,
        )

    def compile_curtain_wall_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        bays: Sequence[CurtainWallBayRecord],
    ) -> CurtainWallSpandrelVisionReceipt:
        b_tuple = tuple(bays)
        total = len(b_tuple)
        total_vision = sum(b.vision_area_pt2 for b in b_tuple)
        total_spandrel = sum(b.spandrel_area_pt2 for b in b_tuple)
        total_insul = sum(b.spandrel_insulation_volume_pt3 for b in b_tuple)

        receipt_id = stable_contract_id(
            "CURTAIN_WALL_RECEIPT",
            (document_id, revision_id, source_sha256, total, round(total_vision, 2)),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return CurtainWallSpandrelVisionReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_bays_count=total,
            total_vision_area_pt2=round(total_vision, 4),
            total_spandrel_area_pt2=round(total_spandrel, 4),
            total_spandrel_insulation_volume_pt3=round(total_insul, 4),
            bays=b_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_SPANDREL_SEAL,
        )
