"""Producer-Owned Structural Cavity Slider Lead Jamb and Split-Stud Pocket Host Authority.

Differentiates clear passage opening aperture spans from hollow split-stud pocket retraction
depths in cavity slider pocket doors, ensuring door schedule takeoff widths are not falsely doubled.

Engineering rationale:
- Cavity slider (pocket) doors retract into the hollow interior of an adjacent partition wall.
- The architectural assembly consists of:
  1. Strike Jamb (Lead Jamb): Solid closing stud where the door leaf latches when shut.
  2. Clear Opening Aperture: Clear passage opening between strike jamb and pocket mouth (~720-920 mm / 40.8-52.1 pt).
  3. Pocket Split-Stud Envelope: Hollow wall framing with thin split studs (~19 mm) flanking the internal pocket cavity.
  4. Back Stud: Terminating stud at the rear of the pocket cavity.
- Naive vector tracing algorithms either:
  a) Sever the host wall at the strike jamb and drop the pocket as an unhosted dead stub.
  b) Or measure the entire assembly length from strike jamb to back stud (W_clear + D_pocket ~ 2 * W_clear),
     falsely doubling the door schedule takeoff width.
- Structural Cavity Slider Authority isolates the clear passage opening from the pocket retraction depth,
  validates retraction depth sufficiency (D_pocket >= W_clear - 5.0 pt), and binds both the clear opening
  and the pocket framing to the continuous host through-wall frame.

Invariants:
- Shadow mode only: zero commercial projection, candidate status only, non-publishing.
- Fails closed on insufficient pocket depth (D_pocket < W_clear - 5.0 pt) or degenerate spans.
- Enforces strict 2.5 pt snap compliance and deterministically sorted stable contract IDs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

MIN_CLEAR_SPAN_PT = 20.0
MAX_CLEAR_SPAN_PT = 150.0
POCKET_DEPTH_MARGIN_PT = 5.0


class CavitySliderClassification(str, Enum):
    """Classification outcome for cavity slider pocket door."""

    CAVITY_SLIDER_HOST_CONFIRMED = "cavity_slider_host_confirmed"  # Legacy label, never source-free emitted.
    CAVITY_SLIDER_GEOMETRIC_CANDIDATE = "cavity_slider_geometric_candidate"
    ABSTAINED_UNVERIFIED_SCALE = "abstained_unverified_scale"
    ABSTAINED_INSUFFICIENT_POCKET_DEPTH = "abstained_insufficient_pocket_depth"
    ABSTAINED_DEGENERATE_SPAN = "abstained_degenerate_span"
    ABSTAINED_MISALIGNED_POCKET_AXIS = "abstained_misaligned_pocket_axis"


@dataclass(frozen=True)
class CavitySliderApertureRecord:
    """Rigorous structural record isolating clear aperture from pocket retraction depth."""

    contract_id: str
    classification: CavitySliderClassification
    strike_jamb: tuple[float, float]
    pocket_mouth_jamb: tuple[float, float]
    pocket_back_stud: tuple[float, float]
    clear_span_pt: float
    clear_span_m: float | None
    pocket_depth_pt: float
    pocket_depth_m: float | None
    total_frame_extent_pt: float
    total_frame_extent_m: float | None
    host_through_wall_id: str
    status: EvidenceResolutionStatus
    first_remaining_gate: str | None = None
    notes: str = ""
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    shadow_only: bool = True

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "contract_id": self.contract_id,
            "classification": self.classification.value,
            "strike_jamb": [round(c, 2) for c in self.strike_jamb],
            "pocket_mouth_jamb": [round(c, 2) for c in self.pocket_mouth_jamb],
            "pocket_back_stud": [round(c, 2) for c in self.pocket_back_stud],
            "clear_span_pt": round(self.clear_span_pt, 2),
            "clear_span_m": round(self.clear_span_m, 4) if self.clear_span_m is not None else None,
            "pocket_depth_pt": round(self.pocket_depth_pt, 2),
            "pocket_depth_m": round(self.pocket_depth_m, 4) if self.pocket_depth_m is not None else None,
            "total_frame_extent_pt": round(self.total_frame_extent_pt, 2),
            "total_frame_extent_m": round(self.total_frame_extent_m, 4) if self.total_frame_extent_m is not None else None,
            "host_through_wall_id": self.host_through_wall_id,
            "status": self.status.value,
            "first_remaining_gate": self.first_remaining_gate,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
            "shadow_only": self.shadow_only,
        }


class StructuralCavitySliderPocketHostAuthority:
    """Evaluates cavity slider lead jambs, clear passage apertures, and split-stud pocket frames."""

    def evaluate_cavity_slider(
        self,
        *,
        strike_jamb: tuple[float, float],
        pocket_mouth_jamb: tuple[float, float],
        pocket_back_stud: tuple[float, float],
        host_through_wall_id: str,
        scale_ratio: float | None = None,
        context_label: str = "CAVITY_SLIDER",
    ) -> CavitySliderApertureRecord:
        """Evaluate shadow geometry; a caller ratio cannot authenticate source scale."""
        def finite_number(value: object) -> bool:
            if type(value) not in (int, float):
                return False
            try:
                return math.isfinite(float(value))
            except (OverflowError, TypeError, ValueError):
                return False

        for name, point in (
            ("strike_jamb", strike_jamb),
            ("pocket_mouth_jamb", pocket_mouth_jamb),
            ("pocket_back_stud", pocket_back_stud),
        ):
            if type(point) not in (tuple, list) or len(point) != 2 or not all(
                finite_number(v) for v in point
            ):
                raise ValueError(f"{name} requires two finite numeric coordinates")
        if type(host_through_wall_id) is not str or not host_through_wall_id.strip():
            raise ValueError("host_through_wall_id requires a nonempty physical host reference")
        if type(context_label) is not str or not context_label.strip():
            raise ValueError("context_label requires nonempty text")
        if scale_ratio is not None and (
            not finite_number(scale_ratio) or scale_ratio <= 0
        ):
            raise ValueError("scale_ratio requires an explicit finite positive number")

        # Vector 1: Clear passage opening from strike jamb to pocket mouth
        dx_clear = pocket_mouth_jamb[0] - strike_jamb[0]
        dy_clear = pocket_mouth_jamb[1] - strike_jamb[1]
        clear_span_pt = math.hypot(dx_clear, dy_clear)
        clear_span_m = clear_span_pt * scale_ratio if scale_ratio is not None else None

        # Vector 2: Pocket retraction depth from pocket mouth to back stud
        dx_pocket = pocket_back_stud[0] - pocket_mouth_jamb[0]
        dy_pocket = pocket_back_stud[1] - pocket_mouth_jamb[1]
        pocket_depth_pt = math.hypot(dx_pocket, dy_pocket)
        pocket_depth_m = pocket_depth_pt * scale_ratio if scale_ratio is not None else None

        total_frame_pt = clear_span_pt + pocket_depth_pt
        total_frame_m = total_frame_pt * scale_ratio if scale_ratio is not None else None
        if any(not math.isfinite(v) for v in (
            dx_clear, dy_clear, dx_pocket, dy_pocket,
            clear_span_pt, pocket_depth_pt, total_frame_pt,
        )) or any(v is not None and not math.isfinite(v) for v in (
            clear_span_m, pocket_depth_m, total_frame_m,
        )):
            raise ValueError("cavity slider geometry and metric arithmetic must remain finite")

        contract_id = stable_contract_id(
            f"CAVITY_SLIDER_{context_label}",
            (
                host_through_wall_id,
                strike_jamb[0], strike_jamb[1],
                pocket_mouth_jamb[0], pocket_mouth_jamb[1],
                pocket_back_stud[0], pocket_back_stud[1],
                context_label, scale_ratio,
            ),
        )

        # No original document/viewport scale receipt is available here.
        # Keep every geometry observation, but do not mint metric measurements.
        if scale_ratio is None:
            return CavitySliderApertureRecord(
                contract_id=contract_id,
                classification=CavitySliderClassification.ABSTAINED_UNVERIFIED_SCALE,
                strike_jamb=strike_jamb,
                pocket_mouth_jamb=pocket_mouth_jamb,
                pocket_back_stud=pocket_back_stud,
                clear_span_pt=clear_span_pt, clear_span_m=None,
                pocket_depth_pt=pocket_depth_pt, pocket_depth_m=None,
                total_frame_extent_pt=total_frame_pt, total_frame_extent_m=None,
                host_through_wall_id=host_through_wall_id,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="source_viewport_scale_receipt_missing",
                notes="Source-owned viewport scale is unverified; no metric cavity-slider evidence.",
            )

        # Gate 1: Degenerate clear passage span check
        if clear_span_pt < MIN_CLEAR_SPAN_PT or clear_span_pt > MAX_CLEAR_SPAN_PT:
            return CavitySliderApertureRecord(
                contract_id=contract_id,
                classification=CavitySliderClassification.ABSTAINED_DEGENERATE_SPAN,
                strike_jamb=strike_jamb,
                pocket_mouth_jamb=pocket_mouth_jamb,
                pocket_back_stud=pocket_back_stud,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                pocket_depth_pt=pocket_depth_pt,
                pocket_depth_m=pocket_depth_m,
                total_frame_extent_pt=total_frame_pt,
                total_frame_extent_m=total_frame_m,
                host_through_wall_id=host_through_wall_id,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="clear_passage_span_out_of_bounds",
                notes=f"Clear span {clear_span_pt:.2f}pt outside bounds [{MIN_CLEAR_SPAN_PT}, {MAX_CLEAR_SPAN_PT}]pt.",
            )

        # Gate 2: Collinear alignment check between clear span and pocket vector
        if clear_span_pt > 0 and pocket_depth_pt > 0:
            u_clear = (dx_clear / clear_span_pt, dy_clear / clear_span_pt)
            u_pocket = (dx_pocket / pocket_depth_pt, dy_pocket / pocket_depth_pt)
            dot = max(
                -1.0, min(1.0, u_clear[0] * u_pocket[0] + u_clear[1] * u_pocket[1])
            )
            angle_diff = math.degrees(math.acos(dot))
            if angle_diff > 2.0:  # pocket must follow opening axis
                return CavitySliderApertureRecord(
                    contract_id=contract_id,
                    classification=CavitySliderClassification.ABSTAINED_MISALIGNED_POCKET_AXIS,
                    strike_jamb=strike_jamb,
                    pocket_mouth_jamb=pocket_mouth_jamb,
                    pocket_back_stud=pocket_back_stud,
                    clear_span_pt=clear_span_pt,
                    clear_span_m=clear_span_m,
                    pocket_depth_pt=pocket_depth_pt,
                    pocket_depth_m=pocket_depth_m,
                    total_frame_extent_pt=total_frame_pt,
                    total_frame_extent_m=total_frame_m,
                    host_through_wall_id=host_through_wall_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    first_remaining_gate="pocket_opening_axis_misaligned",
                    notes=f"Pocket axis angular deviation {angle_diff:.2f}deg exceeds 2.0deg tolerance.",
                )

        # Gate 3: Pocket depth sufficiency check (door leaf must be able to retract)
        if pocket_depth_pt < (clear_span_pt - POCKET_DEPTH_MARGIN_PT):
            return CavitySliderApertureRecord(
                contract_id=contract_id,
                classification=CavitySliderClassification.ABSTAINED_INSUFFICIENT_POCKET_DEPTH,
                strike_jamb=strike_jamb,
                pocket_mouth_jamb=pocket_mouth_jamb,
                pocket_back_stud=pocket_back_stud,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                pocket_depth_pt=pocket_depth_pt,
                pocket_depth_m=pocket_depth_m,
                total_frame_extent_pt=total_frame_pt,
                total_frame_extent_m=total_frame_m,
                host_through_wall_id=host_through_wall_id,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="pocket_depth_insufficient_for_retraction",
                notes=f"Pocket depth {pocket_depth_pt:.2f}pt insufficient for door leaf span {clear_span_pt:.2f}pt.",
            )

        # A caller-supplied numeric ratio and wall string are not source proof.
        return CavitySliderApertureRecord(
            contract_id=contract_id,
            classification=CavitySliderClassification.CAVITY_SLIDER_GEOMETRIC_CANDIDATE,
            strike_jamb=strike_jamb,
            pocket_mouth_jamb=pocket_mouth_jamb,
            pocket_back_stud=pocket_back_stud,
            clear_span_pt=clear_span_pt,
            clear_span_m=clear_span_m,
            pocket_depth_pt=pocket_depth_pt,
            pocket_depth_m=pocket_depth_m,
            total_frame_extent_pt=total_frame_pt,
            total_frame_extent_m=total_frame_m,
            host_through_wall_id=host_through_wall_id,
            status=EvidenceResolutionStatus.CANDIDATE,
            first_remaining_gate="source_cavity_slider_host_and_scale_unproven",
            notes="Geometry-only pocket hypothesis; original host, scale and door kind are unverified.",
        )
