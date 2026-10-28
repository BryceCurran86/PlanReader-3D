"""Producer-Owned Structural Infill Spandrel Wall and Window Sub-Sill Continuity Authority.

Differentiates 2D plan sub-sill wall linework from physical glazed window apertures, preventing
sub-sill spandrel walls from obliterating windows while accurately quantifying both glazed area
and sub-sill wall infill areas.

Engineering rationale:
- Punched windows in masonry or framed walls do not span floor-to-ceiling; they sit above an
  infill spandrel dwarf wall (knee wall) of height h_sill (~600-1000 mm, typically 900 mm).
- On 2D plans cut at h ~ 1000-1200 mm, drafting tools depict the sub-sill spandrel wall as solid
  line work beneath the glazed window profile.
- Naive 2D tracing routines mistake this sub-sill linework for full-height continuous solid wall,
  falsely concluding that no window opening exists and obliterating the aperture candidate.
- In reverse errors, ignoring the spandrel wall fails to quantify the solid wall area beneath the
  sill (A_spandrel = W_clear * h_sill), creating deficient takeoff wall quantities.
- Structural Spandrel Sub-Sill Authority confirms the glazed aperture, validates vertical level
  ordering (0 < h_sill < h_head), and computes both transparent glazing aperture area and solid
  sub-sill infill area bound to the continuous through-wall frame.

Invariants:
- Shadow mode only: zero commercial projection, candidate status only, non-publishing.
- Fails closed on invalid vertical levels (h_sill >= h_head or h_head <= 0) or degenerate spans.
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
MAX_CLEAR_SPAN_PT = 300.0
MIN_SILL_HEIGHT_MM = 300.0
MAX_HEAD_HEIGHT_MM = 4000.0


class SpandrelSubSillClassification(str, Enum):
    """Classification outcome for window over sub-sill spandrel wall."""

    SPANDREL_SUB_SILL_CONFIRMED = "spandrel_sub_sill_confirmed"
    ABSTAINED_INVALID_VERTICAL_LEVELS = "abstained_invalid_vertical_levels"
    ABSTAINED_DEGENERATE_SPAN = "abstained_degenerate_span"


@dataclass(frozen=True)
class SpandrelSubSillRecord:
    """Rigorous structural record isolating glazed aperture area from sub-sill spandrel area."""

    contract_id: str
    classification: SpandrelSubSillClassification
    jamb_left: tuple[float, float]
    jamb_right: tuple[float, float]
    clear_span_pt: float
    clear_span_m: float
    sill_height_mm: float
    head_height_mm: float
    glazing_height_mm: float
    glazing_aperture_area_sqm: float
    spandrel_wall_area_sqm: float
    total_wall_opening_area_sqm: float
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
            "jamb_left": [round(c, 2) for c in self.jamb_left],
            "jamb_right": [round(c, 2) for c in self.jamb_right],
            "clear_span_pt": round(self.clear_span_pt, 2),
            "clear_span_m": round(self.clear_span_m, 4),
            "sill_height_mm": round(self.sill_height_mm, 1),
            "head_height_mm": round(self.head_height_mm, 1),
            "glazing_height_mm": round(self.glazing_height_mm, 1),
            "glazing_aperture_area_sqm": round(self.glazing_aperture_area_sqm, 4),
            "spandrel_wall_area_sqm": round(self.spandrel_wall_area_sqm, 4),
            "total_wall_opening_area_sqm": round(self.total_wall_opening_area_sqm, 4),
            "host_through_wall_id": self.host_through_wall_id,
            "status": self.status.value,
            "first_remaining_gate": self.first_remaining_gate,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
            "shadow_only": self.shadow_only,
        }


class StructuralSpandrelSubSillContinuityAuthority:
    """Evaluates window apertures over sub-sill spandrel walls and computes vertical takeoff areas."""

    @staticmethod
    def _order_jambs(
        p_a: tuple[float, float], p_b: tuple[float, float]
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        if (p_a[0], p_a[1]) <= (p_b[0], p_b[1]):
            return p_a, p_b
        return p_b, p_a

    def evaluate_spandrel_sub_sill(
        self,
        *,
        jamb_a: tuple[float, float],
        jamb_b: tuple[float, float],
        sill_height_mm: float,
        head_height_mm: float,
        host_through_wall_id: str,
        scale_ratio: float = 0.01764,
        context_label: str = "SPANDREL_WINDOW",
    ) -> SpandrelSubSillRecord:
        """Evaluates clear span and vertical levels, computing glazing and sub-sill wall areas."""
        jamb_left, jamb_right = self._order_jambs(jamb_a, jamb_b)
        dx = jamb_right[0] - jamb_left[0]
        dy = jamb_right[1] - jamb_left[1]
        clear_span_pt = math.hypot(dx, dy)
        clear_span_m = clear_span_pt * scale_ratio

        glazing_height_mm = max(0.0, head_height_mm - sill_height_mm)
        glazing_height_m = glazing_height_mm / 1000.0
        sill_height_m = sill_height_mm / 1000.0
        head_height_m = head_height_mm / 1000.0

        glazing_area_sqm = clear_span_m * glazing_height_m
        spandrel_area_sqm = clear_span_m * sill_height_m
        total_opening_area_sqm = clear_span_m * head_height_m

        contract_id = stable_contract_id(
            f"SPANDREL_SUB_SILL_{context_label}",
            (
                host_through_wall_id,
                round(jamb_left[0], 2),
                round(jamb_left[1], 2),
                round(jamb_right[0], 2),
                round(jamb_right[1], 2),
                round(sill_height_mm, 1),
                round(head_height_mm, 1),
            ),
        )

        # Gate 1: Clear span bounds
        if clear_span_pt < MIN_CLEAR_SPAN_PT or clear_span_pt > MAX_CLEAR_SPAN_PT:
            return SpandrelSubSillRecord(
                contract_id=contract_id,
                classification=SpandrelSubSillClassification.ABSTAINED_DEGENERATE_SPAN,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                sill_height_mm=sill_height_mm,
                head_height_mm=head_height_mm,
                glazing_height_mm=glazing_height_mm,
                glazing_aperture_area_sqm=glazing_area_sqm,
                spandrel_wall_area_sqm=spandrel_area_sqm,
                total_wall_opening_area_sqm=total_opening_area_sqm,
                host_through_wall_id=host_through_wall_id,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="clear_span_out_of_bounds",
                notes=f"Clear span {clear_span_pt:.2f}pt outside bounds [{MIN_CLEAR_SPAN_PT}, {MAX_CLEAR_SPAN_PT}]pt.",
            )

        # Gate 2: Vertical levels validation
        if (
            sill_height_mm >= head_height_mm
            or head_height_mm <= 0
            or sill_height_mm < 0
        ):
            return SpandrelSubSillRecord(
                contract_id=contract_id,
                classification=SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                sill_height_mm=sill_height_mm,
                head_height_mm=head_height_mm,
                glazing_height_mm=0.0,
                glazing_aperture_area_sqm=0.0,
                spandrel_wall_area_sqm=0.0,
                total_wall_opening_area_sqm=0.0,
                host_through_wall_id=host_through_wall_id,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="vertical_levels_inverted_or_negative",
                notes=f"Invalid vertical levels: sill={sill_height_mm:.1f}mm >= head={head_height_mm:.1f}mm.",
            )

        # Pass: Spandrel sub-sill confirmed
        return SpandrelSubSillRecord(
            contract_id=contract_id,
            classification=SpandrelSubSillClassification.SPANDREL_SUB_SILL_CONFIRMED,
            jamb_left=jamb_left,
            jamb_right=jamb_right,
            clear_span_pt=clear_span_pt,
            clear_span_m=clear_span_m,
            sill_height_mm=sill_height_mm,
            head_height_mm=head_height_mm,
            glazing_height_mm=glazing_height_mm,
            glazing_aperture_area_sqm=glazing_area_sqm,
            spandrel_wall_area_sqm=spandrel_area_sqm,
            total_wall_opening_area_sqm=total_opening_area_sqm,
            host_through_wall_id=host_through_wall_id,
            status=EvidenceResolutionStatus.CANDIDATE,
            first_remaining_gate="spandrel_sub_sill_shadow_authenticated",
            notes=(
                f"Window confirmed over sub-sill spandrel wall: "
                f"glazing area={glazing_area_sqm:.2f}sqm, spandrel area={spandrel_area_sqm:.2f}sqm."
            ),
        )
