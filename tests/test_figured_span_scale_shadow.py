from __future__ import annotations

from copy import deepcopy
import math

import pytest

from pb_dimension_graph_constraint_engine import DimensionObservation
from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import (
    BindingStatus,
    CoordinateSpace,
    DimensionAnchorBinding,
    DimensionEvidenceBundle,
    ObservedGeometrySegment,
)
from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import (
    ScaleCalibrationStatus,
    ScaleSourceReading,
    ScaleSourceType,
    measurement_authority_for_page_scale,
    resolve_page_scale_calibration,
)
from pb_figured_span_scale_shadow import (
    FIGURED_SPAN_SCALE_CALIBRATION_RESOLVED,
    FIGURED_SPAN_SCALE_CALIBRATION_UNAVAILABLE,
    FIGURED_SPAN_SCALE_CONFLICT,
    FIGURED_SPAN_SCALE_CORROBORATED,
    FIGURED_SPAN_SCALE_SCOPE_MISMATCH,
    FIGURED_SPAN_SCALE_SINGLE_CANDIDATE,
    FIGURED_SPAN_SCALE_UNAVAILABLE,
    FiguredSpanScaleScope,
    build_figured_span_scale_calibration_shadow,
    resolve_figured_span_scale_shadow,
)


SHA = "a" * 64
PAGE = 41
VIEWPORT_ID = "elevation-a"
BBOX = (0.0, 0.0, 1000.0, 1000.0)


def _scope(
    *,
    source_sha256: str = SHA,
    revision_id: str = "rev-1",
    viewport_id: str = VIEWPORT_ID,
) -> FiguredSpanScaleScope:
    return FiguredSpanScaleScope(
        document_id="doc",
        revision_id=revision_id,
        source_sha256=source_sha256,
        page_no=PAGE,
        viewport_id=viewport_id,
    )


def _context(
    *,
    source_sha256: str = SHA,
    revision_id: str = "rev-1",
    current_revision_id: str = "rev-1",
    viewport_id: str = VIEWPORT_ID,
) -> ProviderContext:
    return ProviderContext(
        run_id="run",
        workspace_id="workspace",
        project_id="project",
        document_id="doc",
        source_sha256=source_sha256,
        revision_id=revision_id,
        current_revision_id=current_revision_id,
        selected_pages=(PAGE - 1,),
        owned_viewport_ids=(viewport_id,),
        evidence_snapshot_id="snapshot",
        owned_page_numbers=(PAGE,),
        viewport_page_ownership=((viewport_id, PAGE),),
    )


def _viewport(
    *,
    viewport_id: str = VIEWPORT_ID,
    bbox: tuple[float, float, float, float] = BBOX,
    view_type: str = DrawingViewType.ELEVATION.value,
    status: ViewportResolutionStatus = ViewportResolutionStatus.RESOLVED,
) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id=viewport_id,
        document_id="doc",
        page_id=str(PAGE),
        bbox=bbox,
        view_type=view_type,
        status=status,
        confidence=1.0,
    )


def _obs(
    observation_id: str,
    *,
    value: float,
    unit: str = "mm",
    raw_text: str | None = None,
    view_id: str = VIEWPORT_ID,
    source_page: int = PAGE,
    confidence: float = 1.0,
    authority: str = MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
) -> DimensionObservation:
    return DimensionObservation(
        dimension_id=observation_id,
        source_page=source_page,
        view_id=view_id,
        view_type=DrawingViewType.ELEVATION.value,
        bbox=(90.0, 90.0, 130.0, 105.0),
        raw_text=raw_text if raw_text is not None else f"{value:g}{unit if unit != 'mm' else ''}",
        value=value,
        unit=unit,
        authority=authority,
        confidence=confidence,
    )


