"""Producer-Owned Source Wet Area Waterproofing Membrane & Wall Upstand Height Shadow Authority.

Workstream B Item 15:
Extracts wet area room boundaries, identifies internal shower cubicles vs general
bathroom zones, computes horizontal floor membrane areas and vertical perimeter
upstand heights (150mm general upstand, 1800-2000mm shower wall tanking), and
resolves total membrane surface takeoff.

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

_WATERPROOFING_SEAL = object()


class WetAreaKind(str, Enum):
    BATHROOM = "BATHROOM"
    ENSUITE = "ENSUITE"
    LAUNDRY = "LAUNDRY"
    POWDER_ROOM = "POWDER_ROOM"
    COMMERCIAL_KITCHEN = "COMMERCIAL_KITCHEN"


@dataclass(frozen=True)
class WetAreaWaterproofingRecord:
    wet_area_id: str
    room_id: str
    kind: WetAreaKind
    floor_area_pt2: float
    general_perimeter_pt: float
    general_upstand_height_pt: float
    shower_perimeter_pt: float
    shower_tanking_height_pt: float
    vertical_upstand_area_pt2: float
    total_membrane_area_pt2: float
    membrane_system_spec: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "wet_area_id": self.wet_area_id,
            "room_id": self.room_id,
            "kind": self.kind.value,
            "floor_area_pt2": self.floor_area_pt2,
            "general_perimeter_pt": self.general_perimeter_pt,
            "general_upstand_height_pt": self.general_upstand_height_pt,
            "shower_perimeter_pt": self.shower_perimeter_pt,
            "shower_tanking_height_pt": self.shower_tanking_height_pt,
            "vertical_upstand_area_pt2": self.vertical_upstand_area_pt2,
            "total_membrane_area_pt2": self.total_membrane_area_pt2,
            "membrane_system_spec": self.membrane_system_spec,
        }


@dataclass(frozen=True)
class WetAreaWaterproofingReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_wet_areas_count: int
    total_floor_membrane_pt2: float
    total_vertical_upstand_pt2: float
    total_membrane_takeoff_pt2: float
    wet_areas: Tuple[WetAreaWaterproofingRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _WATERPROOFING_SEAL:
            raise TypeError("WetAreaWaterproofingReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_wet_areas_count": self.total_wet_areas_count,
            "total_floor_membrane_pt2": self.total_floor_membrane_pt2,
            "total_vertical_upstand_pt2": self.total_vertical_upstand_pt2,
            "total_membrane_takeoff_pt2": self.total_membrane_takeoff_pt2,
            "wet_areas": [w.to_dict() for w in self.wet_areas],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceWetAreaWaterproofingShadowAuthority:
    """Calculates horizontal and vertical upstand membrane surface areas for wet areas."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_wet_area_waterproofing(
        self,
        *,
        room_id: str,
        kind: WetAreaKind,
        floor_area_pt2: float,
        general_perimeter_pt: float,
        shower_perimeter_pt: float = 0.0,
        general_upstand_height_pt: float = 4.25,   # ~150mm in pt (1:100 scale: 4.25 pt)
        shower_tanking_height_pt: float = 56.69,   # ~2000mm in pt (1:100 scale: 56.69 pt)
        membrane_spec: str = "CLASS_III_POLYURETHANE_MEMBRANE",
    ) -> WetAreaWaterproofingRecord:
        gen_upstand_area = general_perimeter_pt * general_upstand_height_pt
        shower_tanking_area = shower_perimeter_pt * shower_tanking_height_pt
        total_vert = gen_upstand_area + shower_tanking_area
        total_membrane = floor_area_pt2 + total_vert

        area_id = stable_contract_id(
            "WET_AREA",
            (room_id, kind.value, round(floor_area_pt2, 2), round(total_membrane, 2)),
        )

        return WetAreaWaterproofingRecord(
            wet_area_id=area_id,
            room_id=room_id,
            kind=kind,
            floor_area_pt2=round(floor_area_pt2, 4),
            general_perimeter_pt=round(general_perimeter_pt, 4),
            general_upstand_height_pt=round(general_upstand_height_pt, 4),
            shower_perimeter_pt=round(shower_perimeter_pt, 4),
            shower_tanking_height_pt=round(shower_tanking_height_pt, 4),
            vertical_upstand_area_pt2=round(total_vert, 4),
            total_membrane_area_pt2=round(total_membrane, 4),
            membrane_system_spec=membrane_spec,
        )

    def compile_waterproofing_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        wet_areas: Sequence[WetAreaWaterproofingRecord],
    ) -> WetAreaWaterproofingReceipt:
        w_tuple = tuple(wet_areas)
        total = len(w_tuple)
        total_floor = sum(w.floor_area_pt2 for w in w_tuple)
        total_vert = sum(w.vertical_upstand_area_pt2 for w in w_tuple)
        total_takeoff = sum(w.total_membrane_area_pt2 for w in w_tuple)

        receipt_id = stable_contract_id(
            "WATERPROOF_RECEIPT",
            (document_id, revision_id, source_sha256, total, round(total_takeoff, 2)),
        )

        status = EvidenceResolutionStatus.CORROBORATED if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return WetAreaWaterproofingReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_wet_areas_count=total,
            total_floor_membrane_pt2=round(total_floor, 4),
            total_vertical_upstand_pt2=round(total_vert, 4),
            total_membrane_takeoff_pt2=round(total_takeoff, 4),
            wet_areas=w_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_WATERPROOFING_SEAL,
        )
