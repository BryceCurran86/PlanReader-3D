"""Shadow-only figured-dimension span -> physical-scale evidence.

Consumes already viewport-scoped F.13 DimensionEvidenceBundle output.  It does
not publish a ScaleCalibration, does not alter live extraction, and does not
grant commercial measurement authority.

A figured span is eligible only when F.13 has uniquely bound it to a native
dimension line plus exactly two witness lines/endpoints.  Candidate mappings
are reconciled through the existing page-scale conflict semantics using
INFERRED readings, so this module does not invent a second scale tolerance or
authority ladder.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence

from pb_dimension_graph_constraint_engine import ConstraintStatus, DimensionObservation
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionAnchorBinding,
    DimensionEvidenceBundle,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    ScaleCalibrationStatus,
    ScaleSourceReading,
    ScaleSourceType,
    resolve_page_scale_calibration,
)

FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION = "1.0.0"
FIGURED_SPAN_SCALE_UNAVAILABLE = "figured_span_scale_unavailable"
FIGURED_SPAN_SCALE_SINGLE_CANDIDATE = "figured_span_scale_single_candidate"
FIGURED_SPAN_SCALE_CORROBORATED = "figured_span_scale_corroborated"
FIGURED_SPAN_SCALE_CONFLICT = "figured_span_scale_conflict"
FIGURED_SPAN_SCALE_SCOPE_CONFLICT = "figured_span_scale_scope_conflict"


@dataclass(frozen=True)
class FiguredSpanScaleScope:
    document_id: str
    revision_id: str
    source_sha256: str
    page_no: int
    viewport_id: str

    def __post_init__(self) -> None:
        if not self.document_id or not self.revision_id or not self.viewport_id:
            raise ValueError("document_id, revision_id and viewport_id are required")
        if (
            len(self.source_sha256) != 64
            or self.source_sha256.lower() != self.source_sha256
            or any(ch not in "0123456789abcdef" for ch in self.source_sha256)
        ):
            raise ValueError("source_sha256 must be a lower-case SHA-256 digest")
        if self.page_no < 1:
            raise ValueError("page_no must be positive")


@dataclass(frozen=True)
class FiguredSpanScaleCandidate:
    candidate_id: str
    observation_id: str
    dimension_line_id: str
    witness_line_ids: tuple[str, str]
    endpoints: tuple[tuple[float, float], tuple[float, float]]
    source_span_pt: float
    physical_span_mm: float
    points_per_mm: float
    raw_text: str
    confidence: float


@dataclass(frozen=True)
class FiguredSpanScaleShadowResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope: FiguredSpanScaleScope
    candidates: tuple[FiguredSpanScaleCandidate, ...] = ()
    reconciliation_status: Optional[str] = None
    schema_version: str = FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION

    @property
    def quantity_m2(self) -> None:
        return None


def _binding_index(
    bindings: Sequence[DimensionAnchorBinding],
) -> tuple[dict[str, DimensionAnchorBinding], set[str]]:
    grouped: dict[str, list[DimensionAnchorBinding]] = {}
    for binding in bindings:
        grouped.setdefault(str(binding.observation_id), []).append(binding)
    unique: dict[str, DimensionAnchorBinding] = {}
    duplicates: set[str] = set()
    for observation_id, rows in grouped.items():
        if len(rows) == 1:
            unique[observation_id] = rows[0]
        else:
            duplicates.add(observation_id)
    return unique, duplicates


def _retained_candidates(
    candidates: Sequence[FiguredSpanScaleCandidate],
) -> tuple[FiguredSpanScaleCandidate, ...]:
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    return tuple(by_id[candidate_id] for candidate_id in sorted(by_id))


def _physical_span_mm(observation: DimensionObservation) -> Optional[float]:
    if observation.authority != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value:
        return None
    if observation.conflict_state == ConstraintStatus.CONFLICT_MANUAL_REVIEW.value:
        return None
    try:
        value_m = float(observation.value_m)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value_m) or value_m <= 0.0:
        return None
    return value_m * 1000.0


def _candidate(
    observation: DimensionObservation,
    binding: DimensionAnchorBinding,
    scope: FiguredSpanScaleScope,
) -> Optional[FiguredSpanScaleCandidate]:
    if observation.dimension_id != binding.observation_id:
        return None
    if observation.source_page != scope.page_no or observation.view_id != scope.viewport_id:
        return None
    if binding.status != BindingStatus.WITNESS_BOUND.value:
        return None
    if not binding.dimension_line_id or len(binding.witness_line_ids) != 2 or binding.endpoints is None:
        return None

    physical_span_mm = _physical_span_mm(observation)
    if physical_span_mm is None:
        return None

    try:
        a = (float(binding.endpoints[0][0]), float(binding.endpoints[0][1]))
        b = (float(binding.endpoints[1][0]), float(binding.endpoints[1][1]))
    except (TypeError, ValueError, IndexError):
        return None
    if not all(math.isfinite(value) for value in (*a, *b)):
        return None
    source_span_pt = math.hypot(b[0] - a[0], b[1] - a[1])
    if not math.isfinite(source_span_pt) or source_span_pt <= 0.0:
        return None
    points_per_mm = source_span_pt / physical_span_mm
    if not math.isfinite(points_per_mm) or points_per_mm <= 0.0:
        return None

    witness_ids = tuple(sorted(str(value) for value in binding.witness_line_ids))
    endpoints = tuple(sorted((a, b)))
    payload = {
        "document_id": scope.document_id,
        "revision_id": scope.revision_id,
        "source_sha256": scope.source_sha256,
        "page_no": scope.page_no,
        "viewport_id": scope.viewport_id,
        "observation_id": observation.dimension_id,
        "dimension_line_id": str(binding.dimension_line_id),
        "witness_line_ids": witness_ids,
        "endpoints": endpoints,
        "source_span_pt": round(source_span_pt, 12),
        "physical_span_mm": round(physical_span_mm, 9),
    }
    return FiguredSpanScaleCandidate(
        candidate_id=stable_contract_id("figured_span_scale_shadow_v1", payload, digest_chars=32),
        observation_id=observation.dimension_id,
        dimension_line_id=str(binding.dimension_line_id),
        witness_line_ids=(witness_ids[0], witness_ids[1]),
        endpoints=(endpoints[0], endpoints[1]),
        source_span_pt=source_span_pt,
        physical_span_mm=physical_span_mm,
        points_per_mm=points_per_mm,
        raw_text=str(observation.raw_text or ""),
        confidence=float(observation.confidence) if math.isfinite(float(observation.confidence)) else 0.0,
    )


def _inferred_scale_reading(candidate: FiguredSpanScaleCandidate) -> ScaleSourceReading:
    px_per_m = candidate.points_per_mm * 1000.0
    ratio = POINTS_PER_METRE_AT_1_1 / px_per_m
    return ScaleSourceReading(
        source_type=ScaleSourceType.INFERRED.value,
        scale_text=f"figured-span:{candidate.candidate_id}",
        ratio=ratio,
        confidence=candidate.confidence,
    )


def resolve_figured_span_scale_shadow(
    bundle: DimensionEvidenceBundle,
    *,
    scope: FiguredSpanScaleScope,
) -> FiguredSpanScaleShadowResult:
    """Retain and reconcile viewport-owned witness-bound figured span mappings.

    One valid mapping remains CANDIDATE.  Two or more are CORROBORATED only
    when the existing page-scale reconciler says the inferred ratios do not
    conflict.  Conflicts retain all alternatives; no candidate is selected as
    canonical and no ScaleCalibration is returned.
    """
    if not isinstance(bundle, DimensionEvidenceBundle):
        raise TypeError("bundle must be DimensionEvidenceBundle")

    binding_by_id, duplicate_binding_ids = _binding_index(bundle.bindings)
    if duplicate_binding_ids:
        alternatives: list[FiguredSpanScaleCandidate] = []
        for observation in bundle.observations:
            if not isinstance(observation, DimensionObservation):
                continue
            if observation.dimension_id not in duplicate_binding_ids:
                continue
            for binding in bundle.bindings:
                if binding.observation_id != observation.dimension_id:
                    continue
                candidate = _candidate(observation, binding, scope)
                if candidate is not None:
                    alternatives.append(candidate)
        return FiguredSpanScaleShadowResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(FIGURED_SPAN_SCALE_SCOPE_CONFLICT,),
            scope=scope,
            candidates=_retained_candidates(alternatives),
        )

    candidates: list[FiguredSpanScaleCandidate] = []
    seen_ids: set[str] = set()
    for observation in bundle.observations:
        if not isinstance(observation, DimensionObservation):
            continue
        binding = binding_by_id.get(observation.dimension_id)
        candidate = None if binding is None else _candidate(observation, binding, scope)
        if observation.dimension_id in seen_ids:
            if candidate is not None:
                candidates.append(candidate)
            return FiguredSpanScaleShadowResult(
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(FIGURED_SPAN_SCALE_SCOPE_CONFLICT,),
                scope=scope,
                candidates=_retained_candidates(candidates),
            )
        seen_ids.add(observation.dimension_id)
        if candidate is not None:
            candidates.append(candidate)

    retained = _retained_candidates(candidates)
    if not retained:
        return FiguredSpanScaleShadowResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(FIGURED_SPAN_SCALE_UNAVAILABLE,),
            scope=scope,
        )
    if len(retained) == 1:
        return FiguredSpanScaleShadowResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(FIGURED_SPAN_SCALE_SINGLE_CANDIDATE,),
            scope=scope,
            candidates=retained,
            reconciliation_status=ScaleCalibrationStatus.PROVISIONAL.value,
        )

    reconciliation = resolve_page_scale_calibration(
        page_no=scope.page_no,
        sheet_label=f"viewport:{scope.viewport_id}:figured-span-shadow",
        readings=[_inferred_scale_reading(candidate) for candidate in retained],
        revision_id=scope.revision_id,
    )
    if reconciliation.status in {
        ScaleCalibrationStatus.CONFLICTING.value,
        ScaleCalibrationStatus.MANUAL_REQUIRED.value,
        ScaleCalibrationStatus.BLOCKED.value,
        ScaleCalibrationStatus.UNKNOWN.value,
    }:
        return FiguredSpanScaleShadowResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(FIGURED_SPAN_SCALE_CONFLICT,),
            scope=scope,
            candidates=retained,
            reconciliation_status=reconciliation.status,
        )

    return FiguredSpanScaleShadowResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(FIGURED_SPAN_SCALE_CORROBORATED,),
        scope=scope,
        candidates=retained,
        reconciliation_status=reconciliation.status,
    )


__all__ = [
    "FIGURED_SPAN_SCALE_CONFLICT",
    "FIGURED_SPAN_SCALE_CORROBORATED",
    "FIGURED_SPAN_SCALE_SCOPE_CONFLICT",
    "FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION",
    "FIGURED_SPAN_SCALE_SINGLE_CANDIDATE",
    "FIGURED_SPAN_SCALE_UNAVAILABLE",
    "FiguredSpanScaleCandidate",
    "FiguredSpanScaleScope",
    "FiguredSpanScaleShadowResult",
    "resolve_figured_span_scale_shadow",
]