def _binding_and_geometry(
    observation_id: str,
    *,
    span_pt: float,
    origin: tuple[float, float] = (100.0, 120.0),
    vertical: bool = False,
    status: str = BindingStatus.WITNESS_BOUND.value,
    suffix: str = "",
    duplicate_witness: bool = False,
    line_override: tuple[tuple[float, float], tuple[float, float]] | None = None,
) -> tuple[DimensionAnchorBinding, list[ObservedGeometrySegment]]:
    x, y = origin
    end = (x, y + span_pt) if vertical else (x + span_pt, y)
    line_id = f"line-{observation_id}{suffix}"
    w1 = f"w1-{observation_id}{suffix}"
    w2 = w1 if duplicate_witness else f"w2-{observation_id}{suffix}"
    endpoints = (origin, end) if status == BindingStatus.WITNESS_BOUND.value else None
    binding = DimensionAnchorBinding(
        observation_id=observation_id,
        status=status,
        dimension_line_id=line_id,
        witness_line_ids=(w1, w2),
        endpoints=endpoints,
    )
    line_start, line_end = line_override if line_override is not None else (origin, end)
    geometry = [
        ObservedGeometrySegment(
            segment_id=line_id,
            source_page=PAGE,
            start=line_start,
            end=line_end,
            coordinate_space=CoordinateSpace.PDF_POINTS.value,
            view_id=VIEWPORT_ID,
        )
    ]
    if vertical:
        geometry.extend(
            [
                ObservedGeometrySegment(
                    segment_id=w1,
                    source_page=PAGE,
                    start=(origin[0] - 20.0, origin[1]),
                    end=(origin[0] + 20.0, origin[1]),
                    view_id=VIEWPORT_ID,
                ),
                ObservedGeometrySegment(
                    segment_id=w2,
                    source_page=PAGE,
                    start=(end[0] - 20.0, end[1]),
                    end=(end[0] + 20.0, end[1]),
                    view_id=VIEWPORT_ID,
                ),
            ]
        )
    else:
        geometry.extend(
            [
                ObservedGeometrySegment(
                    segment_id=w1,
                    source_page=PAGE,
                    start=(origin[0], origin[1] - 20.0),
                    end=(origin[0], origin[1] + 20.0),
                    view_id=VIEWPORT_ID,
                ),
                ObservedGeometrySegment(
                    segment_id=w2,
                    source_page=PAGE,
                    start=(end[0], end[1] - 20.0),
                    end=(end[0], end[1] + 20.0),
                    view_id=VIEWPORT_ID,
                ),
            ]
        )
    return binding, geometry


def _bundle(
    pairs: list[tuple[DimensionObservation, DimensionAnchorBinding, list[ObservedGeometrySegment]]],
    *,
    extra_observations: list[DimensionObservation] | None = None,
    extra_geometry: list[ObservedGeometrySegment] | None = None,
) -> DimensionEvidenceBundle:
    return DimensionEvidenceBundle(
        observations=[pair[0] for pair in pairs] + list(extra_observations or []),
        bindings=[pair[1] for pair in pairs],
        observed_geometry=[
            segment for pair in pairs for segment in pair[2]
        ] + list(extra_geometry or []),
    )


def _run(bundle: DimensionEvidenceBundle, **kwargs):
    return resolve_figured_span_scale_shadow(
        bundle,
        scope=kwargs.get("scope", _scope()),
        context=kwargs.get("context", _context()),
        viewport=kwargs.get("viewport", _viewport()),
    )


def _pair(
    observation_id: str,
    physical_mm: float,
    *,
    ppm: float = 0.02835,
    origin: tuple[float, float] = (100.0, 120.0),
    vertical: bool = False,
    status: str = BindingStatus.WITNESS_BOUND.value,
    suffix: str = "",
):
    obs = _obs(observation_id, value=physical_mm)
    binding, geometry = _binding_and_geometry(
        observation_id,
        span_pt=physical_mm * ppm,
        origin=origin,
        vertical=vertical,
        status=status,
        suffix=suffix,
    )
    return obs, binding, geometry


def test_horizontal_unique_witness_bound_span_is_provisional_candidate() -> None:
    result = _run(_bundle([_pair("d1", 10000.0)]))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes == (FIGURED_SPAN_SCALE_SINGLE_CANDIDATE,)
    assert len(result.candidates) == 1
    assert len(result.independence_group_ids) == 1
    assert result.reconciliation_status == ScaleCalibrationStatus.PROVISIONAL.value
    assert math.isclose(result.candidates[0].points_per_mm or 0.0, 0.02835)
    assert result.quantity_m2 is None


