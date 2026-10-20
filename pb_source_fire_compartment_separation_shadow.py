"""Producer-Owned Source Fire Compartment Separation Wall & Damper Penetration Shadow Authority.

Workstream A Item 3:
Classifies fire-rated separating walls with Fire Resistance Levels (FRL
structural/integrity/insulation, e.g. 60/60/60, 90/90/90), binds fire door ratings,
and registers service penetrations requiring fire dampers and intumescent collar seals.

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

_FIRE_SEAL = object()


@dataclass(frozen=True)
class FirePenetrationRecord:
    penetration_id: str
    wall_id: str
    penetration_type: str
    service_dimension_pt: float
    damper_rating_min: int

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "penetration_id": self.penetration_id,
            "wall_id": self.wall_id,
            "penetration_type": self.penetration_type,
            "service_dimension_pt": self.service_dimension_pt,
            "damper_rating_min": self.damper_rating_min,
        }


@dataclass(frozen=True)
class FireCompartmentWallRecord:
    wall_id: str
    frl_rating: str
    compartment_boundary_type: str
    wall_length_pt: float
    wall_height_pt: float
    wall_area_pt2: float
    penetrations: Tuple[FirePenetrationRecord, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "wall_id": self.wall_id,
            "frl_rating": self.frl_rating,
            "compartment_boundary_type": self.compartment_boundary_type,
            "wall_length_pt": self.wall_length_pt,
            "wall_height_pt": self.wall_height_pt,
            "wall_area_pt2": self.wall_area_pt2,
            "penetrations": [p.to_dict() for p in self.penetrations],
        }


@dataclass(frozen=True)
class FireCompartmentSeparationReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_fire_walls_count: int
    total_fire_wall_area_pt2: float
    total_fire_dampers_count: int
    total_collars_count: int
    walls: Tuple[FireCompartmentWallRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _FIRE_SEAL:
            raise TypeError("FireCompartmentSeparationReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_fire_walls_count": self.total_fire_walls_count,
            "total_fire_wall_area_pt2": self.total_fire_wall_area_pt2,
            "total_fire_dampers_count": self.total_fire_dampers_count,
            "total_collars_count": self.total_collars_count,
            "walls": [w.to_dict() for w in self.walls],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceFireCompartmentSeparationShadowAuthority:
    """Manages fire compartment wall barriers and service penetration protection items."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def create_fire_wall(
        self,
        *,
        wall_id: str,
        frl_rating: str = "90/90/90",
        boundary_type: str = "INTER_TENANCY_PARTY_WALL",
        wall_length_pt: float,
        wall_height_pt: float,
        penetrations: Sequence[FirePenetrationRecord] = (),
    ) -> FireCompartmentWallRecord:
        area = wall_length_pt * wall_height_pt

        return FireCompartmentWallRecord(
            wall_id=wall_id,
            frl_rating=frl_rating,
            compartment_boundary_type=boundary_type,
            wall_length_pt=round(wall_length_pt, 4),
            wall_height_pt=round(wall_height_pt, 4),
            wall_area_pt2=round(area, 4),
            penetrations=tuple(penetrations),
        )

    def create_penetration(
        self,
        *,
        wall_id: str,
        penetration_type: str = "FIRE_DAMPER",
        service_dimension_pt: float = 10.0,
        damper_rating_min: int = 90,
    ) -> FirePenetrationRecord:
        pen_id = stable_contract_id(
            "FIRE_PEN",
            (wall_id, penetration_type, round(service_dimension_pt, 2), damper_rating_min),
        )

        return FirePenetrationRecord(
            penetration_id=pen_id,
            wall_id=wall_id,
            penetration_type=penetration_type,
            service_dimension_pt=round(service_dimension_pt, 4),
            damper_rating_min=damper_rating_min,
        )

    def compile_fire_compartment_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        walls: Sequence[FireCompartmentWallRecord],
    ) -> FireCompartmentSeparationReceipt:
        w_tuple = tuple(walls)
        total = len(w_tuple)
        total_area = sum(w.wall_area_pt2 for w in w_tuple)

        all_pens = [p for w in w_tuple for p in w.penetrations]
        dampers = sum(1 for p in all_pens if p.penetration_type == "FIRE_DAMPER")
        collars = sum(1 for p in all_pens if p.penetration_type == "INTUMESCENT_COLLAR")

        receipt_id = stable_contract_id(
            "FIRE_SEPARATION_RECEIPT",
            (document_id, revision_id, source_sha256, total, dampers, collars),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return FireCompartmentSeparationReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_fire_walls_count=total,
            total_fire_wall_area_pt2=round(total_area, 4),
            total_fire_dampers_count=dampers,
            total_collars_count=collars,
            walls=w_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_FIRE_SEAL,
        )
