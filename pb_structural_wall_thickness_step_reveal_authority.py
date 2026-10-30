"""Source-neutral structural wall thickness step and opening reveal shadow evidence.

A geometric thickness step is not a source-authenticated physical opening.
No caller-supplied scale, datum or host string alone authorizes a metric quantity.
This module never publishes to takeoff, issuer or customer consumers.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"
MAX_ALLOWABLE_DATUM_OFFSET_PT = 2.0
MAX_THICKNESS_STEP_PT = 15.0
MIN_CLEAR_SPAN_PT = 20.0
MAX_CLEAR_SPAN_PT = 300.0


class RevealAlignmentDatum(str, Enum):
    EXTERIOR_FLUSH = "exterior_flush"
    INTERIOR_FLUSH = "interior_flush"
    CENTERLINE_ALIGNED = "centerline_aligned"
    ASYMMETRIC_REBATE = "asymmetric_rebate"


class SteppedWallApertureClassification(str, Enum):
    STEPPED_WALL_APERTURE_CONFIRMED = "stepped_wall_aperture_confirmed"  # reserved: source receipt required
    GEOMETRIC_CANDIDATE = "geometric_candidate"
    ABSTAINED_UNVERIFIED_SOURCE = "abstained_unverified_source"
    ABSTAINED_UNALIGNED_DATUM = "abstained_unaligned_datum"
    ABSTAINED_EXCESSIVE_THICKNESS_DISCREPANCY = "abstained_excessive_thickness_discrepancy"
    ABSTAINED_DEGENERATE_SPAN = "abstained_degenerate_span"


@dataclass(frozen=True)
class SteppedWallApertureRecord:
    contract_id: str
    classification: SteppedWallApertureClassification
    jamb_left_datum: tuple[float, float]
    jamb_right_datum: tuple[float, float]
    clear_span_pt: float
    clear_span_m: float | None
    left_wall_thickness_pt: float
    left_wall_thickness_mm: float | None
    right_wall_thickness_pt: float
    right_wall_thickness_mm: float | None
    reveal_depth_pt: float
    reveal_depth_mm: float | None
    centerline_step_offset_pt: float
    datum_alignment: RevealAlignmentDatum | None
    status: EvidenceResolutionStatus
    first_remaining_gate: str | None = None
    notes: str = ""
    # Identity-bound shadow inputs must remain auditable after serialization.
    # They are caller hypotheses, NOT source-verified measurement authority.
    context_label: str = "STEPPED_WALL_OPENING"
    datum_offset_pt: float | None = None
    scale_ratio: float | None = None
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    shadow_only: bool = True

    def __post_init__(self) -> None:
        # Source-neutral records can be constructed or dataclasses.replace'd
        # without invoking the producer; keep the same authority boundary.
        abstained_gates = {
            SteppedWallApertureClassification.ABSTAINED_UNVERIFIED_SOURCE:
                "original_source_scale_or_datum_unverified",
            SteppedWallApertureClassification.ABSTAINED_UNALIGNED_DATUM:
                "datum_faces_divergent",
            SteppedWallApertureClassification.ABSTAINED_EXCESSIVE_THICKNESS_DISCREPANCY:
                "thickness_step_excessive",
            SteppedWallApertureClassification.ABSTAINED_DEGENERATE_SPAN:
                "clear_span_out_of_bounds",
        }
        if (type(self.classification) is not SteppedWallApertureClassification
                or type(self.status) is not EvidenceResolutionStatus
                or type(self.commercial_projection_allowed) is not bool
                or self.commercial_projection_allowed
                or type(self.takeoff_eligible) is not bool
                or self.takeoff_eligible
                or type(self.shadow_only) is not bool
                or not self.shadow_only):
            raise ValueError("source-neutral reveal cannot grant commercial authority")
        if self.classification is SteppedWallApertureClassification.GEOMETRIC_CANDIDATE:
            valid = (self.status is EvidenceResolutionStatus.CANDIDATE
                     and self.first_remaining_gate
                     == "original_source_host_scale_and_reveal_unverified")
        else:
            valid = (self.classification in abstained_gates
                     and self.status is EvidenceResolutionStatus.ABSTAINED
                     and self.first_remaining_gate == abstained_gates.get(self.classification)
                     and all(value is None for value in (
                         self.clear_span_m, self.left_wall_thickness_mm,
                         self.right_wall_thickness_mm, self.reveal_depth_mm,
                     )))
        if not valid:
            raise ValueError("source-neutral reveal classification and source gate conflict")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "contract_id": self.contract_id,
            "classification": self.classification.value,
            # Lossless native and hypothetical metric evidence: rounding here
            # previously made different stable-ID hypotheses indistinguishable.
            "jamb_left_datum": list(self.jamb_left_datum),
            "jamb_right_datum": list(self.jamb_right_datum),
            "clear_span_pt": self.clear_span_pt,
            "clear_span_m": self.clear_span_m,
            "left_wall_thickness_pt": self.left_wall_thickness_pt,
            "left_wall_thickness_mm": self.left_wall_thickness_mm,
            "right_wall_thickness_pt": self.right_wall_thickness_pt,
            "right_wall_thickness_mm": self.right_wall_thickness_mm,
            "reveal_depth_pt": self.reveal_depth_pt,
            "reveal_depth_mm": self.reveal_depth_mm,
            "centerline_step_offset_pt": self.centerline_step_offset_pt,
            "datum_alignment": None if self.datum_alignment is None else self.datum_alignment.value,
            "context_label": self.context_label,
            "datum_offset_pt": self.datum_offset_pt,
            "scale_ratio": self.scale_ratio,
            "status": self.status.value,
            "first_remaining_gate": self.first_remaining_gate,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
            "shadow_only": self.shadow_only,
        }


def _finite_real(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    # Float conversion aliases adjacent integers beyond 2**53; reject them
    # before both geometry and stable-contract identity construction.
    if type(value) is int and abs(value) > 2**53:
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _finite_source_coordinate(value: object) -> bool:
    # Preserve the existing inclusive 2**53 native source-point identity
    # boundary for floats as well as ints. Non-coordinate metric and datum
    # scalars retain their independent finite validation.
    return _finite_real(value) and abs(value) <= 2**53


class StructuralWallThicknessStepRevealAuthority:
    """Source-free, noncommercial geometric candidate and typed abstention producer."""

    @staticmethod
    def _order_datum_jambs(
        p_a: tuple[float, float], p_b: tuple[float, float]
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        return (p_a, p_b) if p_a <= p_b else (p_b, p_a)

    def evaluate_stepped_wall_aperture(
        self,
        *,
        jamb_datum_a: tuple[float, float],
        jamb_datum_b: tuple[float, float],
        left_thickness_pt: float,
        right_thickness_pt: float,
        datum_offset_pt: float | None = None,
        datum_alignment: RevealAlignmentDatum | None = None,
        scale_ratio: float | None = None,
        context_label: str = "STEPPED_WALL_OPENING",
    ) -> SteppedWallApertureRecord:
        """Evaluate only a shadow hypothesis, never a source-confirmed aperture."""
        for name, point in (("jamb_datum_a", jamb_datum_a), ("jamb_datum_b", jamb_datum_b)):
            if not isinstance(point, (tuple, list)) or len(point) != 2:
                raise ValueError(f"{name} requires exactly two coordinates")
            if any(not _finite_source_coordinate(v) for v in point):
                raise ValueError(f"{name} requires finite real coordinates")
        for name, value in (
            ("left_thickness_pt", left_thickness_pt),
            ("right_thickness_pt", right_thickness_pt),
        ):
            if not _finite_real(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if datum_offset_pt is not None and not _finite_real(datum_offset_pt):
            raise ValueError("datum_offset_pt must be finite real")
        if scale_ratio is not None and (not _finite_real(scale_ratio) or scale_ratio <= 0):
            raise ValueError("scale_ratio must be positive and finite")
        if datum_alignment is not None and not isinstance(datum_alignment, RevealAlignmentDatum):
            raise ValueError("datum_alignment must be a typed datum")
        # Context is a source-lineage identity in stable_contract_id, not a
        # display label. Reject padding/control characters rather than
        # manufacturing a second shadow hypothesis for the same context.
        if (type(context_label) is not str or not context_label
                or context_label != context_label.strip()
                or not context_label.isprintable()):
            raise ValueError("context_label must be an exact printable source identity")

        a = (float(jamb_datum_a[0]), float(jamb_datum_a[1]))
        b = (float(jamb_datum_b[0]), float(jamb_datum_b[1]))
        jamb_left, jamb_right = self._order_datum_jambs(a, b)
        clear_span_pt = math.hypot(jamb_right[0] - jamb_left[0],
                                   jamb_right[1] - jamb_left[1])
        reveal_depth_pt = abs(float(left_thickness_pt) - float(right_thickness_pt))
        centerline_step_pt = reveal_depth_pt / 2.0
        if not all(math.isfinite(x) for x in (
            clear_span_pt, reveal_depth_pt, centerline_step_pt
        )):
            raise ValueError("nonfinite geometry")

        # IDs distinguish all source-neutral input hypotheses. Serialization
        # rounding is presentation-only and never used to identify evidence.
        contract_id = stable_contract_id(
            f"STEPPED_WALL_{context_label}",
            (
                *(v.hex() for v in (*jamb_left, *jamb_right)),
                float(left_thickness_pt).hex(),
                float(right_thickness_pt).hex(),
                "missing_datum" if datum_offset_pt is None else float(datum_offset_pt).hex(),
                "missing_alignment" if datum_alignment is None else datum_alignment.value,
                "missing_scale" if scale_ratio is None else float(scale_ratio).hex(),
            ),
        )

        def record(
            classification: SteppedWallApertureClassification,
            status: EvidenceResolutionStatus,
            gate: str,
            notes: str,
            metrics: tuple[float, float, float, float] | None = None,
        ) -> SteppedWallApertureRecord:
            return SteppedWallApertureRecord(
                contract_id=contract_id,
                classification=classification,
                jamb_left_datum=jamb_left,
                jamb_right_datum=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=None if metrics is None else metrics[0],
                left_wall_thickness_pt=float(left_thickness_pt),
                left_wall_thickness_mm=None if metrics is None else metrics[1],
                right_wall_thickness_pt=float(right_thickness_pt),
                right_wall_thickness_mm=None if metrics is None else metrics[2],
                reveal_depth_pt=reveal_depth_pt,
                reveal_depth_mm=None if metrics is None else metrics[3],
                centerline_step_offset_pt=centerline_step_pt,
                datum_alignment=datum_alignment,
                status=status,
                first_remaining_gate=gate,
                notes=notes,
                context_label=context_label,
                datum_offset_pt=None if datum_offset_pt is None else float(datum_offset_pt),
                scale_ratio=None if scale_ratio is None else float(scale_ratio),
            )

        if scale_ratio is None or datum_offset_pt is None or datum_alignment is None:
            return record(
                SteppedWallApertureClassification.ABSTAINED_UNVERIFIED_SOURCE,
                EvidenceResolutionStatus.ABSTAINED,
                "original_source_scale_or_datum_unverified",
                "Missing scale or face-datum receipt; no metric opening or reveal.",
            )

        # Keep the pre-existing geometric tolerances; no default can make
        # a source-free aperture confirmed or commercially publishable.
        if clear_span_pt < MIN_CLEAR_SPAN_PT or clear_span_pt > MAX_CLEAR_SPAN_PT:
            return record(
                SteppedWallApertureClassification.ABSTAINED_DEGENERATE_SPAN,
                EvidenceResolutionStatus.ABSTAINED,
                "clear_span_out_of_bounds",
                "Geometric clear span outside existing bounds.",
            )
        if abs(datum_offset_pt) > MAX_ALLOWABLE_DATUM_OFFSET_PT:
            return record(
                SteppedWallApertureClassification.ABSTAINED_UNALIGNED_DATUM,
                EvidenceResolutionStatus.ABSTAINED,
                "datum_faces_divergent",
                "Datum faces diverge beyond existing tolerance.",
            )
        if reveal_depth_pt > MAX_THICKNESS_STEP_PT:
            return record(
                SteppedWallApertureClassification.ABSTAINED_EXCESSIVE_THICKNESS_DISCREPANCY,
                EvidenceResolutionStatus.ABSTAINED,
                "thickness_step_excessive",
                "Wall thickness step exceeds existing limit.",
            )

        metrics = (
            clear_span_pt * scale_ratio,
            float(left_thickness_pt) * scale_ratio * 1000.0,
            float(right_thickness_pt) * scale_ratio * 1000.0,
            reveal_depth_pt * scale_ratio * 1000.0,
        )
        if not all(math.isfinite(v) for v in metrics):
            raise ValueError("nonfinite hypothetical metric conversion")
        source_lengths = (
            clear_span_pt, float(left_thickness_pt),
            float(right_thickness_pt), reveal_depth_pt,
        )
        if any(metric == 0.0 and source > 0.0
               for metric, source in zip(metrics, source_lengths)):
            raise ValueError("hypothetical metric conversion underflow")
        return record(
            SteppedWallApertureClassification.GEOMETRIC_CANDIDATE,
            EvidenceResolutionStatus.CANDIDATE,
            "original_source_host_scale_and_reveal_unverified",
            "Unverified geometric hypothesis only; NOT a source-confirmed opening.",
            metrics,
        )
