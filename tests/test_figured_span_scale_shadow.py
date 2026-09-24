from __future__ import annotations

from copy import deepcopy
import math

from pb_dimension_graph_constraint_engine import DimensionObservation
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionAnchorBinding,
    DimensionEvidenceBundle,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_figured_span_scale_shadow import (
    FIGURED_SPAN_SCALE_CONFLICT,
    FIGURED_SPAN_SCALE_CORROBORATED,
    FIGURED_SPAN_SCALE_SCOPE_CONFLICT,
    FIGURED_SPAN_SCALE_SINGLE_CANDIDATE,
    FIGURED_SPAN_SCALE_UNAVAILABLE,
    FiguredSpanScaleScope,
    resolve_figured_span_scale_shadow,
)


SHA = "a" * 64


def _scope() -> FiguredSpanScaleScope:
    return FiguredSpanScaleScope(
        document_id="doc",
        revision_id="rev-1",
        source_sha256=SHA,
        page_no=41,
        viewport_id="elevation-a",
    )


def _obs(
    observation_id: str,
    *,
    value_mm: float,
    view_id: str = "elevation-a",
    authority: str = MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
    confidence: float = 1.0,
) -> DimensionObservation:
    return DimensionObservation(
        dimension_id=observation_id,
        source_page=41,
        view_id=view_id,
        raw_text=f"{value_mm:g}",
        value=value_mm,
        unit="mm",
        authority=authority,
        confidence=confidence,
    )


def _binding(
    observation_id: str,
    *,
    span_pt: float,
    origin: tuple[float, float] = (10.0, 20.0),
    vertical: bool = False,
    status: str = BindingStatus.WITNESS_BOUND.value,
    suffix: str = "",
) -> DimensionAnchorBinding:
    x, y = origin
    end = (x, y + span_pt) if vertical else (x + span_pt, y)
    return DimensionAnchorBinding(
        observation_id=observation_id,
        status=status,
        dimension_line_id=f"dim-line-{observation_id}{suffix}",
        witness_line_ids=(f"w1-{observation_id}{suffix}", f"w2-{observation_id}{suffix}"),
        endpoints=(origin, end) if status == BindingStatus.WITNESS_BOUND.value else None,
    )


def _bundle(*pairs: tuple[DimensionObservation, DimensionAnchorBinding]) -> DimensionEvidenceBundle:
    return DimensionEvidenceBundle(
        observations=[pair[0] for pair in pairs],
        bindings=[pair[1] for pair in pairs],
    )


