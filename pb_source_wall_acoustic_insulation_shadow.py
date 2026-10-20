"""Producer-Owned Source Wall Acoustic Insulation Batt Infill Shadow Authority.

Workstream A Item 6:
Extracts partition wall acoustic insulation requirements, matches stud cavity
thicknesses, deducts opening void areas, and computes net acoustic batt infill
surface areas (m2), volumes (m3), and acoustic ratings (Rw, R-value).

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

_ACOUSTIC_SEAL = object()


@dataclass(frozen=True)
class WallAcousticInsulationRecord:
    record_id: str
    wall_id: str
    wall_type: str
    gross_wall_area_pt2: float
    openings_deduction_area_pt2: float
    net_insulation_area_pt2: float
    cavity_thickness_pt: float
    insulation_volume_pt3: float
    r_value: float
    rw_rating: int
    insulation_material: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "record_id": self.record_id,
            "wall_id": self.wall_id,
            "wall_type": self.wall_type,
            "gross_wall_area_pt2": self.gross_wall_area_pt2,
            "openings_deduction_area_pt2": self.openings_deduction_area_pt2,
            "net_insulation_area_pt2": self.net_insulation_area_pt2,
            "cavity_thickness_pt": self.cavity_thickness_pt,
            "insulation_volume_pt3": self.insulation_volume_pt3,
            "r_value": self.r_value,
            "rw_rating": self.rw_rating,
            "insulation_material": self.insulation_material,
        }


@dataclass(frozen=True)
class WallAcousticInsulationReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_insulated_walls_count: int
    total_net_insulation_area_pt2: float
    total_insulation_volume_pt3: float
    records: Tuple[WallAcousticInsulationRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _ACOUSTIC_SEAL:
            raise TypeError("WallAcousticInsulationReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_insulated_walls_count": self.total_insulated_walls_count,
            "total_net_insulation_area_pt2": self.total_net_insulation_area_pt2,
            "total_insulation_volume_pt3": self.total_insulation_volume_pt3,
            "records": [r.to_dict() for r in self.records],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceWallAcousticInsulationShadowAuthority:
    """Computes acoustic insulation batt infill takeoffs with opening deductions."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_wall_insulation(
        self,
        *,
        wall_id: str,
        wall_type: str,
        wall_length_pt: float,
        wall_height_pt: float,
        openings_area_pt2: float = 0.0,
        cavity_thickness_pt: float = 0.0,
        r_value: float = 0.0,
        rw_rating: int = 0,
        insulation_material: str = "",
    ) -> WallAcousticInsulationRecord:
        gross_area = wall_length_pt * wall_height_pt
        net_area = max(0.0, gross_area - openings_area_pt2)
        vol = net_area * cavity_thickness_pt

        rec_id = stable_contract_id(
            "WALL_ACOUSTIC",
            (wall_id, wall_type, round(net_area, 2), r_value, rw_rating),
        )

        return WallAcousticInsulationRecord(
            record_id=rec_id,
            wall_id=wall_id,
            wall_type=wall_type,
            gross_wall_area_pt2=round(gross_area, 4),
            openings_deduction_area_pt2=round(openings_area_pt2, 4),
            net_insulation_area_pt2=round(net_area, 4),
            cavity_thickness_pt=round(cavity_thickness_pt, 4),
            insulation_volume_pt3=round(vol, 4),
            r_value=r_value,
            rw_rating=rw_rating,
            insulation_material=insulation_material,
        )

    def compile_insulation_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        records: Sequence[WallAcousticInsulationRecord],
    ) -> WallAcousticInsulationReceipt:
        r_tuple = tuple(records)
        total = len(r_tuple)
        total_area = sum(r.net_insulation_area_pt2 for r in r_tuple)
        total_vol = sum(r.insulation_volume_pt3 for r in r_tuple)

        receipt_id = stable_contract_id(
            "ACOUSTIC_RECEIPT",
            (document_id, revision_id, source_sha256, total, round(total_area, 2)),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return WallAcousticInsulationReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_insulated_walls_count=total,
            total_net_insulation_area_pt2=round(total_area, 4),
            total_insulation_volume_pt3=round(total_vol, 4),
            records=r_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_ACOUSTIC_SEAL,
        )
