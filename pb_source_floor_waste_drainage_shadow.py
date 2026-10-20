"""Producer-Owned Source Floor Waste Drain & Pluvial Penetration Shadow Authority.

Workstream B Item 19:
Detects floor waste gullies (FWG), floor wastes (FW), and drainage outlet symbols
in wet areas, tracks slab coring/sleeving penetrations, and models puddle flange
waterproofing membrane clamping collars.

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

_WASTE_SEAL = object()


class DrainKind(str, Enum):
    FLOOR_WASTE_GULLY = "FLOOR_WASTE_GULLY"
    FLOOR_WASTE_SHOWER = "FLOOR_WASTE_SHOWER"
    BALCONY_DECK_DRAIN = "BALCONY_DECK_DRAIN"
    INSPECTION_OPENING = "INSPECTION_OPENING"


@dataclass(frozen=True)
class FloorWasteRecord:
    waste_id: str
    room_id: str
    drain_kind: DrainKind
    location_pt: Tuple[float, float]
    pipe_diameter_pt: float
    slab_penetration_diameter_pt: float
    has_puddle_flange: bool
    requires_fire_collar: bool
    grate_finish: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "waste_id": self.waste_id,
            "room_id": self.room_id,
            "drain_kind": self.drain_kind.value,
            "location_pt": list(self.location_pt),
            "pipe_diameter_pt": self.pipe_diameter_pt,
            "slab_penetration_diameter_pt": self.slab_penetration_diameter_pt,
            "has_puddle_flange": self.has_puddle_flange,
            "requires_fire_collar": self.requires_fire_collar,
            "grate_finish": self.grate_finish,
        }


@dataclass(frozen=True)
class FloorWasteDrainageReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_drains_count: int
    total_core_penetrations_count: int
    total_puddle_flanges_count: int
    total_fire_collars_count: int
    drains: Tuple[FloorWasteRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _WASTE_SEAL:
            raise TypeError("FloorWasteDrainageReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_drains_count": self.total_drains_count,
            "total_core_penetrations_count": self.total_core_penetrations_count,
            "total_puddle_flanges_count": self.total_puddle_flanges_count,
            "total_fire_collars_count": self.total_fire_collars_count,
            "drains": [d.to_dict() for d in self.drains],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceFloorWasteDrainageShadowAuthority:
    """Inventories floor wastes and drainage slab penetration details."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_floor_waste(
        self,
        *,
        room_id: str,
        drain_kind: DrainKind,
        location_pt: Tuple[float, float],
        pipe_diameter_pt: float = 0.0,
        has_puddle_flange: bool = True,
        requires_fire_collar: bool = False,
        grate_finish: str = "",
        sleeve_oversize_pt: float = 0.0,
    ) -> FloorWasteRecord:
        core_dia = pipe_diameter_pt + sleeve_oversize_pt

        w_id = stable_contract_id(
            "FLOOR_WASTE",
            (room_id, drain_kind.value, location_pt, round(pipe_diameter_pt, 2)),
        )

        return FloorWasteRecord(
            waste_id=w_id,
            room_id=room_id,
            drain_kind=drain_kind,
            location_pt=location_pt,
            pipe_diameter_pt=round(pipe_diameter_pt, 4),
            slab_penetration_diameter_pt=round(core_dia, 4),
            has_puddle_flange=has_puddle_flange,
            requires_fire_collar=requires_fire_collar,
            grate_finish=grate_finish,
        )

    def compile_waste_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        drains: Sequence[FloorWasteRecord],
    ) -> FloorWasteDrainageReceipt:
        d_tuple = tuple(drains)
        total = len(d_tuple)
        puddle_count = sum(1 for d in d_tuple if d.has_puddle_flange)
        fire_count = sum(1 for d in d_tuple if d.requires_fire_collar)

        receipt_id = stable_contract_id(
            "WASTE_DRAIN_RECEIPT",
            (document_id, revision_id, source_sha256, total, puddle_count, fire_count),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return FloorWasteDrainageReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_drains_count=total,
            total_core_penetrations_count=total,
            total_puddle_flanges_count=puddle_count,
            total_fire_collars_count=fire_count,
            drains=d_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_WASTE_SEAL,
        )
