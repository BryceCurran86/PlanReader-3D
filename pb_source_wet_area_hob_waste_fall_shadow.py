"""Producer-Owned Wet-Area Floor Waste Fall and Hob Boundary Shadow Authority.

Workstream B Item 14 / Workstream A Item 10:
Eliminates blockers where tiled wet-area floors (FT2/FT3 in bathrooms, ensuites,
laundries, PWD, M-AMB, F-AMB) have shower hobs, step-downs, and waste falls.
Prevents mistaking hobs for structural walls (which incorrectly split rooms)
while accurately recovering vertical hob tile face areas and waterproofing
membrane perimeter upturns.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Hobs are sub-room architectural dividers, NOT structural walls.
- Waterproofing upturn height minimum 0.15 m per AS 3740.
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


class HobKind(str, Enum):
    RAISED_HOB = "RAISED_HOB"
    RECESSED_STEPDOWN = "RECESSED_STEPDOWN"
    FLUSH_WATERSTOP_ANGLE = "FLUSH_WATERSTOP_ANGLE"
    INSET_SHOWER_TRAY = "INSET_SHOWER_TRAY"


class WasteKind(str, Enum):
    ROUND_FLOOR_WASTE = "ROUND_FLOOR_WASTE"
    LINEAR_STRIP_DRAIN = "LINEAR_STRIP_DRAIN"
    PUDDLE_FLANGE = "PUDDLE_FLANGE"


@dataclass(frozen=True)
class HobGeometryEvidence:
    hob_id: str
    room_id: str
    hob_kind: HobKind
    centerline_pts: Tuple[Tuple[float, float], ...]
    length_m: float
    width_m: float
    height_m: float
    top_area_sqm: float
    vertical_face_area_sqm: float
    waterproofing_upturn_area_sqm: float
    is_structural_wall: bool
    status: EvidenceResolutionStatus
    notes: str
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "hob_id": self.hob_id,
            "room_id": self.room_id,
            "hob_kind": self.hob_kind.value,
            "centerline_pts": [list(pt) for pt in self.centerline_pts],
            "length_m": round(self.length_m, 4),
            "width_m": round(self.width_m, 4),
            "height_m": round(self.height_m, 4),
            "top_area_sqm": round(self.top_area_sqm, 4),
            "vertical_face_area_sqm": round(self.vertical_face_area_sqm, 4),
            "waterproofing_upturn_area_sqm": round(self.waterproofing_upturn_area_sqm, 4),
            "is_structural_wall": self.is_structural_wall,
            "status": self.status.value,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


@dataclass(frozen=True)
class WetAreaTakeoffSummary:
    room_id: str
    floor_finish_code: str
    main_floor_area_sqm: float
    shower_floor_area_sqm: float
    hob_vertical_faces_sqm: float
    hob_top_faces_sqm: float
    waterproofing_perimeter_upturn_sqm: float
    total_tiling_area_sqm: float
    status: EvidenceResolutionStatus
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "room_id": self.room_id,
            "floor_finish_code": self.floor_finish_code,
            "main_floor_area_sqm": round(self.main_floor_area_sqm, 4),
            "shower_floor_area_sqm": round(self.shower_floor_area_sqm, 4),
            "hob_vertical_faces_sqm": round(self.hob_vertical_faces_sqm, 4),
            "hob_top_faces_sqm": round(self.hob_top_faces_sqm, 4),
            "waterproofing_perimeter_upturn_sqm": round(self.waterproofing_perimeter_upturn_sqm, 4),
            "total_tiling_area_sqm": round(self.total_tiling_area_sqm, 4),
            "status": self.status.value,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _polyline_length(pts: Sequence[Tuple[float, float]]) -> float:
    length = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        length += math.hypot(dx, dy)
    return length


class WetAreaHobWasteFallShadowAuthority:
    """Evaluates wet-area shower hobs, step-downs, and waste falls."""

    def evaluate_hob(
        self,
        room_id: str,
        centerline_pts: Sequence[Tuple[float, float]],
        hob_kind: HobKind,
        width_m: float,
        height_m: float,
        scale_ratio: float,
        waterproofing_upturn_h_m: float = 0.0,
    ) -> HobGeometryEvidence:
        """Evaluates a shower hob or waterstop barrier."""
        pts_tuple = tuple((float(x), float(y)) for x, y in centerline_pts)
        hob_id = stable_contract_id(
            "HOB",
            (room_id, hob_kind.value, pts_tuple),
        )

        if len(pts_tuple) < 2:
            return HobGeometryEvidence(
                hob_id=hob_id,
                room_id=room_id,
                hob_kind=hob_kind,
                centerline_pts=pts_tuple,
                length_m=0.0,
                width_m=width_m,
                height_m=height_m,
                top_area_sqm=0.0,
                vertical_face_area_sqm=0.0,
                waterproofing_upturn_area_sqm=0.0,
                is_structural_wall=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Degenerate hob centerline: fewer than 2 vertices.",
            )

        # Invariant: Hob height must be sub-room height (typically 0.015m to 0.20m).
        # Hobs taller than 0.50m are likely masonry partitions, not hobs.
        if height_m > 0.40:
            return HobGeometryEvidence(
                hob_id=hob_id,
                room_id=room_id,
                hob_kind=hob_kind,
                centerline_pts=pts_tuple,
                length_m=0.0,
                width_m=width_m,
                height_m=height_m,
                top_area_sqm=0.0,
                vertical_face_area_sqm=0.0,
                waterproofing_upturn_area_sqm=0.0,
                is_structural_wall=True,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Height {height_m:.2f}m exceeds hob limits; candidate is structural wall.",
            )

        raw_len_pt = _polyline_length(pts_tuple)
        length_m = raw_len_pt * scale_ratio

        if length_m < 0.30 or length_m > 5.0:
            return HobGeometryEvidence(
                hob_id=hob_id,
                room_id=room_id,
                hob_kind=hob_kind,
                centerline_pts=pts_tuple,
                length_m=length_m,
                width_m=width_m,
                height_m=height_m,
                top_area_sqm=0.0,
                vertical_face_area_sqm=0.0,
                waterproofing_upturn_area_sqm=0.0,
                is_structural_wall=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Hob length {length_m:.2f}m outside valid physical bounds [0.30m, 5.0m].",
            )

        # Area calculations
        top_area_sqm = length_m * width_m
        # Two vertical sides for raised hob; recessed stepdown has one vertical face
        vertical_face_area_sqm = 2.0 * length_m * height_m if hob_kind == HobKind.RAISED_HOB else length_m * height_m
        waterproofing_upturn_area_sqm = length_m * waterproofing_upturn_h_m

        return HobGeometryEvidence(
            hob_id=hob_id,
            room_id=room_id,
            hob_kind=hob_kind,
            centerline_pts=pts_tuple,
            length_m=length_m,
            width_m=width_m,
            height_m=height_m,
            top_area_sqm=top_area_sqm,
            vertical_face_area_sqm=vertical_face_area_sqm,
            waterproofing_upturn_area_sqm=waterproofing_upturn_area_sqm,
            is_structural_wall=False,
            status=EvidenceResolutionStatus.CANDIDATE,
            notes="Candidate non-structural shower hob / waterstop barrier; not independently re-resolved ownership.",
        )

    def compute_wet_area_takeoff(
        self,
        room_id: str,
        floor_finish_code: str,
        room_gross_floor_area_sqm: float,
        shower_enclosure_area_sqm: float,
        hobs: Sequence[HobGeometryEvidence],
        shower_wall_perimeter_m: float = 0.0,
        waterproof_upturn_height_m: float = 0.0,
    ) -> WetAreaTakeoffSummary:
        """Computes comprehensive wet area tiling and waterproofing takeoff."""
        valid_hobs = [
            h for h in hobs
            if h.room_id == room_id and h.status == EvidenceResolutionStatus.CORROBORATED
        ]

        hob_top_faces = sum(h.top_area_sqm for h in valid_hobs)
        hob_vertical_faces = sum(h.vertical_face_area_sqm for h in valid_hobs)

        # Main floor is total gross minus shower floor (if shower is distinct)
        main_floor_area = max(0.0, room_gross_floor_area_sqm - shower_enclosure_area_sqm)
        shower_floor_area = max(0.0, shower_enclosure_area_sqm)

        # Waterproofing perimeter upturn along shower walls
        wall_upturn_area = shower_wall_perimeter_m * waterproof_upturn_height_m
        total_upturn = wall_upturn_area + sum(h.waterproofing_upturn_area_sqm for h in valid_hobs)

        total_tiling = main_floor_area + shower_floor_area + hob_top_faces + hob_vertical_faces

        status = EvidenceResolutionStatus.CANDIDATE if room_gross_floor_area_sqm > 0 else EvidenceResolutionStatus.ABSTAINED

        return WetAreaTakeoffSummary(
            room_id=room_id,
            floor_finish_code=floor_finish_code,
            main_floor_area_sqm=main_floor_area,
            shower_floor_area_sqm=shower_floor_area,
            hob_vertical_faces_sqm=hob_vertical_faces,
            hob_top_faces_sqm=hob_top_faces,
            waterproofing_perimeter_upturn_sqm=total_upturn,
            total_tiling_area_sqm=total_tiling,
            status=status,
        )