def test_vertical_unique_witness_bound_span_is_provisional_candidate() -> None:
    result = _run(_bundle([_pair("d1", 8000.0, vertical=True)]))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.candidates) == 1
    assert math.isclose(result.candidates[0].points_per_mm or 0.0, 0.02835)


def test_two_independent_horizontal_mappings_agree_and_corroborate() -> None:
    result = _run(
        _bundle(
            [
                _pair("d1", 10000.0, origin=(100.0, 150.0)),
                _pair("d2", 5000.0, origin=(100.0, 300.0)),
            ]
        )
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (FIGURED_SPAN_SCALE_CORROBORATED,)
    assert len(result.candidates) == 2
    assert len(result.independence_group_ids) == 2


def test_independent_horizontal_and_vertical_mappings_corroborate() -> None:
    result = _run(
        _bundle(
            [
                _pair("horizontal", 10000.0, origin=(100.0, 150.0)),
                _pair("vertical", 5000.0, origin=(700.0, 200.0), vertical=True),
            ]
        )
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.independence_group_ids) == 2


def test_three_independent_compatible_mappings_are_deterministic() -> None:
    pairs = [
        _pair("a", 10000.0, origin=(100.0, 150.0)),
        _pair("b", 5000.0, origin=(100.0, 350.0)),
        _pair("c", 2000.0, origin=(600.0, 150.0), vertical=True),
    ]
    first = _run(_bundle(pairs))
    second = _run(_bundle(list(reversed(pairs))))
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert second.status is first.status
    assert len(first.independence_group_ids) == 3
    assert first.independence_group_ids == second.independence_group_ids
    assert tuple(c.candidate_id for c in first.candidates) == tuple(
        c.candidate_id for c in second.candidates
    )


def test_one_complete_plus_one_partial_leaves_one_candidate_only() -> None:
    complete = _pair("complete", 10000.0)
    partial = _pair(
        "partial",
        5000.0,
        origin=(100.0, 400.0),
        status=BindingStatus.PARTIAL_WITNESS.value,
    )
    result = _run(_bundle([complete, partial]))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.candidates) == 1
    assert len(result.rejected_candidates) == 1
    assert any(
        reason.startswith("binding_not_witness_bound")
        for reason in result.rejected_candidates[0].blocker_reasons
    )


def test_exact_duplicate_observation_collapses_without_corroborating() -> None:
    pair = _pair("dup", 10000.0)
    bundle = _bundle([pair])
    bundle.observations.append(deepcopy(pair[0]))
    result = _run(bundle)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.candidates) == 1
    assert result.candidates[0].duplicate_count == 2
    assert len(result.independence_group_ids) == 1


def test_same_dimension_line_does_not_count_as_independent() -> None:
    first = _pair("a", 10000.0)
    second_obs = _obs("b", value=10000.0)
    second_binding = deepcopy(first[1])
    second_binding.observation_id = "b"
    bundle = DimensionEvidenceBundle(
        observations=[first[0], second_obs],
        bindings=[first[1], second_binding],
        observed_geometry=first[2],
    )
    result = _run(bundle)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.candidates) == 2
    assert len(result.independence_group_ids) == 1


def test_two_fully_bound_disagreeing_mappings_conflict_and_retain_both() -> None:
    first = _pair("a", 10000.0, ppm=0.02835, origin=(100.0, 150.0))
    second = _pair("b", 10000.0, ppm=0.04000, origin=(100.0, 350.0))
    result = _run(_bundle([first, second]))
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (FIGURED_SPAN_SCALE_CONFLICT,)
    assert len(result.candidates) == 2
    assert len(result.independence_group_ids) == 2


