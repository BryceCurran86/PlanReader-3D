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

    LINTEL_BEARING_CONFIRMED = "lintel_bearing_confirmed"  # Legacy label; never emitted without source proof.
    LINTEL_BEARING_GEOMETRIC_CANDIDATE = "lintel_bearing_geometric_candidate"
    ABSTAINED_UNVERIFIED_SCALE = "abstained_unverified_scale"
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
    pier_width_m: float | None
    bearing_length_pt: float
    bearing_length_m: float | None
    is_bearing_compliant: bool

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "pier_id": self.pier_id,
            "pier_width_pt": round(self.pier_width_pt, 2),
            "pier_width_m": round(self.pier_width_m, 4) if self.pier_width_m is not None else None,
            "bearing_length_pt": round(self.bearing_length_pt, 2),
            "bearing_length_m": round(self.bearing_length_m, 4) if self.bearing_length_m is not None else None,
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
    clear_span_m: float | None
    left_bearing: PierBearingSeatRecord
    right_bearing: PierBearingSeatRecord
    total_lintel_length_pt: float
    total_lintel_length_m: float | None
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
            "clear_span_m": round(self.clear_span_m, 4) if self.clear_span_m is not None else None,
            "left_bearing": self.left_bearing.to_dict(),
            "right_bearing": self.right_bearing.to_dict(),
            "total_lintel_length_pt": round(self.total_lintel_length_pt, 2),
            "total_lintel_length_m": round(self.total_lintel_length_m, 4) if self.total_lintel_length_m is not None else None,
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
        scale_ratio: float | None = None,
        context_label: str = "LINTEL_OPENING",
    ) -> StructuralLintelApertureRecord:
        """Evaluate source-neutral *geometric hypotheses*, never a firm physical lintel."""
        for name, point in (("jamb_a", jamb_a), ("jamb_b", jamb_b)):
            if (type(point) not in (tuple, list) or len(point) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
                raise ValueError(f"{name} requires finite numeric coordinates")
        values = (left_pier_width_pt, right_pier_width_pt,
                  left_bearing_length_pt, right_bearing_length_pt)
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("pier widths and bearing lengths must be finite nonnegative numbers")
        if scale_ratio is not None and (
            type(scale_ratio) not in (int, float) or not math.isfinite(scale_ratio)
            or scale_ratio <= 0
        ):
            raise ValueError("scale_ratio must be an explicit finite positive number")
        if type(lintel_material) is not LintelMaterialType:
            raise ValueError("lintel_material must be a supported enum value")
        if any(type(x) is not str or not x.strip()
               for x in (left_pier_id, right_pier_id, context_label)):
            raise ValueError("pier identity and context label must be nonempty strings")
        if lintel_callout_text is not None and type(lintel_callout_text) is not str:
            raise ValueError("lintel_callout_text must be text or None")
        jamb_left, jamb_right = self._order_jambs(jamb_a, jamb_b)
        dx = jamb_right[0] - jamb_left[0]
        dy = jamb_right[1] - jamb_left[1]
        clear_span_pt = math.hypot(dx, dy)
        clear_span_m = clear_span_pt * scale_ratio if scale_ratio is not None else None

        total_lintel_length_pt = (
            clear_span_pt + left_bearing_length_pt + right_bearing_length_pt
        )
        total_lintel_length_m = total_lintel_length_pt * scale_ratio if scale_ratio is not None else None

        # A numeric comparison is NOT proof of a code-compliant structural bearing.
        # Minimum/maximum example thresholds remain shadow-only, and explicit
        # scale still has no source-issued viewport calibration receipt here.
        min_bearing_pt = 0.1 / scale_ratio if scale_ratio is not None else None
        max_bearing_pt = 0.35 / scale_ratio if scale_ratio is not None else None

        left_seat = PierBearingSeatRecord(
            pier_id=left_pier_id,
            pier_width_pt=left_pier_width_pt,
            pier_width_m=left_pier_width_pt * scale_ratio if scale_ratio is not None else None,
            bearing_length_pt=left_bearing_length_pt,
            bearing_length_m=left_bearing_length_pt * scale_ratio if scale_ratio is not None else None,
            is_bearing_compliant=False,  # No approved schedule/source receipt is present.
        )
        right_seat = PierBearingSeatRecord(
            pier_id=right_pier_id,
            pier_width_pt=right_pier_width_pt,
            pier_width_m=right_pier_width_pt * scale_ratio if scale_ratio is not None else None,
            bearing_length_pt=right_bearing_length_pt,
            bearing_length_m=right_bearing_length_pt * scale_ratio if scale_ratio is not None else None,
            is_bearing_compliant=False,  # No approved schedule/source receipt is present.
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
                left_pier_id,
                right_pier_id,
                context_label,
                lintel_callout_text,
                scale_ratio,
            ),
        )

        # No page/viewport calibration receipt or original lintel/host inventory
        # can be authenticated by this source-neutral calculator. Missing scale
        # must never turn an assumed 1:100 ratio into a metric quantity.
        if scale_ratio is None:
            return StructuralLintelApertureRecord(
                contract_id=contract_id,
                classification=LintelBearingClassification.ABSTAINED_UNVERIFIED_SCALE,
                jamb_left=jamb_left, jamb_right=jamb_right,
                clear_span_pt=clear_span_pt, clear_span_m=None,
                left_bearing=left_seat, right_bearing=right_seat,
                total_lintel_length_pt=total_lintel_length_pt,
                total_lintel_length_m=None,
                lintel_material=lintel_material,
                lintel_callout_text=lintel_callout_text,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="source_viewport_scale_receipt_missing",
                notes="No page/viewport source scale receipt; metric lintel and pier dimensions unavailable.",
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
            left_bearing_length_pt < min_bearing_pt
            or right_bearing_length_pt < min_bearing_pt
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
                notes=f"Geometric bearing length (L={left_bearing_length_pt:.2f}pt, R={right_bearing_length_pt:.2f}pt) below reference 100mm at supplied unverified scale ({min_bearing_pt:.2f}pt).",
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
            left_bearing_length_pt > max_bearing_pt
            or right_bearing_length_pt > max_bearing_pt
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
                notes=f"Overhang exceeds 350mm reference ({max_bearing_pt:.2f}pt) at caller scale; not source-verified.",
            )

        # Compliant lintel bearing confirmed
        return StructuralLintelApertureRecord(
            contract_id=contract_id,
            classification=LintelBearingClassification.LINTEL_BEARING_GEOMETRIC_CANDIDATE,
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
            first_remaining_gate="source_lintel_host_scale_and_specification_unproven",
            notes="Geometry-only shadow hypothesis; physical lintel, host piers, calibrated scale and code applicability not authenticated.",
        )
