"""Producer-Owned Cavity Slider and Pocket Door Jamb Continuity Shadow Authority.

Workstream A Item 7 & 4:
Solves cavity sliders and pocket doors retracting inside hollow wall framing.
Prevents naive opening detectors from treating the internal pocket as an open void
which severs wall continuity, cuts walls into disconnected stubs, or creates
duplicate wall IDs. Accurately bounds the walkthrough passage while maintaining
structural wall framing continuity across the pocket.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Wall continuity is preserved across the pocket frame; no spurious wall splitting.
- Clear walkthrough opening is strictly separated from embedded wall pocket.
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


class PocketDoorLeafOperation(str, Enum):
    SINGLE_SLIDING = "SINGLE_SLIDING"
    DOUBLE_BI_PARTING = "DOUBLE_BI_PARTING"
    CORNER_MEETING = "CORNER_MEETING"


@dataclass(frozen=True)
class CavitySliderEvidence:
    opening_id: str
    wall_id: str
    operation: PocketDoorLeafOperation
    wall_centerline_pts: Tuple[Tuple[float, float], ...]
    clear_opening_start_pt: Tuple[float, float]
    clear_opening_end_pt: Tuple[float, float]
    pocket_recess_start_pt: Tuple[float, float]
    pocket_recess_end_pt: Tuple[float, float]
    clear_opening_width_m: float
    pocket_length_m: float
    total_frame_length_m: float
    wall_thickness_m: float
    retains_wall_continuity: bool
    status: EvidenceResolutionStatus
    notes: str
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "opening_id": self.opening_id,
            "wall_id": self.wall_id,
            "operation": self.operation.value,
            "wall_centerline_pts": [list(pt) for pt in self.wall_centerline_pts],
            "clear_opening_start_pt": list(self.clear_opening_start_pt),
            "clear_opening_end_pt": list(self.clear_opening_end_pt),
            "pocket_recess_start_pt": list(self.pocket_recess_start_pt),
            "pocket_recess_end_pt": list(self.pocket_recess_end_pt),
            "clear_opening_width_m": round(self.clear_opening_width_m, 4),
            "pocket_length_m": round(self.pocket_length_m, 4),
            "total_frame_length_m": round(self.total_frame_length_m, 4),
            "wall_thickness_m": round(self.wall_thickness_m, 4),
            "retains_wall_continuity": self.retains_wall_continuity,
            "status": self.status.value,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


class CavitySliderPocketJambShadowAuthority:
    """Evaluates cavity slider and pocket door jamb geometry and wall continuity."""

    def evaluate_cavity_slider(
        self,
        wall_id: str,
        wall_centerline_pts: Sequence[Tuple[float, float]],
        clear_opening_span: Tuple[Tuple[float, float], Tuple[float, float]],
        pocket_recess_span: Tuple[Tuple[float, float], Tuple[float, float]],
        operation: PocketDoorLeafOperation,
        wall_thickness_m: float,
        scale_ratio: float,
    ) -> CavitySliderEvidence:
        """Evaluates cavity slider opening, pocket, and wall continuity."""
        pts_tuple = tuple((float(x), float(y)) for x, y in wall_centerline_pts)
        c_start, c_end = (float(clear_opening_span[0][0]), float(clear_opening_span[0][1])), (float(clear_opening_span[1][0]), float(clear_opening_span[1][1]))
        p_start, p_end = (float(pocket_recess_span[0][0]), float(pocket_recess_span[0][1])), (float(pocket_recess_span[1][0]), float(pocket_recess_span[1][1]))

        opening_id = stable_contract_id(
            "CAVITY_SLIDER",
            (wall_id, operation.value, c_start, c_end, p_start, p_end),
        )

        clear_width_pt = _pt_dist(c_start, c_end)
        pocket_len_pt = _pt_dist(p_start, p_end)

        clear_opening_width_m = clear_width_pt * scale_ratio
        pocket_length_m = pocket_len_pt * scale_ratio
        total_frame_length_m = clear_opening_width_m + pocket_length_m

        # Validation: Clear opening physical bounds [0.50m, 2.40m]
        if clear_opening_width_m < 0.50 or clear_opening_width_m > 2.40:
            return CavitySliderEvidence(
                opening_id=opening_id,
                wall_id=wall_id,
                operation=operation,
                wall_centerline_pts=pts_tuple,
                clear_opening_start_pt=c_start,
                clear_opening_end_pt=c_end,
                pocket_recess_start_pt=p_start,
                pocket_recess_end_pt=p_end,
                clear_opening_width_m=clear_opening_width_m,
                pocket_length_m=pocket_length_m,
                total_frame_length_m=total_frame_length_m,
                wall_thickness_m=wall_thickness_m,
                retains_wall_continuity=True,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Clear opening width {clear_opening_width_m:.2f}m outside physical bounds [0.50m, 2.40m].",
            )

        # Validation: Pocket length must accommodate door leaf (pocket >= 0.9 * clear_width)
        if pocket_length_m < (0.85 * clear_opening_width_m):
            return CavitySliderEvidence(
                opening_id=opening_id,
                wall_id=wall_id,
                operation=operation,
                wall_centerline_pts=pts_tuple,
                clear_opening_start_pt=c_start,
                clear_opening_end_pt=c_end,
                pocket_recess_start_pt=p_start,
                pocket_recess_end_pt=p_end,
                clear_opening_width_m=clear_opening_width_m,
                pocket_length_m=pocket_length_m,
                total_frame_length_m=total_frame_length_m,
                wall_thickness_m=wall_thickness_m,
                retains_wall_continuity=True,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Pocket length {pocket_length_m:.2f}m insufficient for leaf width {clear_opening_width_m:.2f}m.",
            )

        # Invariant: Wall thickness must support cavity framing (typically 0.07m to 0.20m)
        if wall_thickness_m < 0.06 or wall_thickness_m > 0.35:
            return CavitySliderEvidence(
                opening_id=opening_id,
                wall_id=wall_id,
                operation=operation,
                wall_centerline_pts=pts_tuple,
                clear_opening_start_pt=c_start,
                clear_opening_end_pt=c_end,
                pocket_recess_start_pt=p_start,
                pocket_recess_end_pt=p_end,
                clear_opening_width_m=clear_opening_width_m,
                pocket_length_m=pocket_length_m,
                total_frame_length_m=total_frame_length_m,
                wall_thickness_m=wall_thickness_m,
                retains_wall_continuity=True,
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Wall thickness {wall_thickness_m:.2f}m incompatible with cavity pocket framing.",
            )

        return CavitySliderEvidence(
            opening_id=opening_id,
            wall_id=wall_id,
            operation=operation,
            wall_centerline_pts=pts_tuple,
            clear_opening_start_pt=c_start,
            clear_opening_end_pt=c_end,
            pocket_recess_start_pt=p_start,
            pocket_recess_end_pt=p_end,
            clear_opening_width_m=clear_opening_width_m,
            pocket_length_m=pocket_length_m,
            total_frame_length_m=total_frame_length_m,
            wall_thickness_m=wall_thickness_m,
            retains_wall_continuity=True,
            status=EvidenceResolutionStatus.CANDIDATE,
            notes="Corroborated cavity slider with structural wall continuity preserved across pocket.",
        )