def test_identical_text_value_on_unrelated_spans_does_not_collapse_by_value() -> None:
    first = _pair("a", 10000.0, ppm=0.02835, origin=(100.0, 150.0))
    second = _pair("b", 10000.0, ppm=0.02840, origin=(100.0, 350.0))
    result = _run(_bundle([first, second]))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.candidates) == 2
    assert len(result.independence_group_ids) == 2


def test_sibling_viewport_dimension_never_corroborates_owned_candidate() -> None:
    owned = _pair("owned", 10000.0)
    foreign_obs = _obs("foreign", value=5000.0, view_id="sibling")
    foreign_binding, foreign_geometry = _binding_and_geometry(
        "foreign",
        span_pt=141.75,
        origin=(100.0, 400.0),
    )
    foreign_geometry = [
        ObservedGeometrySegment(
            segment_id=segment.segment_id,
            source_page=segment.source_page,
            start=segment.start,
            end=segment.end,
            coordinate_space=segment.coordinate_space,
            view_id="sibling",
        )
        for segment in foreign_geometry
    ]
    result = _run(_bundle([owned, (foreign_obs, foreign_binding, foreign_geometry)]))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert len(result.candidates) == 1
    assert any(
        "observation_viewport_mismatch" in record.blocker_reasons
        for record in result.rejected_candidates
    )


def test_title_block_ratio_metadata_cannot_promote_one_figured_candidate() -> None:
    viewport = _viewport()
    viewport = ViewportEvidence(
        viewport_id=viewport.viewport_id,
        document_id=viewport.document_id,
        page_id=viewport.page_id,
        bbox=viewport.bbox,
        view_type=viewport.view_type,
        status=viewport.status,
        confidence=viewport.confidence,
        metadata={"scale_raw": "1:100", "scale_denominator": 100.0},
    )
    result = _run(_bundle([_pair("d1", 10000.0)]), viewport=viewport)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    bridge = build_figured_span_scale_calibration_shadow(
        physical_scale_result=result,
        scope=_scope(),
        context=_context(),
        viewport=viewport,
    )
    assert bridge.status is EvidenceResolutionStatus.ABSTAINED
    assert bridge.reason_codes[0] == FIGURED_SPAN_SCALE_CALIBRATION_UNAVAILABLE


