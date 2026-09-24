"""Shadow figured-dimension span -> viewport physical-scale evidence.

Approved architecture (PR #879):
- one uniquely WITNESS_BOUND figured span may create CANDIDATE physical-scale
  evidence only;
- two or more independent compatible source-owned witness bundles may create
  CORROBORATED physical-scale evidence;
- this producer never mints FIRM scale;
- canonical scale compatibility/authority remains owned by
  pb_page_scale_calibration_authority.

The producer consumes an already viewport-scoped F.13 DimensionEvidenceBundle
plus existing migration ownership contracts.  Every candidate retains source
lineage.  Exact duplicates collapse deterministically.  Non-independent
records never increase the corroboration count.  Competing mappings are
retained; nearest/first/smallest/largest/majority selection is forbidden.

The shadow bridge at the bottom converts CORROBORATED mappings to existing
ScaleSourceReading(INFERRED) records and delegates to
resolve_page_scale_calibration.  It deliberately does not classify figured
spans as SCALE_BAR and does not modify live viewport binding or publication.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Optional, Sequence

from pb_dimension_graph_constraint_engine import (
    ConstraintStatus,
    DimensionObservation,
    _PLAUSIBLE_DIMENSION_RANGE_MM,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import (
    BindingStatus,
    CoordinateSpace,
    DimensionAnchorBinding,
    DimensionEvidenceBundle,
    ObservedGeometrySegment,
    classify_dimension_token,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType, ScaleCalibration
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    ScaleCalibrationStatus,
    ScaleSourceReading,
    ScaleSourceType,
    check_calibration_freshness,
    measurement_authority_for_page_scale,
    resolve_page_scale_calibration,
    scale_calibration_fingerprint,
)

FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION = "1.1.0"

FIGURED_SPAN_SCALE_UNAVAILABLE = "figured_span_scale_unavailable"
FIGURED_SPAN_SCALE_SINGLE_CANDIDATE = "figured_span_scale_single_candidate"
FIGURED_SPAN_SCALE_CORROBORATED = "figured_span_scale_corroborated"
FIGURED_SPAN_SCALE_CONFLICT = "figured_span_scale_conflict"
FIGURED_SPAN_SCALE_SCOPE_MISMATCH = "figured_span_scale_scope_mismatch"
FIGURED_SPAN_SCALE_CALIBRATION_UNAVAILABLE = "figured_span_scale_calibration_unavailable"
FIGURED_SPAN_SCALE_CALIBRATION_RESOLVED = "figured_span_scale_calibration_resolved"
FIGURED_SPAN_SCALE_CALIBRATION_CONFLICT = "figured_span_scale_calibration_conflict"

_NON_DRAWING_VIEW_TYPES = {
    DrawingViewType.SCHEDULE.value,
    DrawingViewType.LEGEND.value,
    DrawingViewType.SPECIFICATION.value,
    DrawingViewType.REPEATED_OR_REFERENCE.value,
    DrawingViewType.ADJACENT_SCOPE.value,
    DrawingViewType.UNKNOWN.value,
}


@dataclass(frozen=True)
class FiguredSpanScaleScope:
    document_id: str
    revision_id: str
    source_sha256: str
    page_no: int
    viewport_id: str

    def __post_init__(self) -> None:
        if not str(self.document_id or "").strip():
            raise ValueError("document_id is required")
        if not str(self.revision_id or "").strip():
            raise ValueError("revision_id is required")
        if not str(self.viewport_id or "").strip():
            raise ValueError("viewport_id is required")
        source_sha = str(self.source_sha256 or "")
        if (
            len(source_sha) != 64
            or source_sha.lower() != source_sha
            or any(ch not in "0123456789abcdef" for ch in source_sha)
        ):
            raise ValueError("source_sha256 must be a lower-case SHA-256 digest")
        if int(self.page_no) < 1:
            raise ValueError("page_no must be positive")


@dataclass(frozen=True)
class FiguredSpanScaleCandidate:
    candidate_id: str
    document_id: str
    source_sha256: str
    revision_id: str
    page_no: int
    viewport_id: str
    observation_id: str
    extraction_method: str
    dimension_line_id: Optional[str]
    witness_line_ids: tuple[str, ...]
    endpoints: Optional[tuple[tuple[float, float], tuple[float, float]]]
    raw_text: str
    physical_value: Optional[float]
    unit: str
    physical_span_mm: Optional[float]
    source_span_pt: Optional[float]
    points_per_mm: Optional[float]
    status: EvidenceResolutionStatus
    blocker_reasons: tuple[str, ...] = ()
    independence_group_id: Optional[str] = None
    duplicate_count: int = 1
    confidence: float = 0.0
    schema_version: str = FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION

    @property
    def valid(self) -> bool:
        return (
            self.status is EvidenceResolutionStatus.CANDIDATE
            and not self.blocker_reasons
            and self.points_per_mm is not None
        )


@dataclass(frozen=True)
class FiguredSpanScaleShadowResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope: FiguredSpanScaleScope
    records: tuple[FiguredSpanScaleCandidate, ...] = ()
    independence_group_ids: tuple[str, ...] = ()
    reconciliation_status: Optional[str] = None
    reconciliation_issues: tuple[str, ...] = ()
    schema_version: str = FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION

    @property
    def candidates(self) -> tuple[FiguredSpanScaleCandidate, ...]:
        return tuple(record for record in self.records if record.valid)

    @property
    def rejected_candidates(self) -> tuple[FiguredSpanScaleCandidate, ...]:
        return tuple(record for record in self.records if not record.valid)

    @property
    def quantity_m2(self) -> None:
        return None


@dataclass(frozen=True)
class FiguredSpanScaleCalibrationBridgeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    physical_scale_result: FiguredSpanScaleShadowResult
    calibration: Optional[ScaleCalibration]
    measurement_authority: str
    scale_fingerprint: Optional[str]
    viewport_id: str
    schema_version: str = FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION


def _bbox_fully_inside(
    inner: Sequence[float],
    outer: Sequence[float],
) -> bool:
    if len(inner) != 4 or len(outer) != 4:
        return False
    return (
        float(inner[0]) >= float(outer[0])
        and float(inner[1]) >= float(outer[1])
        and float(inner[2]) <= float(outer[2])
        and float(inner[3]) <= float(outer[3])
    )


def _point_in_bbox(point: Sequence[float], bbox: Sequence[float]) -> bool:
    if len(point) != 2 or len(bbox) != 4:
        return False
    return (
        float(bbox[0]) <= float(point[0]) <= float(bbox[2])
        and float(bbox[1]) <= float(point[1]) <= float(bbox[3])
    )


def _segment_in_bbox(segment: ObservedGeometrySegment, bbox: Sequence[float]) -> bool:
    return _point_in_bbox(segment.start, bbox) and _point_in_bbox(segment.end, bbox)


def _scope_blockers(
    *,
    scope: FiguredSpanScaleScope,
    context: ProviderContext,
    viewport: ViewportEvidence,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if scope.document_id != context.document_id:
        reasons.append("document_id_mismatch")
    if scope.source_sha256 != context.source_sha256:
        reasons.append("source_sha256_mismatch")
    if not context.revision_id or not context.current_revision_id:
        reasons.append("revision_unbound")
    elif context.revision_id != context.current_revision_id:
        reasons.append("stale_revision")
    if scope.revision_id != context.current_revision_id:
        reasons.append("scope_revision_mismatch")
    if scope.viewport_id != viewport.viewport_id:
        reasons.append("viewport_id_mismatch")
    if viewport.document_id != context.document_id:
        reasons.append("viewport_document_mismatch")
    try:
        viewport_page = int(viewport.page_id)
    except (TypeError, ValueError):
        viewport_page = -1
    if viewport_page != int(scope.page_no):
        reasons.append("viewport_page_mismatch")
    if scope.viewport_id not in context.trusted_viewport_ids():
        reasons.append("viewport_not_owned")
    if int(scope.page_no) not in context.trusted_page_numbers():
        reasons.append("page_not_owned")
    mapped = context.page_for_viewport(scope.viewport_id)
    if mapped is None or int(mapped) != int(scope.page_no):
        reasons.append("viewport_page_ownership_missing")
    if viewport.status is not ViewportResolutionStatus.RESOLVED:
        reasons.append("viewport_not_resolved")
    if viewport.view_type in _NON_DRAWING_VIEW_TYPES:
        reasons.append("viewport_not_scale_bearing_drawing")
    x0, y0, x1, y1 = viewport.bbox
    if not all(math.isfinite(float(v)) for v in viewport.bbox) or x1 <= x0 or y1 <= y0:
        reasons.append("viewport_bbox_invalid")
    return tuple(dict.fromkeys(reasons))


def _geometry_index(
    bundle: DimensionEvidenceBundle,
) -> dict[str, tuple[ObservedGeometrySegment, ...]]:
    grouped: dict[str, list[ObservedGeometrySegment]] = {}
    for segment in bundle.observed_geometry:
        if isinstance(segment, ObservedGeometrySegment):
            grouped.setdefault(str(segment.segment_id), []).append(segment)
    return {key: tuple(rows) for key, rows in grouped.items()}


def _bindings_for_observation(
    bundle: DimensionEvidenceBundle,
    observation_id: str,
) -> tuple[DimensionAnchorBinding, ...]:
    return tuple(
        binding
        for binding in bundle.bindings
        if isinstance(binding, DimensionAnchorBinding)
        and str(binding.observation_id) == str(observation_id)
    )


def _typed_physical_mm(
    observation: DimensionObservation,
) -> tuple[Optional[float], tuple[str, ...]]:
    reasons: list[str] = []
    if observation.authority != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value:
        reasons.append("not_documented_dimension_authority")
    if observation.conflict_state == ConstraintStatus.CONFLICT_MANUAL_REVIEW.value:
        reasons.append("dimension_conflict")
    raw_text = str(observation.raw_text or "")
    token = classify_dimension_token(raw_text)
    if not token.is_linear_dimension:
        reasons.append("typed_non_dimension_token")

    try:
        value_m = float(observation.value_m)
    except (TypeError, ValueError):
        value_m = math.nan
        reasons.append("malformed_unit")
    physical_mm = value_m * 1000.0 if math.isfinite(value_m) else None
    if physical_mm is None or not math.isfinite(physical_mm) or physical_mm <= 0.0:
        reasons.append("invalid_figured_value")
    elif not (
        _PLAUSIBLE_DIMENSION_RANGE_MM[0]
        <= physical_mm
        <= _PLAUSIBLE_DIMENSION_RANGE_MM[1]
    ):
        reasons.append("figured_value_outside_existing_plausible_range")

    if token.is_linear_dimension:
        try:
            if token.unit == "mm":
                token_mm = float(token.value)
            elif token.unit == "m":
                token_mm = float(token.value) * 1000.0
            elif token.unit == "in":
                token_mm = float(token.value) * 25.4
            else:
                token_mm = math.nan
        except (TypeError, ValueError):
            token_mm = math.nan
        if not math.isfinite(token_mm):
            reasons.append("malformed_typed_unit")
        elif physical_mm is not None and not math.isclose(
            token_mm,
            physical_mm,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            reasons.append("printed_value_observation_mismatch")

    try:
        confidence = float(observation.confidence)
    except (TypeError, ValueError):
        confidence = math.nan
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        reasons.append("invalid_confidence")

    return physical_mm, tuple(dict.fromkeys(reasons))


def _safe_optional_float(value: object) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _normalised_endpoints(
    binding: DimensionAnchorBinding,
) -> tuple[Optional[tuple[tuple[float, float], tuple[float, float]]], tuple[str, ...]]:
    reasons: list[str] = []
    endpoints = binding.endpoints
    if endpoints is None or len(endpoints) != 2:
        return None, ("resolved_endpoints_missing",)
    try:
        first = (float(endpoints[0][0]), float(endpoints[0][1]))
        second = (float(endpoints[1][0]), float(endpoints[1][1]))
    except (TypeError, ValueError, IndexError):
        return None, ("resolved_endpoints_invalid",)
    if not all(math.isfinite(value) for value in (*first, *second)):
        reasons.append("resolved_endpoints_invalid")
    if reasons:
        return None, tuple(reasons)
    ordered = tuple(sorted((first, second)))
    return (ordered[0], ordered[1]), ()


def _source_identity_payload(
    *,
    scope: FiguredSpanScaleScope,
    observation: DimensionObservation,
    binding: Optional[DimensionAnchorBinding],
    endpoints: Optional[tuple[tuple[float, float], tuple[float, float]]],
) -> dict[str, object]:
    return {
        "document_id": scope.document_id,
        "source_sha256": scope.source_sha256,
        "revision_id": scope.revision_id,
        "page_no": scope.page_no,
        "viewport_id": scope.viewport_id,
        "observation_id": str(observation.dimension_id),
        "extraction_method": str(observation.extraction_method or ""),
        "raw_text": str(observation.raw_text or ""),
        "value": _safe_optional_float(observation.value),
        "unit": str(observation.unit or ""),
        "dimension_line_id": None if binding is None else binding.dimension_line_id,
        "witness_line_ids": []
        if binding is None
        else sorted(str(value) for value in binding.witness_line_ids),
        "endpoints": endpoints,
    }


def _build_record(
    *,
    observation: DimensionObservation,
    binding: Optional[DimensionAnchorBinding],
    geometry: dict[str, tuple[ObservedGeometrySegment, ...]],
    scope: FiguredSpanScaleScope,
    viewport: ViewportEvidence,
) -> FiguredSpanScaleCandidate:
    reasons: list[str] = []
    if int(observation.source_page) != int(scope.page_no):
        reasons.append("observation_page_mismatch")
    if str(observation.view_id or "") != scope.viewport_id:
        reasons.append("observation_viewport_mismatch")
    if observation.bbox is None or not _bbox_fully_inside(observation.bbox, viewport.bbox):
        reasons.append("observation_bbox_outside_viewport")

    if binding is None:
        reasons.append("binding_missing")
        endpoints = None
    else:
        if binding.status != BindingStatus.WITNESS_BOUND.value:
            reasons.append(f"binding_not_witness_bound:{binding.status}")
        if not str(binding.dimension_line_id or "").strip():
            reasons.append("dimension_line_id_missing")
        witness_ids = tuple(str(value) for value in binding.witness_line_ids)
        if len(witness_ids) != 2:
            reasons.append("witness_count_not_two")
        elif len(set(witness_ids)) != 2:
            reasons.append("duplicated_witness")
        endpoints, endpoint_reasons = _normalised_endpoints(binding)
        reasons.extend(endpoint_reasons)
        if endpoints is not None and not all(
            _point_in_bbox(point, viewport.bbox) for point in endpoints
        ):
            reasons.append("resolved_endpoints_outside_viewport")

    physical_mm, physical_reasons = _typed_physical_mm(observation)
    reasons.extend(physical_reasons)

    line_id = None if binding is None else str(binding.dimension_line_id or "")
    witness_ids = () if binding is None else tuple(str(value) for value in binding.witness_line_ids)

    required_segment_ids = tuple(
        value
        for value in (line_id, *witness_ids)
        if str(value or "").strip()
    )
    for segment_id in required_segment_ids:
        matches = geometry.get(segment_id, ())
        if len(matches) != 1:
            reasons.append(f"source_segment_identity_not_unique:{segment_id}")
            continue
        segment = matches[0]
        if int(segment.source_page) != int(scope.page_no):
            reasons.append(f"source_segment_page_mismatch:{segment_id}")
        if str(segment.view_id or "") != scope.viewport_id:
            reasons.append(f"source_segment_viewport_mismatch:{segment_id}")
        if segment.coordinate_space != CoordinateSpace.PDF_POINTS.value:
            reasons.append(f"source_segment_coordinate_space_invalid:{segment_id}")
        if not _segment_in_bbox(segment, viewport.bbox):
            reasons.append(
                "dimension_line_crosses_viewport"
                if segment_id == line_id
                else f"witness_crosses_viewport:{segment_id}"
            )

    source_span_pt: Optional[float] = None
    points_per_mm: Optional[float] = None
    if endpoints is not None:
        source_span_pt = math.hypot(
            endpoints[1][0] - endpoints[0][0],
            endpoints[1][1] - endpoints[0][1],
        )
        if not math.isfinite(source_span_pt) or source_span_pt <= 0.0:
            reasons.append("native_span_invalid")
            source_span_pt = None
        elif physical_mm is not None and math.isfinite(physical_mm) and physical_mm > 0.0:
            points_per_mm = source_span_pt / physical_mm
            if not math.isfinite(points_per_mm) or points_per_mm <= 0.0:
                reasons.append("physical_mapping_invalid")
                points_per_mm = None

    reasons = list(dict.fromkeys(reasons))
    status = (
        EvidenceResolutionStatus.CANDIDATE
        if not reasons and points_per_mm is not None
        else EvidenceResolutionStatus.ABSTAINED
    )
    payload = _source_identity_payload(
        scope=scope,
        observation=observation,
        binding=binding,
        endpoints=endpoints,
    )
    candidate_id = stable_contract_id(
        "figured_span_scale_shadow_v1",
        payload,
        digest_chars=32,
    )
    confidence = _safe_optional_float(observation.confidence)
    return FiguredSpanScaleCandidate(
        candidate_id=candidate_id,
        document_id=scope.document_id,
        source_sha256=scope.source_sha256,
        revision_id=scope.revision_id,
        page_no=scope.page_no,
        viewport_id=scope.viewport_id,
        observation_id=str(observation.dimension_id),
        extraction_method=str(observation.extraction_method or ""),
        dimension_line_id=line_id or None,
        witness_line_ids=tuple(sorted(witness_ids)),
        endpoints=endpoints,
        raw_text=str(observation.raw_text or ""),
        physical_value=_safe_optional_float(observation.value),
        unit=str(observation.unit or ""),
        physical_span_mm=physical_mm if physical_mm is not None and math.isfinite(physical_mm) else None,
        source_span_pt=source_span_pt,
        points_per_mm=points_per_mm,
        status=status,
        blocker_reasons=tuple(reasons),
        confidence=confidence if confidence is not None else 0.0,
    )


def _collapse_exact_duplicates(
    records: Sequence[FiguredSpanScaleCandidate],
) -> tuple[FiguredSpanScaleCandidate, ...]:
    by_id: dict[str, FiguredSpanScaleCandidate] = {}
    counts: dict[str, int] = {}
    for record in records:
        counts[record.candidate_id] = counts.get(record.candidate_id, 0) + 1
        existing = by_id.get(record.candidate_id)
        if existing is None:
            by_id[record.candidate_id] = record
        elif existing != record:
            # Same source identity must never equivocate.
            blockers = tuple(
                dict.fromkeys(
                    (
                        *existing.blocker_reasons,
                        *record.blocker_reasons,
                        "duplicate_source_identity_equivocation",
                    )
                )
            )
            by_id[record.candidate_id] = replace(
                existing,
                status=EvidenceResolutionStatus.ABSTAINED,
                blocker_reasons=blockers,
            )
    return tuple(
        replace(by_id[candidate_id], duplicate_count=counts[candidate_id])
        for candidate_id in sorted(by_id)
    )


def _span_identity(candidate: FiguredSpanScaleCandidate) -> tuple[object, ...]:
    endpoints = candidate.endpoints or ()
    rounded = tuple(
        tuple(round(float(value), 9) for value in point)
        for point in endpoints
    )
    return (rounded, None if candidate.source_span_pt is None else round(candidate.source_span_pt, 9))


def _same_source_system(
    left: FiguredSpanScaleCandidate,
    right: FiguredSpanScaleCandidate,
) -> bool:
    if left.observation_id == right.observation_id:
        return True
    if left.dimension_line_id and left.dimension_line_id == right.dimension_line_id:
        return True
    if left.witness_line_ids and left.witness_line_ids == right.witness_line_ids:
        return True
    if _span_identity(left) == _span_identity(right):
        return True
    return False


def _assign_independence_groups(
    records: Sequence[FiguredSpanScaleCandidate],
) -> tuple[tuple[FiguredSpanScaleCandidate, ...], tuple[str, ...]]:
    valid_indices = [index for index, record in enumerate(records) if record.valid]
    parents = {index: index for index in valid_indices}

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parents[max(root_left, root_right)] = min(root_left, root_right)

    for pos, left_index in enumerate(valid_indices):
        for right_index in valid_indices[pos + 1 :]:
            if _same_source_system(records[left_index], records[right_index]):
                union(left_index, right_index)

    grouped: dict[int, list[int]] = {}
    for index in valid_indices:
        grouped.setdefault(find(index), []).append(index)

    group_ids: dict[int, str] = {}
    for root, indices in grouped.items():
        candidate_ids = sorted(records[index].candidate_id for index in indices)
        group_ids[root] = stable_contract_id(
            "figured_span_scale_group",
            {"candidate_ids": candidate_ids},
            digest_chars=24,
        )

    updated = list(records)
    for index in valid_indices:
        updated[index] = replace(
            updated[index],
            independence_group_id=group_ids[find(index)],
        )
    return tuple(updated), tuple(sorted(group_ids.values()))


def scale_readings_for_figured_span(
    result: FiguredSpanScaleShadowResult,
) -> tuple[ScaleSourceReading, ...]:
    """Translate retained valid mappings into existing INFERRED scale readings."""
    readings: list[ScaleSourceReading] = []
    for candidate in sorted(result.candidates, key=lambda item: item.candidate_id):
        assert candidate.points_per_mm is not None
        px_per_m = candidate.points_per_mm * 1000.0
        ratio = POINTS_PER_METRE_AT_1_1 / px_per_m
        readings.append(
            ScaleSourceReading(
                source_type=ScaleSourceType.INFERRED.value,
                scale_text=f"figured-span:{candidate.candidate_id}",
                ratio=ratio,
                confidence=candidate.confidence,
            )
        )
    return tuple(readings)


def resolve_figured_span_scale_shadow(
    bundle: DimensionEvidenceBundle,
    *,
    scope: FiguredSpanScaleScope,
    context: ProviderContext,
    viewport: ViewportEvidence,
) -> FiguredSpanScaleShadowResult:
    """Derive physical-scale evidence without minting canonical scale authority."""
    if type(bundle) is not DimensionEvidenceBundle:
        raise TypeError("bundle must be DimensionEvidenceBundle")
    if type(scope) is not FiguredSpanScaleScope:
        raise TypeError("scope must be FiguredSpanScaleScope")
    if type(context) is not ProviderContext:
        raise TypeError("context must be ProviderContext")
    if type(viewport) is not ViewportEvidence:
        raise TypeError("viewport must be ViewportEvidence")

    scope_reasons = _scope_blockers(scope=scope, context=context, viewport=viewport)
    if scope_reasons:
        return FiguredSpanScaleShadowResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(FIGURED_SPAN_SCALE_SCOPE_MISMATCH, *scope_reasons),
            scope=scope,
        )

    geometry = _geometry_index(bundle)
    raw_records: list[FiguredSpanScaleCandidate] = []
    for observation in bundle.observations:
        if not isinstance(observation, DimensionObservation):
            continue
        bindings = _bindings_for_observation(bundle, observation.dimension_id)
        if not bindings:
            raw_records.append(
                _build_record(
                    observation=observation,
                    binding=None,
                    geometry=geometry,
                    scope=scope,
                    viewport=viewport,
                )
            )
            continue
        for binding in bindings:
            raw_records.append(
                _build_record(
                    observation=observation,
                    binding=binding,
                    geometry=geometry,
                    scope=scope,
                    viewport=viewport,
                )
            )

    records = _collapse_exact_duplicates(raw_records)
    records, group_ids = _assign_independence_groups(records)
    candidates = tuple(record for record in records if record.valid)

    if not candidates:
        return FiguredSpanScaleShadowResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(FIGURED_SPAN_SCALE_UNAVAILABLE,),
            scope=scope,
            records=records,
        )

    provisional = FiguredSpanScaleShadowResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(FIGURED_SPAN_SCALE_SINGLE_CANDIDATE,),
        scope=scope,
        records=records,
        independence_group_ids=group_ids,
    )
    reconciliation = resolve_page_scale_calibration(
        page_no=scope.page_no,
        sheet_label=f"viewport:{scope.viewport_id}:figured-span-shadow",
        readings=list(scale_readings_for_figured_span(provisional)),
        revision_id=scope.revision_id,
    )

    if reconciliation.status in {
        ScaleCalibrationStatus.CONFLICTING.value,
        ScaleCalibrationStatus.MANUAL_REQUIRED.value,
        ScaleCalibrationStatus.BLOCKED.value,
        ScaleCalibrationStatus.UNKNOWN.value,
    }:
        return replace(
            provisional,
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(FIGURED_SPAN_SCALE_CONFLICT,),
            reconciliation_status=reconciliation.status,
            reconciliation_issues=tuple(reconciliation.issues),
        )

    if len(group_ids) < 2:
        return replace(
            provisional,
            reconciliation_status=reconciliation.status,
            reconciliation_issues=tuple(reconciliation.issues),
        )

    return replace(
        provisional,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(FIGURED_SPAN_SCALE_CORROBORATED,),
        reconciliation_status=reconciliation.status,
        reconciliation_issues=tuple(reconciliation.issues),
    )


def build_figured_span_scale_calibration_shadow(
    *,
    physical_scale_result: FiguredSpanScaleShadowResult,
    scope: FiguredSpanScaleScope,
    context: ProviderContext,
    viewport: ViewportEvidence,
) -> FiguredSpanScaleCalibrationBridgeResult:
    """Route CORROBORATED figured-span evidence through canonical scale authority.

    The bridge emits only existing ScaleSourceReading(INFERRED) records.  It
    neither rewrites source type nor upgrades the authority returned by the
    canonical resolver.
    """
    scope_reasons = _scope_blockers(scope=scope, context=context, viewport=viewport)
    if (
        physical_scale_result.scope != scope
        or scope_reasons
        or physical_scale_result.status is not EvidenceResolutionStatus.CORROBORATED
        or len(physical_scale_result.independence_group_ids) < 2
    ):
        return FiguredSpanScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(
                FIGURED_SPAN_SCALE_CALIBRATION_UNAVAILABLE,
                *scope_reasons,
            ),
            physical_scale_result=physical_scale_result,
            calibration=None,
            measurement_authority=AuthorityStatus.BLOCKED.value,
            scale_fingerprint=None,
            viewport_id=scope.viewport_id,
        )

    calibration = resolve_page_scale_calibration(
        page_no=scope.page_no,
        sheet_label=f"viewport:{scope.viewport_id}:figured-span-shadow",
        readings=list(scale_readings_for_figured_span(physical_scale_result)),
        revision_id=scope.revision_id,
    )
    fresh = check_calibration_freshness(calibration, context.current_revision_id)
    authority = measurement_authority_for_page_scale(fresh)
    fingerprint = scale_calibration_fingerprint(fresh)

    if fresh.status in {
        ScaleCalibrationStatus.CONFLICTING.value,
        ScaleCalibrationStatus.MANUAL_REQUIRED.value,
        ScaleCalibrationStatus.BLOCKED.value,
        ScaleCalibrationStatus.UNKNOWN.value,
    }:
        return FiguredSpanScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(FIGURED_SPAN_SCALE_CALIBRATION_CONFLICT,),
            physical_scale_result=physical_scale_result,
            calibration=fresh,
            measurement_authority=authority,
            scale_fingerprint=fingerprint,
            viewport_id=scope.viewport_id,
        )

    return FiguredSpanScaleCalibrationBridgeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(FIGURED_SPAN_SCALE_CALIBRATION_RESOLVED,),
        physical_scale_result=physical_scale_result,
        calibration=fresh,
        measurement_authority=authority,
        scale_fingerprint=fingerprint,
        viewport_id=scope.viewport_id,
    )


__all__ = [
    "FIGURED_SPAN_SCALE_CALIBRATION_CONFLICT",
    "FIGURED_SPAN_SCALE_CALIBRATION_RESOLVED",
    "FIGURED_SPAN_SCALE_CALIBRATION_UNAVAILABLE",
    "FIGURED_SPAN_SCALE_CONFLICT",
    "FIGURED_SPAN_SCALE_CORROBORATED",
    "FIGURED_SPAN_SCALE_SCOPE_MISMATCH",
    "FIGURED_SPAN_SCALE_SHADOW_SCHEMA_VERSION",
    "FIGURED_SPAN_SCALE_SINGLE_CANDIDATE",
    "FIGURED_SPAN_SCALE_UNAVAILABLE",
    "FiguredSpanScaleCalibrationBridgeResult",
    "FiguredSpanScaleCandidate",
    "FiguredSpanScaleScope",
    "FiguredSpanScaleShadowResult",
    "build_figured_span_scale_calibration_shadow",
    "resolve_figured_span_scale_shadow",
    "scale_readings_for_figured_span",
]
