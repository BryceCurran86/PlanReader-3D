"""Producer-Owned Source Skirting Board & Wall Base Finish Linear Takeoff Shadow Authority.

Workstream B Item 20:
Computes net linear skirting and wall base trim takeoffs per room, rigorously
deducting doorway threshold opening widths and built-in joinery contact lengths,
and tracking internal vs external mitre corners.

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

_SKIRTING_SEAL = object()


class SkirtingMaterialProfile(str, Enum):
    TIMBER_MDF_BEVELLED = "TIMBER_MDF_BEVELLED"
    TIMBER_COLONIAL = "TIMBER_COLONIAL"
    VINYL_COVE_FORMED = "VINYL_COVE_FORMED"
    ALUMINUM_SHADOWLINE = "ALUMINUM_SHADOWLINE"
    TILED_SKIRTING = "TILED_SKIRTING"


@dataclass(frozen=True)
class RoomSkirtingRecord:
    record_id: str
    room_id: str
    gross_perimeter_pt: float
    doorways_deduction_pt: float
    joinery_deduction_pt: float
    net_skirting_length_pt: float
    skirting_profile: SkirtingMaterialProfile
    internal_corners_count: int
    external_corners_count: int

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "record_id": self.record_id,
            "room_id": self.room_id,
            "gross_perimeter_pt": self.gross_perimeter_pt,
            "doorways_deduction_pt": self.doorways_deduction_pt,
            "joinery_deduction_pt": self.joinery_deduction_pt,
            "net_skirting_length_pt": self.net_skirting_length_pt,
            "skirting_profile": self.skirting_profile.value,
            "internal_corners_count": self.internal_corners_count,
            "external_corners_count": self.external_corners_count,
        }


@dataclass(frozen=True)
class SkirtingWallBaseReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_rooms_count: int
    total_gross_perimeter_pt: float
    total_doorways_deducted_pt: float
    total_net_skirting_length_pt: float
    total_internal_corners_count: int
    total_external_corners_count: int
    records: Tuple[RoomSkirtingRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _SKIRTING_SEAL:
            raise TypeError("SkirtingWallBaseReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_rooms_count": self.total_rooms_count,
            "total_gross_perimeter_pt": self.total_gross_perimeter_pt,
            "total_doorways_deducted_pt": self.total_doorways_deducted_pt,
            "total_net_skirting_length_pt": self.total_net_skirting_length_pt,
            "total_internal_corners_count": self.total_internal_corners_count,
            "total_external_corners_count": self.total_external_corners_count,
            "records": [r.to_dict() for r in self.records],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceSkirtingWallBaseShadowAuthority:
    """Computes net linear skirting and wall base trim takeoffs with doorway and joinery deductions."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_room_skirting(
        self,
        *,
        room_id: str,
        gross_perimeter_pt: float,
        doorway_widths_pt: Sequence[float] = (),
        joinery_lengths_pt: Sequence[float] = (),
        profile: SkirtingMaterialProfile = SkirtingMaterialProfile.TIMBER_MDF_BEVELLED,
        internal_corners_count: int = 0,
        external_corners_count: int = 0,
    ) -> RoomSkirtingRecord:
        door_ded = sum(doorway_widths_pt)
        join_ded = sum(joinery_lengths_pt)
        net_len = max(0.0, gross_perimeter_pt - door_ded - join_ded)

        rec_id = stable_contract_id(
            "ROOM_SKIRTING",
            (room_id, profile.value, round(gross_perimeter_pt, 2), round(net_len, 2)),
        )

        return RoomSkirtingRecord(
            record_id=rec_id,
            room_id=room_id,
            gross_perimeter_pt=round(gross_perimeter_pt, 4),
            doorways_deduction_pt=round(door_ded, 4),
            joinery_deduction_pt=round(join_ded, 4),
            net_skirting_length_pt=round(net_len, 4),
            skirting_profile=profile,
            internal_corners_count=internal_corners_count,
            external_corners_count=external_corners_count,
        )

    def compile_skirting_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        records: Sequence[RoomSkirtingRecord],
    ) -> SkirtingWallBaseReceipt:
        r_tuple = tuple(records)
        total = len(r_tuple)
        gross_perim = sum(r.gross_perimeter_pt for r in r_tuple)
        door_ded = sum(r.doorways_deduction_pt for r in r_tuple)
        net_skirting = sum(r.net_skirting_length_pt for r in r_tuple)
        int_corners = sum(r.internal_corners_count for r in r_tuple)
        ext_corners = sum(r.external_corners_count for r in r_tuple)

        receipt_id = stable_contract_id(
            "SKIRTING_RECEIPT",
            (document_id, revision_id, source_sha256, total, round(net_skirting, 2)),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return SkirtingWallBaseReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_rooms_count=total,
            total_gross_perimeter_pt=round(gross_perim, 4),
            total_doorways_deducted_pt=round(door_ded, 4),
            total_net_skirting_length_pt=round(net_skirting, 4),
            total_internal_corners_count=int_corners,
            total_external_corners_count=ext_corners,
            records=r_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_SKIRTING_SEAL,
        )
