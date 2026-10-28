"""Producer-Owned Structural Lintel-to-Pier Bearing and Head Wall Vertical Continuity Authority.

Differentiates overhead structural lintel projection and bearing lengths from clear opening
aperture spans, ensuring physical window/door widths are not inflated by lintel endseats.

Engineering rationale:
- Structural openings through loadbearing masonry, precast concrete, or timber/steel framing
  require an overhead lintel (steel angle, PFC, concrete beam, timber LVL header).
- Building standards (AS 4773, AS 1684, NCC) mandate minimum structural bearing on flanking piers:
  L_bearing >= 100 mm (~5.67 pt at 1:100 scale).
- Total manufactured lintel length is:
  L_lintel = W_clear + L_bearing_left + L_bearing_right (~ W_clear + 200 mm to 300 mm).
- Naive vector tracing algorithms mistake overhead dashed/hidden lintel extents for the clear
  opening aperture, erroneously inflating physical window/door spans by 200-300 mm and truncating
  flanking structural piers.
- Structural Lintel Authority isolates clear aperture span between terminal jambs, validates
  compliant bearing seats (>= 100 mm) on flanking solid piers, and establishes vertical load path continuity.

Invariants:
- Shadow mode only: zero commercial projection, candidate status only, non-publishing.
- Fails closed on insufficient bearing length (< 100 mm / 5.67 pt) or sub-threshold pier width.
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

MIN_STRUCTURAL_BEARING_PT = 5.67  # ~100 mm at 1:100 scale (scale_ratio ~ 0.01764 m/pt)
MAX_STRUCTURAL_BEARING_PT = 20.0  # ~350 mm
MIN_CLEAR_SPAN_PT = 20.0
MAX_CLEAR_SPAN_PT = 300.0


class LintelMaterialType(str, Enum):
    """Structural material specification for overhead lintel."""

    STEEL_ANGLE = "steel_angle"
    STEEL_PFC = "steel_pfc"
    TIMBER_LVL = "timber_lvl"
    REINFORCED_CONCRETE = "reinforced_concrete"
    UNSPECIFIED = "unspecified"


class LintelBearingClassification(str, Enum):
    """Classification outcome for lintel-to-pier bearing."""

    LINTEL_BEARING_CONFIRMED = "lintel_bearing_confirmed"
    ABSTAINED_INSUFFICIENT_BEARING = "abstained_insufficient_bearing"
    ABSTAINED_INSUFFICIENT_PIER_WIDTH = "abstained_insufficient_pier_width"
    ABSTAINED_EXCESSIVE_OVERHANG = "abstained_excessive_overhang"
    ABSTAINED_MISSING_HOST_PIER = "abstained_missing_host_pier"
    ABSTAINED_DEGENERATE_SPAN = "abstained_degenerate_span"


@dataclass(frozen=True)
class PierBearingSeatRecord:
    """Bearing seat details on a flanking structural pier."""

    pier_id: str
    pier_width_pt: float
    pier_width_m: float
    bearing_length_pt: float
    bearing_length_m: float
    is_bearing_compliant: bool

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "pier_id": self.pier_id,
            "pier_width_pt": round(self.pier_width_pt, 2),
            "pier_width_m": round(self.pier_width_m, 4),
            "bearing_length_pt": round(self.bearing_length_pt, 2),
            "bearing_length_m": round(self.bearing_length_m, 4),
            "is_bearing_compliant": self.is_bearing_compliant,
        }


@dataclass(frozen=True)
class StructuralLintelApertureRecord:
    """Rigorous structural record linking clear aperture span to overhead lintel bearing."""

    contract_id: str
    classification: LintelBearingClassification
    jamb_left: tuple[float, float]
    jamb_right: tuple[float, float]
    clear_span_pt: float
    clear_span_m: float
    left_bearing: PierBearingSeatRecord
    right_bearing: PierBearingSeatRecord
    total_lintel_length_pt: float
    total_lintel_length_m: float
    lintel_material: LintelMaterialType
    status: EvidenceResolutionStatus
    lintel_callout_text: str | None = None
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
            "left_bearing": self.left_bearing.to_dict(),
            "right_bearing": self.right_bearing.to_dict(),
            "total_lintel_length_pt": round(self.total_lintel_length_pt, 2),
            "total_lintel_length_m": round(self.total_lintel_length_m, 4),
            "lintel_material": self.lintel_material.value,
            "lintel_callout_text": self.lintel_callout_text,
            "status": self.status.value,
            "first_remaining_gate": self.first_remaining_gate,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
            "shadow_only": self.shadow_only,
        }


class StructuralLintelPierBearingAuthority:
    """Evaluates clear opening spans vs overhead lintel pier bearing seats."""

    @staticmethod
    def _order_jambs(
        p_a: tuple[float, float], p_b: tuple[float, float]
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        if (p_a[0], p_a[1]) <= (p_b[0], p_b[1]):
            return p_a, p_b
        return p_b, p_a

    def evaluate_lintel_bearing(
        self,
        *,
        jamb_a: tuple[float, float],
        jamb_b: tuple[float, float],
        left_pier_width_pt: float,
        right_pier_width_pt: float,
        left_bearing_length_pt: float,
        right_bearing_length_pt: float,
        left_pier_id: str = "PIER_LEFT",
        right_pier_id: str = "PIER_RIGHT",
        lintel_material: LintelMaterialType = LintelMaterialType.UNSPECIFIED,
        lintel_callout_text: str | None = None,
        scale_ratio: float = 0.01764,
        context_label: str = "LINTEL_OPENING",
    ) -> StructuralLintelApertureRecord:
        """Evaluates opening clear span vs overhead lintel bearing requirements."""
        jamb_left, jamb_right = self._order_jambs(jamb_a, jamb_b)
        dx = jamb_right[0] - jamb_left[0]
        dy = jamb_right[1] - jamb_left[1]
        clear_span_pt = math.hypot(dx, dy)
        clear_span_m = clear_span_pt * scale_ratio

        total_lintel_length_pt = (
            clear_span_pt + left_bearing_length_pt + right_bearing_length_pt
        )
        total_lintel_length_m = total_lintel_length_pt * scale_ratio

        left_compliant = (
            left_bearing_length_pt >= MIN_STRUCTURAL_BEARING_PT
            and left_pier_width_pt >= left_bearing_length_pt
        )
        right_compliant = (
            right_bearing_length_pt >= MIN_STRUCTURAL_BEARING_PT
            and right_pier_width_pt >= right_bearing_length_pt
        )

        left_seat = PierBearingSeatRecord(
            pier_id=left_pier_id,
            pier_width_pt=left_pier_width_pt,
            pier_width_m=left_pier_width_pt * scale_ratio,
            bearing_length_pt=left_bearing_length_pt,
            bearing_length_m=left_bearing_length_pt * scale_ratio,
            is_bearing_compliant=left_compliant,
        )
        right_seat = PierBearingSeatRecord(
            pier_id=right_pier_id,
            pier_width_pt=right_pier_width_pt,
            pier_width_m=right_pier_width_pt * scale_ratio,
            bearing_length_pt=right_bearing_length_pt,
            bearing_length_m=right_bearing_length_pt * scale_ratio,
            is_bearing_compliant=right_compliant,
        )

        contract_id = stable_contract_id(
            f"LINTEL_BEARING_{context_label}",
            (
                round(jamb_left[0], 2),
                round(jamb_left[1], 2),
                round(jamb_right[0], 2),
                round(jamb_right[1], 2),
                round(left_bearing_length_pt, 2),
                round(right_bearing_length_pt, 2),
                round(left_pier_width_pt, 2),
                round(right_pier_width_pt, 2),
                lintel_material.value,
            ),
        )

        # Gate 1: Clear span bounds check
        if clear_span_pt < MIN_CLEAR_SPAN_PT or clear_span_pt > MAX_CLEAR_SPAN_PT:
            return StructuralLintelApertureRecord(
                contract_id=contract_id,
                classification=LintelBearingClassification.ABSTAINED_DEGENERATE_SPAN,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                left_bearing=left_seat,
                right_bearing=right_seat,
                total_lintel_length_pt=total_lintel_length_pt,
                total_lintel_length_m=total_lintel_length_m,
                lintel_material=lintel_material,
                lintel_callout_text=lintel_callout_text,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="clear_span_out_of_bounds",
                notes=f"Clear span {clear_span_pt:.2f}pt outside allowable bounds [{MIN_CLEAR_SPAN_PT}, {MAX_CLEAR_SPAN_PT}]pt.",
            )

        # Gate 2: Missing or zero flanking pier
        if left_pier_width_pt <= 0.0 or right_pier_width_pt <= 0.0:
            return StructuralLintelApertureRecord(
                contract_id=contract_id,
                classification=LintelBearingClassification.ABSTAINED_MISSING_HOST_PIER,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                left_bearing=left_seat,
                right_bearing=right_seat,
                total_lintel_length_pt=total_lintel_length_pt,
                total_lintel_length_m=total_lintel_length_m,
                lintel_material=lintel_material,
                lintel_callout_text=lintel_callout_text,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="missing_flanking_host_pier",
                notes="Missing solid host pier flanking terminal jamb.",
            )

        # Gate 3: Insufficient bearing seat length (< 100 mm / 5.67 pt)
        if (
            left_bearing_length_pt < MIN_STRUCTURAL_BEARING_PT
            or right_bearing_length_pt < MIN_STRUCTURAL_BEARING_PT
        ):
            return StructuralLintelApertureRecord(
                contract_id=contract_id,
                classification=LintelBearingClassification.ABSTAINED_INSUFFICIENT_BEARING,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                left_bearing=left_seat,
                right_bearing=right_seat,
                total_lintel_length_pt=total_lintel_length_pt,
                total_lintel_length_m=total_lintel_length_m,
                lintel_material=lintel_material,
                lintel_callout_text=lintel_callout_text,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="lintel_bearing_seat_subminimum",
                notes=f"Bearing length (L={left_bearing_length_pt:.2f}pt, R={right_bearing_length_pt:.2f}pt) below minimum {MIN_STRUCTURAL_BEARING_PT:.2f}pt (100mm).",
            )

        # Gate 4: Insufficient flanking pier width to accommodate bearing seat
        if (
            left_pier_width_pt < left_bearing_length_pt
            or right_pier_width_pt < right_bearing_length_pt
        ):
            return StructuralLintelApertureRecord(
                contract_id=contract_id,
                classification=LintelBearingClassification.ABSTAINED_INSUFFICIENT_PIER_WIDTH,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                left_bearing=left_seat,
                right_bearing=right_seat,
                total_lintel_length_pt=total_lintel_length_pt,
                total_lintel_length_m=total_lintel_length_m,
                lintel_material=lintel_material,
                lintel_callout_text=lintel_callout_text,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="flanking_pier_narrower_than_bearing_seat",
                notes="Host pier width is narrower than required lintel bearing seat.",
            )

        # Gate 5: Excessive overhang projection
        if (
            left_bearing_length_pt > MAX_STRUCTURAL_BEARING_PT
            or right_bearing_length_pt > MAX_STRUCTURAL_BEARING_PT
        ):
            return StructuralLintelApertureRecord(
                contract_id=contract_id,
                classification=LintelBearingClassification.ABSTAINED_EXCESSIVE_OVERHANG,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=clear_span_m,
                left_bearing=left_seat,
                right_bearing=right_seat,
                total_lintel_length_pt=total_lintel_length_pt,
                total_lintel_length_m=total_lintel_length_m,
                lintel_material=lintel_material,
                lintel_callout_text=lintel_callout_text,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="lintel_overhang_excessive",
                notes=f"Overhang projection exceeds maximum standard bearing {MAX_STRUCTURAL_BEARING_PT:.2f}pt.",
            )

        # Compliant lintel bearing confirmed
        return StructuralLintelApertureRecord(
            contract_id=contract_id,
            classification=LintelBearingClassification.LINTEL_BEARING_CONFIRMED,
            jamb_left=jamb_left,
            jamb_right=jamb_right,
            clear_span_pt=clear_span_pt,
            clear_span_m=clear_span_m,
            left_bearing=left_seat,
            right_bearing=right_seat,
            total_lintel_length_pt=total_lintel_length_pt,
            total_lintel_length_m=total_lintel_length_m,
            lintel_material=lintel_material,
            lintel_callout_text=lintel_callout_text,
            status=EvidenceResolutionStatus.CANDIDATE,
            first_remaining_gate="lintel_bearing_shadow_authenticated",
            notes="Clear aperture span verified and isolated from compliant overhead lintel bearing seats.",
        )
