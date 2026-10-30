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
- Structural Spandrel Sub-Sill shadow evaluates an unverified aperture candidate and vertical level
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

def _native_source_identity(value: object) -> bool:
    """Reject padded or control-bearing caller identities before shadow lineage."""
    return (
        type(value) is str
        and bool(value)
        and value == value.strip()
        and value.isprintable()
    )



class SpandrelSubSillClassification(str, Enum):
    """Classification outcome for window over sub-sill spandrel wall."""

    SPANDREL_SUB_SILL_CONFIRMED = "spandrel_sub_sill_confirmed"  # reserved for future source-backed receipt
    GEOMETRIC_CANDIDATE = "geometric_candidate"
    ABSTAINED_UNVERIFIED_SCALE = "abstained_unverified_scale"
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
    clear_span_m: float | None
    sill_height_mm: float
    head_height_mm: float
    glazing_height_mm: float | None
    glazing_aperture_area_sqm: float | None
    spandrel_wall_area_sqm: float | None
    total_wall_opening_area_sqm: float | None
    host_through_wall_id: str
    status: EvidenceResolutionStatus
    first_remaining_gate: str | None = None
    notes: str = ""
    # Unverified source-hypothesis inputs retained for immutable identity.
    context_label: str = "SPANDREL_WINDOW"
    scale_ratio: float | None = None
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    shadow_only: bool = True

    def __post_init__(self) -> None:
        # Source-free record authority must survive direct construction and
        # dataclasses.replace, not depend solely on the producer's call site.
        abstained_gates = {
            SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE:
                "original_source_scale_authority_unverified",
            SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS:
                "vertical_levels_inverted_or_negative",
            SpandrelSubSillClassification.ABSTAINED_DEGENERATE_SPAN:
                "clear_span_out_of_bounds",
        }
        if (type(self.classification) is not SpandrelSubSillClassification
                or type(self.status) is not EvidenceResolutionStatus
                or type(self.commercial_projection_allowed) is not bool
                or self.commercial_projection_allowed
                or type(self.takeoff_eligible) is not bool
                or self.takeoff_eligible
                or type(self.shadow_only) is not bool
                or not self.shadow_only):
            raise ValueError("source-neutral spandrel cannot grant commercial authority")
        if self.classification is SpandrelSubSillClassification.GEOMETRIC_CANDIDATE:
            valid = (self.status is EvidenceResolutionStatus.CANDIDATE
                     and self.first_remaining_gate
                     == "original_source_spandrel_host_scale_levels_unverified")
        else:
            valid = (self.classification in abstained_gates
                     and self.status is EvidenceResolutionStatus.ABSTAINED
                     and self.first_remaining_gate == abstained_gates.get(self.classification)
                     and all(value is None for value in (
                         self.clear_span_m, self.glazing_height_mm,
                         self.glazing_aperture_area_sqm,
                         self.spandrel_wall_area_sqm,
                         self.total_wall_opening_area_sqm,
                     )))
        if not valid:
            raise ValueError("source-neutral spandrel classification and source gate conflict")
        # Frozen shadow records are public dataclasses: direct construction and
        # dataclasses.replace must not serialize nonfinite/impossible evidence.
        def finite_real(value: object) -> bool:
            if type(value) not in (int, float):
                return False
            if type(value) is int and abs(value) > 2**53:
                return False
            try:
                return math.isfinite(float(value))
            except (OverflowError, ValueError):
                return False

        for point in (self.jamb_left, self.jamb_right):
            if (type(point) is not tuple or len(point) != 2
                    or any(not finite_real(v) or abs(v) > 2**53 for v in point)):
                raise ValueError("spandrel numeric evidence must be finite and physical")
        if (not finite_real(self.clear_span_pt) or self.clear_span_pt < 0
                or not finite_real(self.sill_height_mm)
                or not finite_real(self.head_height_mm)
                or any(value is not None and
                       (not finite_real(value) or value <= 0)
                       for value in (
                           self.clear_span_m, self.glazing_height_mm,
                           self.glazing_aperture_area_sqm,
                           self.spandrel_wall_area_sqm,
                           self.total_wall_opening_area_sqm,
                       ))):
            raise ValueError("spandrel numeric evidence must be finite and physical")
        if (not _native_source_identity(self.host_through_wall_id)
                or not _native_source_identity(self.context_label)):
            raise ValueError("spandrel exact host and context identity required")
        if self.jamb_left > self.jamb_right:
            raise ValueError("spandrel jamb ordering conflicts with producer")
        if (self.scale_ratio is not None
                and (not finite_real(self.scale_ratio) or self.scale_ratio <= 0)):
            raise ValueError("spandrel scale must be finite and positive")
        if ((self.classification is SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE)
                != (self.scale_ratio is None)):
            raise ValueError("spandrel scale receipt conflicts with source gate")
        expected_span = math.hypot(
            self.jamb_right[0] - self.jamb_left[0],
            self.jamb_right[1] - self.jamb_left[1],
        )
        if (not math.isfinite(expected_span)
                or not math.isclose(self.clear_span_pt, expected_span,
                                    rel_tol=1e-12, abs_tol=1e-9)):
            raise ValueError("spandrel numeric evidence conflicts with jamb geometry")
        # Reconstruct the producer's ordered first-failure decision from
        # frozen evidence. Status/gate string coherence alone is insufficient:
        # direct replacement can otherwise conceal a short span as an invalid
        # level, or relabel a valid candidate as a rejected hypothesis.
        if self.scale_ratio is None:
            expected_classification = (
                SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE)
        elif not MIN_CLEAR_SPAN_PT <= self.clear_span_pt <= MAX_CLEAR_SPAN_PT:
            expected_classification = (
                SpandrelSubSillClassification.ABSTAINED_DEGENERATE_SPAN)
        elif (self.sill_height_mm >= self.head_height_mm
              or self.head_height_mm <= 0 or self.sill_height_mm <= 0):
            expected_classification = (
                SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS)
        else:
            expected_classification = SpandrelSubSillClassification.GEOMETRIC_CANDIDATE
        if self.classification is not expected_classification:
            raise ValueError("spandrel frozen first-failing geometric gate conflict")

        if self.classification is SpandrelSubSillClassification.GEOMETRIC_CANDIDATE:
            # Direct construction and dataclasses.replace must honor the
            # same geometric bounds as evaluate_spandrel_sub_sill. A 1pt or
            # 301pt span cannot become CANDIDATE merely because its area
            # fields are internally consistent; it must remain abstained.
            if not MIN_CLEAR_SPAN_PT <= self.clear_span_pt <= MAX_CLEAR_SPAN_PT:
                raise ValueError("spandrel candidate span outside producer bounds")
            if (self.sill_height_mm <= 0
                    or self.head_height_mm <= self.sill_height_mm
                    or any(value is None for value in (
                        self.clear_span_m, self.glazing_height_mm,
                        self.glazing_aperture_area_sqm,
                        self.spandrel_wall_area_sqm,
                        self.total_wall_opening_area_sqm,
                    ))
                    or not math.isclose(self.glazing_height_mm,
                                        self.head_height_mm - self.sill_height_mm,
                                        rel_tol=1e-12, abs_tol=1e-9)
                    or not math.isclose(self.glazing_aperture_area_sqm,
                                        self.total_wall_opening_area_sqm,
                                        rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError("spandrel numeric evidence conflicts with candidate geometry")
            expected_metric_span = self.clear_span_pt * self.scale_ratio
            if (not math.isfinite(expected_metric_span)
                    or expected_metric_span <= 0
                    or not math.isclose(self.clear_span_m, expected_metric_span,
                                        rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError("spandrel metric span conflicts with scale receipt")
            # Public frozen records can be replaced after production. The
            # positive hypothetical areas must still equal their owned
            # span and vertical axes, not arbitrary caller-supplied m².
            expected_glazing = self.clear_span_m * (self.glazing_height_mm / 1000.0)
            expected_spandrel = self.clear_span_m * (self.sill_height_mm / 1000.0)
            if (not math.isfinite(expected_glazing)
                    or not math.isfinite(expected_spandrel)
                    or expected_glazing <= 0
                    or expected_spandrel <= 0
                    or not math.isclose(self.glazing_aperture_area_sqm,
                                        expected_glazing,
                                        rel_tol=1e-12, abs_tol=1e-12)
                    or not math.isclose(self.spandrel_wall_area_sqm,
                                        expected_spandrel,
                                        rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError("spandrel numeric evidence conflicts with metric area axes")

        # A public frozen record cannot retain a previous physical-host or
        # geometry identity after a coherent direct replacement. Source-neutral
        # identities do not establish source-backed measurement authority.
        expected_id = _spandrel_identity(
            self.context_label, self.host_through_wall_id,
            self.jamb_left, self.jamb_right,
            self.sill_height_mm, self.head_height_mm, self.scale_ratio,
        )
        if type(self.contract_id) is not str or self.contract_id != expected_id:
            raise ValueError("spandrel stable identity conflicts with source-neutral inputs")

    def to_dict(self) -> Mapping[str, Any]:
        # Retain full native/candidate evidence precision. The stable ID binds
        # these exact values; rounding would alias distinct shadow hypotheses.
        return {
            "schema_version": SCHEMA_VERSION,
            "contract_id": self.contract_id,
            "classification": self.classification.value,
            "jamb_left": list(self.jamb_left),
            "jamb_right": list(self.jamb_right),
            "clear_span_pt": self.clear_span_pt,
            "clear_span_m": self.clear_span_m,
            "sill_height_mm": self.sill_height_mm,
            "head_height_mm": self.head_height_mm,
            "glazing_height_mm": self.glazing_height_mm,
            "glazing_aperture_area_sqm": self.glazing_aperture_area_sqm,
            "spandrel_wall_area_sqm": self.spandrel_wall_area_sqm,
            "total_wall_opening_area_sqm": self.total_wall_opening_area_sqm,
            "host_through_wall_id": self.host_through_wall_id,
            "context_label": self.context_label,
            "scale_ratio": self.scale_ratio,
            "status": self.status.value,
            "first_remaining_gate": self.first_remaining_gate,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
            "shadow_only": self.shadow_only,
        }



def _spandrel_identity(
    context_label: str,
    host_through_wall_id: str,
    jamb_left: tuple[float, float],
    jamb_right: tuple[float, float],
    sill_height_mm: float,
    head_height_mm: float,
    scale_ratio: float | None,
) -> str:
    """Producer/frozen-record exact geometric hypothesis identity."""
    return stable_contract_id(
        f"SPANDREL_SUB_SILL_{context_label}",
        (
            host_through_wall_id,
            *(float(v).hex() for v in (*jamb_left, *jamb_right)),
            float(sill_height_mm).hex(),
            float(head_height_mm).hex(),
            "source_scale_unverified" if scale_ratio is None else float(scale_ratio).hex(),
        ),
    )


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
        scale_ratio: float | None = None,
        context_label: str = "SPANDREL_WINDOW",
    ) -> SpandrelSubSillRecord:
        """Evaluates clear span and vertical levels, computing glazing and sub-sill wall areas."""
        # Source-free inputs must never mint a metric or a confirmed opening.
        # In particular, int values too large to convert to float must abstain
        # rather than leaking an OverflowError through the shadow consumer.
        def _finite_real(value: object) -> bool:
            if type(value) not in (int, float):
                return False
            # Distinct source integer hypotheses must not alias after float conversion.
            if type(value) is int and abs(value) > 2**53:
                return False
            try:
                return math.isfinite(float(value))
            except (OverflowError, ValueError):
                return False

        def _finite_source_coordinate(value: object) -> bool:
            # Binary64 cannot preserve distinct native source-point identities
            # beyond the same inclusive 2**53 limit already used for ints.
            # Scalar heights and scales retain their separate validation.
            return _finite_real(value) and abs(value) <= 2**53

        for name, value in (("sill_height_mm", sill_height_mm),
                            ("head_height_mm", head_height_mm)):
            if not _finite_real(value):
                raise ValueError(f"{name} must be finite real")
        if scale_ratio is not None:
            if not _finite_real(scale_ratio):
                raise ValueError("scale_ratio must be finite real")
            if scale_ratio <= 0:
                raise ValueError("scale_ratio must be positive")
        # Unverified caller IDs are still lineage keys. A padded spelling
        # must not fragment one physical host into distinct shadow receipts.
        if not _native_source_identity(host_through_wall_id):
            raise ValueError("exact printable physical host identity required")
        if not _native_source_identity(context_label):
            raise ValueError("exact printable context identity required")
        for name, point in (("jamb_a", jamb_a), ("jamb_b", jamb_b)):
            if not isinstance(point, (tuple, list)) or len(point) != 2:
                raise ValueError(f"{name} must contain two coordinates")
            if any(not _finite_source_coordinate(v) for v in point):
                raise ValueError(f"{name} must contain finite real coordinates")
        # Detach caller-owned lists before storing geometry in frozen receipts.
        jamb_left, jamb_right = self._order_jambs(
            tuple(float(v) for v in jamb_a),
            tuple(float(v) for v in jamb_b),
        )
        dx = float(jamb_right[0]) - float(jamb_left[0])
        dy = float(jamb_right[1]) - float(jamb_left[1])
        clear_span_pt = math.hypot(dx, dy)
        if not math.isfinite(clear_span_pt):
            raise ValueError("nonfinite geometric span")
        if scale_ratio is None:
            # A typed abstention is essential at the existing shadow record
            # seam. Null metric fields are unknown, never zero quantities.
            contract_id = _spandrel_identity(
                context_label, host_through_wall_id, jamb_left, jamb_right,
                sill_height_mm, head_height_mm, None,
            )
            return SpandrelSubSillRecord(
                contract_id=contract_id,
                classification=SpandrelSubSillClassification.ABSTAINED_UNVERIFIED_SCALE,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=None,
                sill_height_mm=sill_height_mm,
                head_height_mm=head_height_mm,
                glazing_height_mm=None,
                glazing_aperture_area_sqm=None,
                spandrel_wall_area_sqm=None,
                total_wall_opening_area_sqm=None,
                host_through_wall_id=host_through_wall_id,
                context_label=context_label,
                scale_ratio=scale_ratio,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="original_source_scale_authority_unverified",
                notes="Source scale absent; no metric opening or wall area.",
            )

        contract_id = _spandrel_identity(
            context_label, host_through_wall_id, jamb_left, jamb_right,
            sill_height_mm, head_height_mm, scale_ratio,
        )

        # Gate 1: Clear span bounds
        if clear_span_pt < MIN_CLEAR_SPAN_PT or clear_span_pt > MAX_CLEAR_SPAN_PT:
            return SpandrelSubSillRecord(
                contract_id=contract_id,
                classification=SpandrelSubSillClassification.ABSTAINED_DEGENERATE_SPAN,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=None,
                sill_height_mm=sill_height_mm,
                head_height_mm=head_height_mm,
                glazing_height_mm=None,
                glazing_aperture_area_sqm=None,
                spandrel_wall_area_sqm=None,
                total_wall_opening_area_sqm=None,
                host_through_wall_id=host_through_wall_id,
                context_label=context_label,
                scale_ratio=scale_ratio,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="clear_span_out_of_bounds",
                notes=f"Clear span {clear_span_pt!r}pt outside bounds [{MIN_CLEAR_SPAN_PT}, {MAX_CLEAR_SPAN_PT}]pt.",
            )

        # Gate 2: Vertical levels validation
        if (
            sill_height_mm >= head_height_mm
            or head_height_mm <= 0
            or sill_height_mm <= 0
        ):
            return SpandrelSubSillRecord(
                contract_id=contract_id,
                classification=SpandrelSubSillClassification.ABSTAINED_INVALID_VERTICAL_LEVELS,
                jamb_left=jamb_left,
                jamb_right=jamb_right,
                clear_span_pt=clear_span_pt,
                clear_span_m=None,
                sill_height_mm=sill_height_mm,
                head_height_mm=head_height_mm,
                glazing_height_mm=None,
                glazing_aperture_area_sqm=None,
                spandrel_wall_area_sqm=None,
                total_wall_opening_area_sqm=None,
                host_through_wall_id=host_through_wall_id,
                context_label=context_label,
                scale_ratio=scale_ratio,
                status=EvidenceResolutionStatus.ABSTAINED,
                first_remaining_gate="vertical_levels_inverted_or_negative",
                notes=f"Invalid vertical levels: sill={sill_height_mm:.1f}mm >= head={head_height_mm:.1f}mm.",
            )

        # Source-free rejected geometry must abstain before metric conversion.
        # Extreme but finite caller scale/levels cannot mask the first typed
        # geometry or vertical-level failure with an arithmetic exception.
        clear_span_m = clear_span_pt * scale_ratio
        if not math.isfinite(clear_span_m) or (clear_span_pt > 0 and clear_span_m == 0):
            raise ValueError("nonfinite or underflowed metric conversion")

        glazing_height_mm = max(0.0, head_height_mm - sill_height_mm)
        glazing_height_m = glazing_height_mm / 1000.0
        sill_height_m = sill_height_mm / 1000.0
        head_height_m = head_height_mm / 1000.0
        if ((glazing_height_mm > 0 and glazing_height_m == 0)
                or (sill_height_mm > 0 and sill_height_m == 0)
                or (head_height_mm > 0 and head_height_m == 0)):
            raise ValueError("underflowed positive vertical measurement")

        glazing_area_sqm = clear_span_m * glazing_height_m
        spandrel_area_sqm = clear_span_m * sill_height_m
        # Solid sub-sill wall is not an opening deduction.
        total_opening_area_sqm = glazing_area_sqm
        if not all(math.isfinite(v) for v in (glazing_area_sqm, spandrel_area_sqm)):
            raise ValueError("nonfinite hypothetical area")
        if ((glazing_height_mm > 0 and glazing_area_sqm == 0)
                or (sill_height_mm > 0 and spandrel_area_sqm == 0)):
            raise ValueError("underflowed positive hypothetical area")

        # Shadow candidate only: physical opening and source scale unproven
        return SpandrelSubSillRecord(
            contract_id=contract_id,
            classification=SpandrelSubSillClassification.GEOMETRIC_CANDIDATE,
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
            context_label=context_label,
            scale_ratio=scale_ratio,
            status=EvidenceResolutionStatus.CANDIDATE,
            first_remaining_gate="original_source_spandrel_host_scale_levels_unverified",
            notes=(
                f"Unverified geometry only, NOT a source-authenticated opening: "
                f"glazing area={glazing_area_sqm!r}sqm, spandrel area={spandrel_area_sqm!r}sqm."
            ),
        )
