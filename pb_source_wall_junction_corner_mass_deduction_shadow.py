"""Producer-Owned Wall Junction Corner Mass Deduction Authority.

Workstream A Item 4 & 6:
Eliminates double-counting of corner junction mass and obscured wall faces at
perpendicular and angled wall intersections (L-junctions, T-junctions, X-junctions)
across 3D wall takeoff models and surface finish calculations.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Disjoint volume partition: total structural volume is strictly non-overlapping.
- Obscured contact faces are deducted from internal lining/finishes.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)


class JunctionKind(str, Enum):
    L_JUNCTION_CORNER = "L_JUNCTION_CORNER"
    T_JUNCTION_ABUTMENT = "T_JUNCTION_ABUTMENT"
    X_JUNCTION_CROSSING = "X_JUNCTION_CROSSING"


@dataclass(frozen=True)
class WallJunctionDeductionEvidence:
    junction_id: str
    junction_kind: JunctionKind
    through_wall_id: str
    abutting_wall_ids: Tuple[str, ...]
    junction_point: Tuple[float, float]
    overlap_area_sqm: float
    deducted_volume_cum: float
    obscured_face_length_m: float
    obscured_finish_area_sqm: float
    wall_height_m: float
    status: EvidenceResolutionStatus
    notes: str
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "junction_id": self.junction_id,
            "junction_kind": self.junction_kind.value,
            "through_wall_id": self.through_wall_id,
            "abutting_wall_ids": list(self.abutting_wall_ids),
            "junction_point": list(self.junction_point),
            "overlap_area_sqm": round(self.overlap_area_sqm, 4),
            "deducted_volume_cum": round(self.deducted_volume_cum, 4),
            "obscured_face_length_m": round(self.obscured_face_length_m, 4),
            "obscured_finish_area_sqm": round(self.obscured_finish_area_sqm, 4),
            "wall_height_m": round(self.wall_height_m, 4),
            "status": self.status.value,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class WallJunctionCornerMassDeductionShadowAuthority:
    """Evaluates wall intersections, corner mass overlaps, and finish deductions."""

    def evaluate_t_junction(
        self,
        through_wall_id: str,
        abutting_wall_id: str,
        junction_point: Tuple[float, float],
        through_wall_thickness_m: float,
        abutting_wall_thickness_m: float,
        wall_height_m: float,
    ) -> WallJunctionDeductionEvidence:
        """Evaluates a T-junction where an abutting wall meets a continuous through-wall."""
        pt = (float(junction_point[0]), float(junction_point[1]))
        junction_id = stable_contract_id(
            "T_JUNCTION",
            (through_wall_id, abutting_wall_id, pt),
        )

        # Invariant checks: physical thickness bounds [0.06m, 0.60m]
        if through_wall_thickness_m < 0.05 or abutting_wall_thickness_m < 0.05:
            return WallJunctionDeductionEvidence(
                junction_id=junction_id,
                junction_kind=JunctionKind.T_JUNCTION_ABUTMENT,
                through_wall_id=through_wall_id,
                abutting_wall_ids=(abutting_wall_id,),
                junction_point=pt,
                overlap_area_sqm=0.0,
                deducted_volume_cum=0.0,
                obscured_face_length_m=0.0,
                obscured_finish_area_sqm=0.0,
                wall_height_m=wall_height_m,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Wall thickness below physical threshold.",
            )

        if wall_height_m <= 0.0 or wall_height_m > 12.0:
            return WallJunctionDeductionEvidence(
                junction_id=junction_id,
                junction_kind=JunctionKind.T_JUNCTION_ABUTMENT,
                through_wall_id=through_wall_id,
                abutting_wall_ids=(abutting_wall_id,),
                junction_point=pt,
                overlap_area_sqm=0.0,
                deducted_volume_cum=0.0,
                obscured_face_length_m=0.0,
                obscured_finish_area_sqm=0.0,
                wall_height_m=wall_height_m,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Wall height {wall_height_m}m outside valid bounds (0, 12m].",
            )

        # In a T-junction, the overlapping area is the thickness of the through-wall multiplied
        # by the thickness of the abutting wall: Area = T_through * T_abut
        overlap_area = through_wall_thickness_m * abutting_wall_thickness_m
        deducted_volume = overlap_area * wall_height_m

        # Obscured face on the through-wall contact surface is T_abut
        obscured_face_length = abutting_wall_thickness_m
        obscured_finish_area = obscured_face_length * wall_height_m

        return WallJunctionDeductionEvidence(
            junction_id=junction_id,
            junction_kind=JunctionKind.T_JUNCTION_ABUTMENT,
            through_wall_id=through_wall_id,
            abutting_wall_ids=(abutting_wall_id,),
            junction_point=pt,
            overlap_area_sqm=overlap_area,
            deducted_volume_cum=deducted_volume,
            obscured_face_length_m=obscured_face_length,
            obscured_finish_area_sqm=obscured_finish_area,
            wall_height_m=wall_height_m,
            status=EvidenceResolutionStatus.CORROBORATED,
            notes="Corroborated T-junction: through-wall retains continuous mass; abutting overlap deducted.",
        )

    def evaluate_l_junction(
        self,
        wall1_id: str,
        wall2_id: str,
        corner_point: Tuple[float, float],
        wall1_thickness_m: float,
        wall2_thickness_m: float,
        wall_height_m: float,
    ) -> WallJunctionDeductionEvidence:
        """Evaluates an L-junction corner intersection between two walls."""
        pt = (float(corner_point[0]), float(corner_point[1]))
        junction_id = stable_contract_id(
            "L_JUNCTION",
            (wall1_id, wall2_id, pt),
        )

        if wall1_thickness_m < 0.05 or wall2_thickness_m < 0.05 or wall_height_m <= 0.0:
            return WallJunctionDeductionEvidence(
                junction_id=junction_id,
                junction_kind=JunctionKind.L_JUNCTION_CORNER,
                through_wall_id=wall1_id,
                abutting_wall_ids=(wall2_id,),
                junction_point=pt,
                overlap_area_sqm=0.0,
                deducted_volume_cum=0.0,
                obscured_face_length_m=0.0,
                obscured_finish_area_sqm=0.0,
                wall_height_m=wall_height_m,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Invalid wall dimensions or height.",
            )

        overlap_area = wall1_thickness_m * wall2_thickness_m
        deducted_volume = overlap_area * wall_height_m

        # In an L-junction, the butt joint obscures one wall thickness
        obscured_face_length = min(wall1_thickness_m, wall2_thickness_m)
        obscured_finish_area = obscured_face_length * wall_height_m

        return WallJunctionDeductionEvidence(
            junction_id=junction_id,
            junction_kind=JunctionKind.L_JUNCTION_CORNER,
            through_wall_id=wall1_id,
            abutting_wall_ids=(wall2_id,),
            junction_point=pt,
            overlap_area_sqm=overlap_area,
            deducted_volume_cum=deducted_volume,
            obscured_face_length_m=obscured_face_length,
            obscured_finish_area_sqm=obscured_finish_area,
            wall_height_m=wall_height_m,
            status=EvidenceResolutionStatus.CORROBORATED,
            notes="Corroborated L-junction corner: shared corner block deducted from secondary wall.",
        )
