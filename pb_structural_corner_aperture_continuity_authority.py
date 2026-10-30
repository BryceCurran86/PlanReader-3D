"""Source-neutral two-leg corner-aperture shadow evidence.

This producer only evaluates geometry. It cannot authenticate an opening,
physical host, corner post, frame, or measurement scale; it never publishes
commercial quantities. Missing or conflicting evidence abstains, preserving
the existing 15–300 pt leg, 75–105 degree angle and 15 pt post bounds.
The separate wall-topology snap limit remains unchanged.
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

MIN_LEG_SPAN_PT = 15.0
MAX_LEG_SPAN_PT = 300.0
MIN_CORNER_ANGLE_DEG = 75.0
MAX_CORNER_ANGLE_DEG = 105.0
MAX_CORNER_POST_DIM_PT = 15.0


class CornerPostCondition(str, Enum):
    """Condition of the corner vertex."""

    POSTLESS_BUTT_JOINT = "postless_butt_joint"
    STRUCTURAL_CORNER_POST = "structural_corner_post"
    UNRESOLVED_CORNER_CONDITION = "unresolved_corner_condition"


class CornerApertureClassification(str, Enum):
    """Classification outcome for a corner aperture candidate."""

    CORNER_APERTURE_CONFIRMED = "corner_aperture_confirmed"  # reserved for original-source authority
    GEOMETRIC_CANDIDATE = "geometric_candidate"
    ABSTAINED_UNVERIFIED_SOURCE = "abstained_unverified_source"
    ABSTAINED_NON_ORTHOGONAL_ANGLE = "abstained_non_orthogonal_angle"
    ABSTAINED_DEGENERATE_LEG = "abstained_degenerate_leg"
    ABSTAINED_NON_INTERSECTING_AXES = "abstained_non_intersecting_axes"
    ABSTAINED_EXCESSIVE_POST_DIMENSION = "abstained_excessive_post_dimension"


@dataclass(frozen=True)
class CornerOpeningLegRecord:
    """Parameters for an individual leg of a corner opening."""

    leg_id: str
    terminal_jamb: tuple[float, float]
    corner_vertex: tuple[float, float]
    axis_vector: tuple[float, float]
    leg_span_pt: float
    leg_span_m: float | None
    host_wall_id: str

    def __post_init__(self) -> None:
        # Public frozen records can be directly constructed or replaced.
        # Keep their numeric shadow evidence physical before serialization.
        for point in (self.terminal_jamb, self.corner_vertex, self.axis_vector):
            if (type(point) is not tuple or len(point) != 2
                    or any(not _finite_real(v) for v in point)):
                raise ValueError("corner leg numeric evidence must be finite and physical")
        if (any(not _finite_source_coordinate(v) for v in
                (*self.terminal_jamb, *self.corner_vertex))
                or any(abs(v) > 1.0 for v in self.axis_vector)
                or not _finite_real(self.leg_span_pt)
                or self.leg_span_pt < 0
                or (self.leg_span_m is not None and
                    (not _finite_real(self.leg_span_m) or self.leg_span_m <= 0))):
            raise ValueError("corner leg numeric evidence must be finite and physical")
        # Direct dataclass replacement cannot substitute an unrelated wall
        # direction or span. A genuinely degenerate source leg has zero axis
        # and stays a typed abstention at the parent record, never a host.
        dx = self.terminal_jamb[0] - self.corner_vertex[0]
        dy = self.terminal_jamb[1] - self.corner_vertex[1]
        span = math.hypot(dx, dy)
        if (not math.isfinite(span)
                or not math.isclose(self.leg_span_pt, span,
                                    rel_tol=1e-12, abs_tol=1e-9)):
            raise ValueError("corner leg numeric evidence conflicts with geometry")
        if span == 0.0:
            if self.axis_vector != (0.0, 0.0):
                raise ValueError("corner leg axis conflicts with degenerate geometry")
        elif (not math.isclose(math.hypot(*self.axis_vector), 1.0,
                               rel_tol=0.0, abs_tol=1e-12)
              or not math.isclose(self.axis_vector[0], dx / span,
                                  rel_tol=0.0, abs_tol=1e-12)
              or not math.isclose(self.axis_vector[1], dy / span,
                                  rel_tol=0.0, abs_tol=1e-12)):
            raise ValueError("corner leg axis conflicts with geometry")

    def to_dict(self) -> Mapping[str, Any]:
        # Native shadow evidence must retain the coordinates used by contract_id.
        # Display rounding here would alias distinct source hypotheses.
        return {
            "leg_id": self.leg_id,
            "terminal_jamb": list(self.terminal_jamb),
            "corner_vertex": list(self.corner_vertex),
            "axis_vector": list(self.axis_vector),
            "leg_span_pt": self.leg_span_pt,
            "leg_span_m": self.leg_span_m,
            "host_wall_id": self.host_wall_id,
        }


@dataclass(frozen=True)
class StructuralCornerApertureRecord:
    """Rigorous structural record for a multi-leg corner aperture."""

    contract_id: str
    classification: CornerApertureClassification
    leg_a: CornerOpeningLegRecord
    leg_b: CornerOpeningLegRecord
    corner_vertex: tuple[float, float]
    corner_angle_deg: float
    post_condition: CornerPostCondition
    total_girth_pt: float
    total_girth_m: float | None
    diagonal_chord_pt: float
    status: EvidenceResolutionStatus
    post_dimension_pt: float | None = None
    first_remaining_gate: str | None = None
    notes: str = ""
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    shadow_only: bool = True

    def __post_init__(self) -> None:
        # Frozen records can be directly constructed/replaced without the
        # shadow producer. A caller cannot manufacture source or post authority.
        abstained_gates = {
            CornerApertureClassification.ABSTAINED_DEGENERATE_LEG:
                ("corner_leg_span_out_of_bounds",),
            CornerApertureClassification.ABSTAINED_NON_ORTHOGONAL_ANGLE:
                ("corner_angle_non_orthogonal",),
            CornerApertureClassification.ABSTAINED_EXCESSIVE_POST_DIMENSION:
                ("corner_post_dimension_excessive",),
            CornerApertureClassification.ABSTAINED_UNVERIFIED_SOURCE:
                ("original_source_scale_or_post_unverified",
                 "distinct_corner_host_walls_unverified"),
        }
        if (type(self.classification) is not CornerApertureClassification
                or type(self.status) is not EvidenceResolutionStatus
                or self.post_condition is not CornerPostCondition.UNRESOLVED_CORNER_CONDITION
                or type(self.commercial_projection_allowed) is not bool
                or self.commercial_projection_allowed
                or type(self.takeoff_eligible) is not bool
                or self.takeoff_eligible
                or type(self.shadow_only) is not bool
                or not self.shadow_only):
            raise ValueError("source-neutral corner cannot grant commercial or post authority")
        if self.classification is CornerApertureClassification.GEOMETRIC_CANDIDATE:
            valid = (self.status is EvidenceResolutionStatus.CANDIDATE
                     and self.first_remaining_gate
                     == "original_source_corner_host_frame_unverified")
        else:
            valid = (self.status is EvidenceResolutionStatus.ABSTAINED
                     and self.first_remaining_gate in abstained_gates.get(
                         self.classification, ())
                     and self.total_girth_m is None
                     and self.leg_a.leg_span_m is None
                     and self.leg_b.leg_span_m is None)
        if not valid:
            raise ValueError("source-neutral corner classification and source gate conflict")
        if (type(self.leg_a) is not CornerOpeningLegRecord
                or type(self.leg_b) is not CornerOpeningLegRecord
                or type(self.corner_vertex) is not tuple
                or len(self.corner_vertex) != 2
                or any(not _finite_source_coordinate(v) for v in self.corner_vertex)
                or self.leg_a.corner_vertex != self.corner_vertex
                or self.leg_b.corner_vertex != self.corner_vertex
                or not _finite_real(self.corner_angle_deg)
                or not 0 <= self.corner_angle_deg <= 180
                or not _finite_real(self.total_girth_pt)
                or self.total_girth_pt < 0
                or not _finite_real(self.diagonal_chord_pt)
                or self.diagonal_chord_pt < 0
                or (self.post_dimension_pt is not None and
                    (not _finite_real(self.post_dimension_pt)
                     or self.post_dimension_pt < 0))
                or (self.total_girth_m is not None and
                    (not _finite_real(self.total_girth_m)
                     or self.total_girth_m <= 0))):
            raise ValueError("corner record numeric evidence must be finite and physical")
        expected_girth = self.leg_a.leg_span_pt + self.leg_b.leg_span_pt
        expected_chord = math.hypot(
            self.leg_a.terminal_jamb[0] - self.leg_b.terminal_jamb[0],
            self.leg_a.terminal_jamb[1] - self.leg_b.terminal_jamb[1],
        )
        if (not math.isfinite(expected_girth)
                or not math.isfinite(expected_chord)
                or not math.isclose(self.total_girth_pt, expected_girth,
                                    rel_tol=1e-12, abs_tol=1e-9)
                or not math.isclose(self.diagonal_chord_pt, expected_chord,
                                    rel_tol=1e-12, abs_tol=1e-9)):
            raise ValueError("corner record numeric evidence conflicts with leg geometry")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "contract_id": self.contract_id,
            "classification": self.classification.value,
            "leg_a": self.leg_a.to_dict(),
            "leg_b": self.leg_b.to_dict(),
            "corner_vertex": list(self.corner_vertex),
            "corner_angle_deg": self.corner_angle_deg,
            "post_condition": self.post_condition.value,
            "post_dimension_pt": self.post_dimension_pt,
            "total_girth_pt": self.total_girth_pt,
            "total_girth_m": self.total_girth_m,
            "diagonal_chord_pt": self.diagonal_chord_pt,
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
    # Conversion to float would alias distinct integer source hypotheses.
    if type(value) is int and abs(value) > 2**53:
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _finite_source_coordinate(value: object) -> bool:
    # Match the existing inclusive 2**53 native source-point identity limit
    # for floats and ints, without constraining independent scale/post scalars.
    return _finite_real(value) and abs(value) <= 2**53


class StructuralCornerApertureContinuityAuthority:
    """Source-neutral corner-leg hypotheses; never authenticates an opening."""

    def evaluate_corner_aperture(
        self,
        *,
        jamb_a: tuple[float, float],
        jamb_b: tuple[float, float],
        corner_vertex: tuple[float, float],
        host_wall_a_id: str,
        host_wall_b_id: str,
        post_dimension_pt: float | None = None,
        scale_ratio: float | None = None,
        context_label: str = "CORNER_APERTURE",
    ) -> StructuralCornerApertureRecord:
        """Return a shadow candidate or a typed abstention, never FIRM."""
        for name, point in (
            ("jamb_a", jamb_a), ("jamb_b", jamb_b),
            ("corner_vertex", corner_vertex),
        ):
            if not isinstance(point, (tuple, list)) or len(point) != 2:
                raise ValueError(f"{name} requires exactly two coordinates")
            if any(not _finite_source_coordinate(value) for value in point):
                raise ValueError(f"{name} requires finite real coordinates")
        for name, value in (
            ("post_dimension_pt", post_dimension_pt),
            ("scale_ratio", scale_ratio),
        ):
            if value is not None and (
                not _finite_real(value) or float(value) < 0
                or (name == "scale_ratio" and value == 0)
            ):
                raise ValueError(f"{name} must be finite and nonnegative")
        for name, value in (
            ("host_wall_a_id", host_wall_a_id),
            ("host_wall_b_id", host_wall_b_id),
            ("context_label", context_label),
        ):
            # A padded or nonprintable caller identity is not a second
            # source wall. Reject it before dual-host comparison and stable ID
            # construction rather than silently aliasing physical ownership.
            if (type(value) is not str or not value
                    or value != value.strip() or not value.isprintable()):
                raise ValueError(f"{name} must be an exact printable source identity")

        a = (float(jamb_a[0]), float(jamb_a[1]))
        b = (float(jamb_b[0]), float(jamb_b[1]))
        vertex = (float(corner_vertex[0]), float(corner_vertex[1]))
        legs = sorted(((host_wall_a_id, a), (host_wall_b_id, b)))
        (host_a, a), (host_b, b) = legs

        dx_a, dy_a = a[0] - vertex[0], a[1] - vertex[1]
        dx_b, dy_b = b[0] - vertex[0], b[1] - vertex[1]
        span_a, span_b = math.hypot(dx_a, dy_a), math.hypot(dx_b, dy_b)
        total_pt = span_a + span_b
        chord_pt = math.hypot(b[0] - a[0], b[1] - a[1])
        if not all(math.isfinite(v) for v in (
            dx_a, dy_a, dx_b, dy_b, span_a, span_b, total_pt, chord_pt,
        )):
            raise ValueError("nonfinite corner geometry")
        axis_a = (dx_a / span_a, dy_a / span_a) if span_a else (0.0, 0.0)
        axis_b = (dx_b / span_b, dy_b / span_b) if span_b else (0.0, 0.0)
        dot = max(-1.0, min(1.0, axis_a[0] * axis_b[0] + axis_a[1] * axis_b[1]))
        angle = math.degrees(math.acos(dot))

        # Full-precision identity includes source-neutral scale, post, host and
        # geometry; sorting makes input-order swaps invariant.
        contract_id = stable_contract_id(
            f"CORNER_APERTURE_{context_label}",
            (
                *(v.hex() for v in (*vertex, *a, *b)),
                host_a, host_b,
                "missing_post" if post_dimension_pt is None else float(post_dimension_pt).hex(),
                "missing_scale" if scale_ratio is None else float(scale_ratio).hex(),
            ),
        )

        def record(
            classification: CornerApertureClassification,
            status: EvidenceResolutionStatus,
            gate: str,
            notes: str,
            ratio: float | None = None,
            post: CornerPostCondition = CornerPostCondition.UNRESOLVED_CORNER_CONDITION,
        ) -> StructuralCornerApertureRecord:
            if ratio is not None:
                metric_lengths = (span_a * ratio, span_b * ratio, total_pt * ratio)
                if not all(math.isfinite(v) and v > 0 for v in metric_lengths):
                    raise ValueError("invalid or underflowed hypothetical metric conversion")
            else:
                metric_lengths = (None, None, None)
            leg_a = CornerOpeningLegRecord(
                leg_id=f"{contract_id}:LEG_A",
                terminal_jamb=a, corner_vertex=vertex, axis_vector=axis_a,
                leg_span_pt=span_a, leg_span_m=metric_lengths[0], host_wall_id=host_a,
            )
            leg_b = CornerOpeningLegRecord(
                leg_id=f"{contract_id}:LEG_B",
                terminal_jamb=b, corner_vertex=vertex, axis_vector=axis_b,
                leg_span_pt=span_b, leg_span_m=metric_lengths[1], host_wall_id=host_b,
            )
            return StructuralCornerApertureRecord(
                contract_id=contract_id, classification=classification,
                leg_a=leg_a, leg_b=leg_b, corner_vertex=vertex,
                corner_angle_deg=angle, post_condition=post,
                total_girth_pt=total_pt, total_girth_m=metric_lengths[2],
                diagonal_chord_pt=chord_pt, status=status,
                post_dimension_pt=post_dimension_pt,
                first_remaining_gate=gate, notes=notes,
            )

        if (span_a < MIN_LEG_SPAN_PT or span_a > MAX_LEG_SPAN_PT
                or span_b < MIN_LEG_SPAN_PT or span_b > MAX_LEG_SPAN_PT):
            return record(
                CornerApertureClassification.ABSTAINED_DEGENERATE_LEG,
                EvidenceResolutionStatus.ABSTAINED, "corner_leg_span_out_of_bounds",
                "Corner leg span outside existing bounds.",
            )
        if angle < MIN_CORNER_ANGLE_DEG or angle > MAX_CORNER_ANGLE_DEG:
            return record(
                CornerApertureClassification.ABSTAINED_NON_ORTHOGONAL_ANGLE,
                EvidenceResolutionStatus.ABSTAINED, "corner_angle_non_orthogonal",
                "Corner angle outside orthogonal bounds.",
            )
        if post_dimension_pt is not None and post_dimension_pt > MAX_CORNER_POST_DIM_PT:
            return record(
                CornerApertureClassification.ABSTAINED_EXCESSIVE_POST_DIMENSION,
                EvidenceResolutionStatus.ABSTAINED, "corner_post_dimension_excessive",
                "Corner post exceeds existing maximum.",
            )
        if scale_ratio is None or post_dimension_pt is None:
            return record(
                CornerApertureClassification.ABSTAINED_UNVERIFIED_SOURCE,
                EvidenceResolutionStatus.ABSTAINED,
                "original_source_scale_or_post_unverified",
                "Missing scale or post receipt; no metric corner aperture.",
            )
        # Two legs cannot be independently hosted by the same physical wall ID.
        # Preserve the native geometry but abstain before a dual-host candidate
        # or hypothetical metric girth can be inferred from duplicate identity.
        if host_a == host_b:
            return record(
                CornerApertureClassification.ABSTAINED_UNVERIFIED_SOURCE,
                EvidenceResolutionStatus.ABSTAINED,
                "distinct_corner_host_walls_unverified",
                "Both legs claim the same host wall; distinct physical hosts unverified.",
            )
        # A caller's post dimension is not an original-source post receipt.
        # Preserve the numeric hypothesis, but never assert a physical post.
        post = CornerPostCondition.UNRESOLVED_CORNER_CONDITION
        return record(
            CornerApertureClassification.GEOMETRIC_CANDIDATE,
            EvidenceResolutionStatus.CANDIDATE,
            "original_source_corner_host_frame_unverified",
            "Unverified two-leg geometry only; NOT a source-confirmed opening.",
            float(scale_ratio), post,
        )