@pytest.mark.parametrize(
    "raw_text",
    ["ROOM 12", "SHEET 12", "REV 2", "GRID A1", "1:100"],
)
def test_typed_non_dimension_tokens_abstain(raw_text: str) -> None:
    pair = _pair("noise", 1000.0)
    pair[0].raw_text = raw_text
    result = _run(_bundle([pair]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (FIGURED_SPAN_SCALE_UNAVAILABLE,)
    assert "typed_non_dimension_token" in result.rejected_candidates[0].blocker_reasons


def test_schedule_viewport_abstains_before_candidate_generation() -> None:
    result = _run(
        _bundle([_pair("d1", 10000.0)]),
        viewport=_viewport(view_type=DrawingViewType.SCHEDULE.value),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes[0] == FIGURED_SPAN_SCALE_SCOPE_MISMATCH
    assert "viewport_not_scale_bearing_drawing" in result.reason_codes


def test_duplicate_witness_ids_abstain() -> None:
    obs = _obs("d1", value=10000.0)
    binding, geometry = _binding_and_geometry(
        "d1",
        span_pt=283.5,
        duplicate_witness=True,
    )
    result = _run(_bundle([(obs, binding, geometry)]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "duplicated_witness" in result.rejected_candidates[0].blocker_reasons


def test_zero_length_native_span_abstains() -> None:
    obs = _obs("d1", value=10000.0)
    binding, geometry = _binding_and_geometry("d1", span_pt=0.0)
    result = _run(_bundle([(obs, binding, geometry)]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "native_span_invalid" in result.rejected_candidates[0].blocker_reasons


def test_invalid_negative_figured_value_abstains() -> None:
    obs = _obs("d1", value=-1000.0, raw_text="-1000")
    binding, geometry = _binding_and_geometry("d1", span_pt=28.35)
    result = _run(_bundle([(obs, binding, geometry)]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "invalid_figured_value" in result.rejected_candidates[0].blocker_reasons


def test_malformed_unit_abstains() -> None:
    obs = _obs("d1", value=10.0, unit="yards", raw_text="10yards")
    binding, geometry = _binding_and_geometry("d1", span_pt=283.5)
    result = _run(_bundle([(obs, binding, geometry)]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "malformed_unit" in result.rejected_candidates[0].blocker_reasons


def test_endpoint_outside_owned_viewport_abstains() -> None:
    obs = _obs("d1", value=10000.0)
    binding, geometry = _binding_and_geometry(
        "d1",
        span_pt=283.5,
        origin=(900.0, 120.0),
    )
    result = _run(_bundle([(obs, binding, geometry)]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "resolved_endpoints_outside_viewport" in result.rejected_candidates[0].blocker_reasons


def test_dimension_line_crossing_viewport_boundary_abstains() -> None:
    obs = _obs("d1", value=10000.0)
    binding, geometry = _binding_and_geometry(
        "d1",
        span_pt=283.5,
        line_override=((-10.0, 120.0), (400.0, 120.0)),
    )
    result = _run(_bundle([(obs, binding, geometry)]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "dimension_line_crosses_viewport" in result.rejected_candidates[0].blocker_reasons


def test_stale_revision_abstains() -> None:
    result = _run(
        _bundle([_pair("d1", 10000.0)]),
        context=_context(revision_id="rev-1", current_revision_id="rev-2"),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "stale_revision" in result.reason_codes


def test_wrong_source_sha_abstains() -> None:
    result = _run(
        _bundle([_pair("d1", 10000.0)]),
        scope=_scope(source_sha256="b" * 64),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "source_sha256_mismatch" in result.reason_codes


def test_derived_viewport_is_not_accepted_as_exact_scale_ownership() -> None:
    result = _run(
        _bundle([_pair("d1", 10000.0)]),
        viewport=_viewport(status=ViewportResolutionStatus.DERIVED),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "viewport_not_resolved" in result.reason_codes


def test_translation_and_90_and_180_rotation_preserve_mapping() -> None:
    base = _run(_bundle([_pair("d1", 10000.0, origin=(100.0, 120.0))]))
    rot90 = _run(_bundle([_pair("d1", 10000.0, origin=(700.0, 100.0), vertical=True)]))

    obs = _obs("d1", value=10000.0)
    binding, geometry = _binding_and_geometry(
        "d1",
        span_pt=283.5,
        origin=(700.0, 700.0),
    )
    binding.endpoints = (binding.endpoints[1], binding.endpoints[0])
    geometry[0] = ObservedGeometrySegment(
        segment_id=geometry[0].segment_id,
        source_page=PAGE,
        start=geometry[0].end,
        end=geometry[0].start,
        view_id=VIEWPORT_ID,
    )
    rot180 = _run(_bundle([(obs, binding, geometry)]))

    assert base.status is rot90.status is rot180.status
    assert math.isclose(base.candidates[0].points_per_mm or 0.0, rot90.candidates[0].points_per_mm or 0.0)
    assert math.isclose(base.candidates[0].points_per_mm or 0.0, rot180.candidates[0].points_per_mm or 0.0)


def test_uniform_coordinate_scale_changes_mapping_by_same_factor() -> None:
    base = _run(_bundle([_pair("d1", 10000.0, ppm=0.02835)]))
    scaled = _run(_bundle([_pair("d1", 10000.0, ppm=0.05670)]))
    assert base.status is scaled.status
    assert math.isclose(
        (scaled.candidates[0].points_per_mm or 0.0)
        / (base.candidates[0].points_per_mm or 1.0),
        2.0,
    )


def test_unrelated_content_and_segment_splitting_do_not_change_result() -> None:
    pair = _pair("d1", 10000.0)
    base = _run(_bundle([pair]))
    extras = [
        ObservedGeometrySegment(
            segment_id="unrelated-a",
            source_page=PAGE,
            start=(800.0, 800.0),
            end=(850.0, 800.0),
            view_id=VIEWPORT_ID,
        ),
        ObservedGeometrySegment(
            segment_id="unrelated-b",
            source_page=PAGE,
            start=(850.0, 800.0),
            end=(900.0, 800.0),
            view_id=VIEWPORT_ID,
        ),
    ]
    expanded = _run(_bundle([pair], extra_geometry=extras))
    assert expanded.status is base.status
    assert expanded.candidates == base.candidates


def test_viewport_expansion_without_ownership_change_preserves_stable_ids() -> None:
    bundle = _bundle([_pair("d1", 10000.0)])
    base = _run(bundle)
    expanded = _run(bundle, viewport=_viewport(bbox=(-10.0, -10.0, 1010.0, 1010.0)))
    assert expanded.status is base.status
    assert tuple(c.candidate_id for c in expanded.candidates) == tuple(
        c.candidate_id for c in base.candidates
    )


def test_deterministic_replay_input_order_and_no_mutation() -> None:
    pairs = [
        _pair("a", 10000.0, origin=(100.0, 150.0)),
        _pair("b", 5000.0, origin=(100.0, 350.0)),
    ]
    bundle = _bundle(pairs)
    before = deepcopy(bundle)
    first = _run(bundle)
    replay = _run(bundle)
    reordered = DimensionEvidenceBundle(
        observations=list(reversed(bundle.observations)),
        bindings=list(reversed(bundle.bindings)),
        observed_geometry=list(reversed(bundle.observed_geometry)),
    )
    reordered_result = _run(reordered)
    assert bundle == before
    assert first == replay
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert reordered_result.status is first.status
    assert tuple(c.candidate_id for c in reordered_result.candidates) == tuple(
        c.candidate_id for c in first.candidates
    )


def test_corroborated_evidence_routes_to_canonical_resolver_without_firm_promotion() -> None:
    physical = _run(
        _bundle(
            [
                _pair("a", 10000.0, origin=(100.0, 150.0)),
                _pair("b", 5000.0, origin=(100.0, 350.0)),
            ]
        )
    )
    bridge = build_figured_span_scale_calibration_shadow(
        physical_scale_result=physical,
        scope=_scope(),
        context=_context(),
        viewport=_viewport(),
    )
    assert bridge.status is EvidenceResolutionStatus.CORROBORATED
    assert bridge.reason_codes == (FIGURED_SPAN_SCALE_CALIBRATION_RESOLVED,)
    assert bridge.calibration is not None
    assert bridge.calibration.source_type == ScaleSourceType.INFERRED.value
    assert bridge.calibration.status == ScaleCalibrationStatus.PROVISIONAL.value
    assert bridge.measurement_authority == AuthorityStatus.PROVISIONAL.value
    assert bridge.scale_fingerprint


def test_single_candidate_never_enters_canonical_bridge() -> None:
    physical = _run(_bundle([_pair("a", 10000.0)]))
    bridge = build_figured_span_scale_calibration_shadow(
        physical_scale_result=physical,
        scope=_scope(),
        context=_context(),
        viewport=_viewport(),
    )
    assert bridge.status is EvidenceResolutionStatus.ABSTAINED
    assert bridge.calibration is None
    assert bridge.measurement_authority == AuthorityStatus.BLOCKED.value


def test_title_block_plus_one_figured_span_stays_provisional_outside_bridge() -> None:
    physical = _run(_bundle([_pair("a", 10000.0)]))
    assert physical.status is EvidenceResolutionStatus.CANDIDATE
    candidate_reading = ScaleSourceReading(
        source_type=ScaleSourceType.INFERRED.value,
        scale_text="figured",
        ratio=100.0,
        confidence=1.0,
    )
    calibration = resolve_page_scale_calibration(
        page_no=PAGE,
        sheet_label="test",
        readings=[
            ScaleSourceReading(
                source_type=ScaleSourceType.TITLE_BLOCK.value,
                scale_text="1:100",
                ratio=100.0,
                confidence=1.0,
            ),
            candidate_reading,
        ],
        revision_id="rev-1",
    )
    assert measurement_authority_for_page_scale(calibration) == AuthorityStatus.PROVISIONAL.value
