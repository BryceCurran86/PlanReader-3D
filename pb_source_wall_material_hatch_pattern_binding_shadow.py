"""Producer-Owned Source Wall Material Hatch Pattern Semantic Binding Shadow Authority.

Workstream A Item 5:
Classifies 2D vector hatch patterns (diagonal hatching, cross-hatch, stipple,
solid fill, insulated zig-zag) within closed wall boundaries to bind architectural/
structural material specifications (concrete, brickwork, CMU, stud drywall, insulated sandwich panel).

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


class WallHatchType(str, Enum):
    SOLID_FILL = "SOLID_FILL"
    DIAGONAL_SINGLE = "DIAGONAL_SINGLE"
    CROSS_HATCH_DIAMOND = "CROSS_HATCH_DIAMOND"
    STIPPLE_DOTS = "STIPPLE_DOTS"
    INSULATION_BATT_OR_ZIGZAG = "INSULATION_BATT_OR_ZIGZAG"
    EMPTY_OR_UNHATCHED = "EMPTY_OR_UNHATCHED"


@dataclass(frozen=True)
class WallMaterialBindingRecord:
    wall_id: str
    detected_hatch: WallHatchType
    bound_material: str
    confidence: float
    hatch_line_count: int
    is_structural: bool
    spacing_pt: float

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "wall_id": self.wall_id,
            "detected_hatch": self.detected_hatch.value,
            "bound_material": self.bound_material,
            "confidence": self.confidence,
            "hatch_line_count": self.hatch_line_count,
            "is_structural": self.is_structural,
            "spacing_pt": self.spacing_pt,
        }


@dataclass(frozen=True)
class WallMaterialBindingReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_walls_evaluated: int
    bound_materials_count: int
    unhatched_count: int
    bindings: Tuple[WallMaterialBindingRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _HATCH_SEAL:
            raise TypeError("WallMaterialBindingReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_walls_evaluated": self.total_walls_evaluated,
            "bound_materials_count": self.bound_materials_count,
            "unhatched_count": self.unhatched_count,
            "bindings": [b.to_dict() for b in self.bindings],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceWallMaterialHatchPatternBindingShadowAuthority:
    """Binds vector hatch patterns within wall boundaries to semantic materials."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def bind_wall_hatch(
        self,
        *,
        wall_id: str,
        hatch_type: WallHatchType,
        interior_lines_count: int = 0,
        average_spacing_pt: float = 0.0,
    ) -> WallMaterialBindingRecord:
        if hatch_type == WallHatchType.SOLID_FILL:
            mat = "REINFORCED_CONCRETE"
            conf = 0.95
            is_struct = True
        elif hatch_type == WallHatchType.DIAGONAL_SINGLE:
            mat = "BRICK_MASONRY"
            conf = 0.90 if interior_lines_count >= 3 else 0.70
            is_struct = True
        elif hatch_type == WallHatchType.CROSS_HATCH_DIAMOND:
            mat = "CONCRETE_MASONRY_UNIT"
            conf = 0.92 if interior_lines_count >= 4 else 0.75
            is_struct = True
        elif hatch_type == WallHatchType.STIPPLE_DOTS:
            mat = "CAST_IN_PLACE_CONCRETE"
            conf = 0.88
            is_struct = True
        elif hatch_type == WallHatchType.INSULATION_BATT_OR_ZIGZAG:
            mat = "INSULATED_SANDWICH_PANEL"
            conf = 0.94
            is_struct = True
        else:
            mat = "LIGHTWEIGHT_STUD_DRYWALL"
            conf = 0.60
            is_struct = False

        return WallMaterialBindingRecord(
            wall_id=wall_id,
            detected_hatch=hatch_type,
            bound_material=mat,
            confidence=conf,
            hatch_line_count=interior_lines_count,
            is_structural=is_struct,
            spacing_pt=round(average_spacing_pt, 4),
        )

    def compile_hatch_binding_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        bindings: Sequence[WallMaterialBindingRecord],
    ) -> WallMaterialBindingReceipt:
        b_tuple = tuple(bindings)
        total = len(b_tuple)
        bound_count = sum(1 for b in b_tuple if b.detected_hatch != WallHatchType.EMPTY_OR_UNHATCHED)
        unhatched_count = total - bound_count

        receipt_id = stable_contract_id(
            "WALL_HATCH_BINDING_RECEIPT",
            (document_id, revision_id, source_sha256, total, bound_count, unhatched_count),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return WallMaterialBindingReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_walls_evaluated=total,
            bound_materials_count=bound_count,
            unhatched_count=unhatched_count,
            bindings=b_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_HATCH_SEAL,
        )