def test_single_witness_bound_span_stays_candidate_only() -> None:
    span = 453.6
    result = resolve_figured_span_scale_shadow(
        _bundle((_obs("d1", value_mm=16000.0), _binding("d1", span_pt=span))),
        scope=_scope(),
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes == (FIGURED_SPAN_SCALE_SINGLE_CANDIDATE,)
    assert len(result.candidates) == 1
    assert math.isclose(result.candidates[0].points_per_mm, span / 16000.0)
    assert result.quantity_m2 is None


def test_two_independent_agreeing_spans_are_corroborated_but_not_promoted() -> None:
    ppm = 0.02835
    result = resolve_figured_span_scale_shadow(
        _bundle(
            (_obs("long", value_mm=16000.0), _binding("long", span_pt=ppm * 16000.0)),
            (_obs("short", value_mm=8200.0), _binding("short", span_pt=ppm * 8200.0, vertical=True)),
        ),
        scope=_scope(),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (FIGURED_SPAN_SCALE_CORROBORATED,)
    assert len(result.candidates) == 2
    assert {round(c.points_per_mm, 10) for c in result.candidates} == {round(ppm, 10)}
    assert result.quantity_m2 is None


def test_competing_physical_mappings_retain_both_and_conflict() -> None:
    result = resolve_figured_span_scale_shadow(
        _bundle(
            (_obs("d1", value_mm=10000.0), _binding("d1", span_pt=283.5)),
            (_obs("d2", value_mm=10000.0), _binding("d2", span_pt=210.0, vertical=True)),
        ),
        scope=_scope(),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (FIGURED_SPAN_SCALE_CONFLICT,)
    assert len(result.candidates) == 2


def test_partial_ambiguous_and_non_documented_evidence_cannot_mint_candidate() -> None:
    partial = _binding("partial", span_pt=100.0, status=BindingStatus.PARTIAL_WITNESS.value)
    ambiguous = _binding("ambiguous", span_pt=100.0, status=BindingStatus.AMBIGUOUS.value)
    ai_obs = _obs("ai", value_mm=5000.0, authority="ai_detected")
    result = resolve_figured_span_scale_shadow(
        _bundle(
            (_obs("partial", value_mm=5000.0), partial),
            (_obs("ambiguous", value_mm=5000.0), ambiguous),
            (ai_obs, _binding("ai", span_pt=141.75)),
        ),
        scope=_scope(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (FIGURED_SPAN_SCALE_UNAVAILABLE,)
    assert result.candidates == ()


def test_cross_viewport_evidence_is_not_borrowed() -> None:
    result = resolve_figured_span_scale_shadow(
        _bundle(
            (
                _obs("foreign", value_mm=10000.0, view_id="elevation-b"),
                _binding("foreign", span_pt=283.5),
            )
        ),
        scope=_scope(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (FIGURED_SPAN_SCALE_UNAVAILABLE,)


def test_duplicate_binding_identity_fails_closed() -> None:
    obs = _obs("dup", value_mm=10000.0)
    bundle = DimensionEvidenceBundle(
        observations=[obs],
        bindings=[
            _binding("dup", span_pt=283.5, suffix="-a"),
            _binding("dup", span_pt=283.5, suffix="-b"),
        ],
    )
    result = resolve_figured_span_scale_shadow(bundle, scope=_scope())
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (FIGURED_SPAN_SCALE_SCOPE_CONFLICT,)
    assert len(result.candidates) == 2


def test_duplicate_observation_identity_retains_distinct_alternatives() -> None:
    binding = _binding("dup-obs", span_pt=283.5)
    bundle = DimensionEvidenceBundle(
        observations=[
            _obs("dup-obs", value_mm=10000.0),
            _obs("dup-obs", value_mm=9000.0),
        ],
        bindings=[binding],
    )
    result = resolve_figured_span_scale_shadow(bundle, scope=_scope())
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.reason_codes == (FIGURED_SPAN_SCALE_SCOPE_CONFLICT,)
    assert len(result.candidates) == 2


def test_translation_rotation_endpoint_order_and_uniform_scale_metamorphics() -> None:
    base_obs = _obs("d1", value_mm=10000.0)
    base = resolve_figured_span_scale_shadow(
        _bundle((base_obs, _binding("d1", span_pt=283.5))),
        scope=_scope(),
    )

    rotated = DimensionAnchorBinding(
        observation_id="d1",
        status=BindingStatus.WITNESS_BOUND.value,
        dimension_line_id="dim-line-d1",
        witness_line_ids=("w2-d1", "w1-d1"),
        endpoints=((1100.0, 2283.5), (1100.0, 2000.0)),
    )
    transformed = resolve_figured_span_scale_shadow(
        _bundle((deepcopy(base_obs), rotated)),
        scope=_scope(),
    )

    scaled_obs = _obs("d1", value_mm=20000.0)
    scaled_binding = _binding("d1", span_pt=567.0, origin=(300.0, 400.0), vertical=True)
    uniformly_scaled = resolve_figured_span_scale_shadow(
        _bundle((scaled_obs, scaled_binding)),
        scope=_scope(),
    )

    assert base.status is transformed.status is uniformly_scaled.status
    assert math.isclose(base.candidates[0].points_per_mm, transformed.candidates[0].points_per_mm)
    assert math.isclose(base.candidates[0].points_per_mm, uniformly_scaled.candidates[0].points_per_mm)


def test_input_order_unrelated_content_replay_and_no_mutation() -> None:
    ppm = 0.02835
    pair_a = (_obs("a", value_mm=16000.0), _binding("a", span_pt=ppm * 16000.0))
    pair_b = (_obs("b", value_mm=8200.0), _binding("b", span_pt=ppm * 8200.0, vertical=True))
    bundle = _bundle(pair_a, pair_b)
    bundle.observations.append(_obs("noise", value_mm=1234.0, view_id="other-view"))
    before = deepcopy(bundle)

    first = resolve_figured_span_scale_shadow(bundle, scope=_scope())
    replay = resolve_figured_span_scale_shadow(bundle, scope=_scope())
    reordered = DimensionEvidenceBundle(
        observations=list(reversed(bundle.observations)),
        bindings=list(reversed(bundle.bindings)),
    )
    reordered_result = resolve_figured_span_scale_shadow(reordered, scope=_scope())

    assert bundle == before
    assert first == replay
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert reordered_result.status is first.status
    assert tuple(c.candidate_id for c in reordered_result.candidates) == tuple(
        c.candidate_id for c in first.candidates
    )
