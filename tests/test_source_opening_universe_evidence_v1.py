"""tests/test_source_opening_universe_evidence_v1.py — Comprehensive adversarial tests.

Validates the clean, evidence-first opening candidate authority across all required edge cases:
1. One arc with no tag -> UNRESOLVED (never assumes D1).
2. One arc beside D1 with authenticated relation -> PROVEN_SAME (binds unambiguously).
3. Tag binding rejected when viewport unauthenticated.
4. Tag binding rejected when revision mismatched.
5. Tag binding filters incompatible semantic trade tags (e.g. W1 ignored for door swing).
6. One arc beside two plausible tags -> UNRESOLVED (fails closed).
7. Two equal doors at distinct locations -> PROVEN_DISTINCT.
8. Coincident detections at same location with shared lineage -> PROVEN_SAME.
9. Logo cubic -> rejected by context filter / viewport boundary.
10. Furniture arc -> rejected (not hosted at wall jamb).
11. Sanitary arc -> rejected (sanitary fixture context/layers).
12. Schedule sample door vs plan opening -> UNRESOLVED (different context kinds not comparable for physical instance identity).
13. Window detail card -> rejected by viewport view-class authority.
14. Dimension-chain window with no type mark -> UNRESOLVED (never assumes W1/W2).
15. Two possible W-tags -> UNRESOLVED (fails closed).
16. Duplicate plan/elevation observations -> UNRESOLVED (different context kinds).
17. Same opening in plan and schedule -> UNRESOLVED (different context kinds).
18. Distinct equal-size openings -> PROVEN_DISTINCT, count is 2.
19. Viewport validation: uncropped floor plan -> accepted.
20. Viewport validation: cropped viewport -> rejected (fails closed).
21. Viewport validation: unsegmented viewport -> rejected (fails closed).
22. Viewport validation: uncorroborated view class -> rejected (fails closed).
23. Upstream opening-universe completeness authority integration (decode complete vs partial).
24. Statistically grounded tolerance: physical scale/stroke derivation.
25. Statistically grounded tolerance: sample size rules (N<10 fail-closed, 10<=N<30 MAD k=2.576, N>=30 empirical p99).
26. Forbidden pattern from PR #534: detector output directly marked CORROBORATED is rejected.
27. Lineage preservation: conversion to upstream CandidateSemanticOpening contract.
28. Orientation / aspect ratio difference inside tolerance does NOT create physical distinctness -> UNRESOLVED.
29. Nearby openings with conflicting tags inside tolerance -> UNRESOLVED (conflicting annotations).
30. Nearby openings with conflicting patterns inside tolerance -> UNRESOLVED (differing detector modalities).
31. Nearby candidates with disjoint lineage inside tolerance -> UNRESOLVED.
32. Regression Matrix Tests 1 to 14.
33. Reviewer Mutation Tests (17 tests covering candidate ID enforcement, typed tag bindings, required safety inputs, viewport authority, and conservative physical distinctness).
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessProducer,
    OpeningUniverseCompletenessRecord,
    OpeningUniverseScope,
    OpeningUniverseSelector,
    SourceEnumerationState,
    build_opening_universe_member_from_indexed_primitive,
    build_opening_universe_scope,
)
from pb_physical_opening_authority import (
    CandidateSemanticOpening,
    PhysicalOpeningIdentityResult,
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PHYSICAL_OPENING_IDENTITY_RESOLVED,
    PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
)
from pb_source_observation_authority import SourceDecodeCoverageRecord
from pb_source_opening_candidate_authority import (
    AuthenticatedViewportDecision,
    CandidateContextFilter,
    IdentityState,
    OpeningIdentityResolver,
    OpeningTagBindingResult,
    PhysicalOpeningCandidateRecord,
    SourceToleranceProvenance,
    TagBindingEvidence,
    TagBindingRelationKind,
    TagObservation,
    create_opening_candidate,
    derive_deterministic_candidate_id,
    validate_opening_decision_viewport,
)
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_DETAIL,
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    VIEW_KIND_SCHEDULE,
    VIEW_KIND_SECTION,
    ViewportViewClassAuthority,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)


@pytest.fixture
def sample_tolerance() -> SourceToleranceProvenance:
    """Fixture providing source-derived tolerance from scale 1:100 and 0.7pt stroke width."""
    return SourceToleranceProvenance.from_scale_and_stroke(
        scale_ratio=100.0,
        stroke_width_pt=0.7,
        scale_residual_mm=1.5,
        raster_dpi=300.0,
    )


@pytest.fixture
def floor_plan_selector() -> ViewportViewClassSelector:
    """Fixture providing selector for test floor plan viewport."""
    return ViewportViewClassSelector(
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        viewport_id="vp_floor_plan_p1",
    )


@pytest.fixture
def sample_segmented_viewport() -> SegmentedViewport:
    """Fixture providing an authenticated floor-plan viewport."""
    return SegmentedViewport(
        view_id="vp_floor_plan_p1",
        page_number=1,
        view_type="floor_plan",
        label="GROUND FLOOR PLAN",
        title_bbox=(50.0, 50.0, 200.0, 70.0),
        bounding_box=(0.0, 0.0, 1000.0, 1000.0),
        status="resolved",
        boundary_source="vector_frame",
        confidence=1.0,
    )


@pytest.fixture
def sample_view_class_authority(
    floor_plan_selector: ViewportViewClassSelector,
) -> ViewportViewClassAuthority:
    """Fixture providing view-class authority with authenticated floor plan."""
    producer = ViewportViewClassProducer.create()
    producer.publish(
        floor_plan_selector,
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=("obs_view_title_01",),
    )
    return producer.authority()


@pytest.fixture
def sample_viewport_decision(
    sample_segmented_viewport: SegmentedViewport,
) -> AuthenticatedViewportDecision:
    """Fixture providing an authenticated viewport decision."""
    return AuthenticatedViewportDecision(
        viewport=sample_segmented_viewport,
        view_kind=VIEW_KIND_FLOOR_PLAN,
        status=EvidenceResolutionStatus.CORROBORATED,
        is_uncropped=True,
    )


_candidate_counter = 0


def make_candidate(
    *,
    document_id: str = "doc_test",
    revision_id: str = "rev_test_01",
    source_sha256: str = "a" * 64,
    snapshot_id: str = "snap_01",
    page_id: str = "page_1",
    viewport_id: str = "vp_floor_plan_p1",
    geometry: Tuple[float, float, float, float] = (100.0, 100.0, 140.0, 140.0),
    structural_pattern: str = "door_swing_arc",
    context_kind: str = "floor_plan_opening",
    source_observation_ids: Optional[Sequence[str]] = None,
    source_lineage_root_ids: Optional[Sequence[str]] = None,
    tolerance_provenance: Optional[SourceToleranceProvenance] = None,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE,
    tag_binding: Optional[OpeningTagBindingResult] = None,
    dimension_mm: Optional[Tuple[float, float]] = None,
    semantic_family: str = "openings",
    reason_codes: Sequence[str] = (),
) -> PhysicalOpeningCandidateRecord:
    """Helper to construct PhysicalOpeningCandidateRecord with unique lineage and valid deterministic candidate_id."""
    global _candidate_counter
    _candidate_counter += 1
    if source_observation_ids is None:
        source_observation_ids = (f"obs_unique_{_candidate_counter}",)
    if source_lineage_root_ids is None:
        source_lineage_root_ids = (f"root_unique_{_candidate_counter}",)

    if tolerance_provenance is None:
        tolerance_provenance = SourceToleranceProvenance.from_scale_and_stroke(
            scale_ratio=100.0,
            stroke_width_pt=0.7,
            scale_residual_mm=1.5,
            raster_dpi=300.0,
        )
    cid = derive_deterministic_candidate_id(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        geometry=geometry,
        structural_pattern=structural_pattern,
        source_observation_ids=source_observation_ids,
        source_lineage_root_ids=source_lineage_root_ids,
    )
    return PhysicalOpeningCandidateRecord(
        candidate_id=cid,
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        geometry=geometry,
        structural_pattern=structural_pattern,
        context_kind=context_kind,
        source_observation_ids=tuple(source_observation_ids),
        source_lineage_root_ids=tuple(source_lineage_root_ids),
        tolerance_provenance=tolerance_provenance,
        status=status,
        tag_binding=tag_binding,
        dimension_mm=dimension_mm,
        semantic_family=semantic_family,
        reason_codes=tuple(reason_codes),
    )


def make_tag_obs(
    *,
    tag_text: str = "D1",
    center: Tuple[float, float] = (120.0, 120.0),
    observation_id: str = "obs_tag_01",
    document_id: str = "doc_test",
    revision_id: str = "rev_test_01",
    source_sha256: str = "a" * 64,
    snapshot_id: str = "snap_01",
    page_id: str = "page_1",
    viewport_id: str = "vp_floor_plan_p1",
    source_observation_ids: Sequence[str] = (),
    source_lineage_root_ids: Sequence[str] = (),
) -> TagObservation:
    """Helper to construct TagObservation with authentic scope."""
    cx, cy = center
    bbox = (cx - 5.0, cy - 5.0, cx + 5.0, cy + 5.0)
    return TagObservation(
        observation_id=observation_id,
        raw_tag_text=tag_text,
        bounding_box=bbox,
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        source_observation_ids=tuple(source_observation_ids),
        source_lineage_root_ids=tuple(source_lineage_root_ids),
    )


# ---------------------------------------------------------------------------
# Edge Case 1: One arc with no tag -> UNRESOLVED (never assumes D1)
# ---------------------------------------------------------------------------
def test_one_arc_with_no_tag_remains_unresolved() -> None:
    candidate = make_candidate()
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
    assert "no_tag_evidence_present" in result.reason_codes
    assert result.bound_tag != "D1"


# ---------------------------------------------------------------------------
# Edge Case 2: One arc beside D1 with relation -> PROVEN_SAME (unambiguous)
# ---------------------------------------------------------------------------
def test_one_arc_beside_d1_binds_unambiguously() -> None:
    candidate = make_candidate()
    tag_obs = make_tag_obs(tag_text="D1", center=(122.0, 121.0), observation_id="tag_obs_d1")
    evidence = TagBindingEvidence(
        tag_observation_id="tag_obs_d1",
        candidate_id=candidate.candidate_id,
        relation_kind=TagBindingRelationKind.LEADER_TO_OPENING,
    )
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[tag_obs],
        binding_evidences=[evidence],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.PROVEN_SAME
    assert result.bound_tag == "D1"
    assert "authenticated_tag_relation_proven" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 3: Tag binding rejected when viewport unauthenticated
# ---------------------------------------------------------------------------
def test_tag_binding_rejected_when_viewport_unauthenticated() -> None:
    candidate = make_candidate()
    tag_obs = make_tag_obs(tag_text="D1", center=(122.0, 121.0))
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[tag_obs],
        expected_semantic_family="doors",
        viewport_authenticated=False,  # Unauthenticated!
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
    assert "unauthenticated_viewport_blocks_tag_binding" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 4: Tag binding rejected when revision mismatched
# ---------------------------------------------------------------------------
def test_tag_binding_rejected_when_revision_mismatched() -> None:
    candidate = make_candidate()
    tag_obs = make_tag_obs(tag_text="D1", center=(122.0, 121.0))
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[tag_obs],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=False,  # Mismatched!
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
    assert "revision_mismatch_blocks_tag_binding" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 5: Tag binding semantic family filtering
# ---------------------------------------------------------------------------
def test_tag_binding_semantic_family_filtering() -> None:
    candidate = make_candidate()
    tag_w = make_tag_obs(tag_text="W1", center=(122.0, 121.0), observation_id="obs_w1")
    result_window_tag = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[tag_w],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result_window_tag.identity_state == IdentityState.UNRESOLVED
    assert result_window_tag.bound_tag is None

    tag_d = make_tag_obs(tag_text="D1", center=(120.0, 120.0), observation_id="obs_d1")
    evidence = TagBindingEvidence(
        tag_observation_id="obs_d1",
        candidate_id=candidate.candidate_id,
        relation_kind=TagBindingRelationKind.EXPLICIT_APERTURE_TAG,
    )
    result_both = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[tag_w, tag_d],
        binding_evidences=[evidence],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result_both.identity_state == IdentityState.PROVEN_SAME
    assert result_both.bound_tag == "D1"


# ---------------------------------------------------------------------------
# Edge Case 6: One arc beside two plausible tags -> UNRESOLVED (fails closed)
# ---------------------------------------------------------------------------
def test_one_arc_beside_two_plausible_tags_fails_closed() -> None:
    candidate = make_candidate()
    tag_1 = make_tag_obs(tag_text="D1", center=(121.0, 120.0), observation_id="obs_d1")
    tag_2 = make_tag_obs(tag_text="D2", center=(120.0, 122.0), observation_id="obs_d2")
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[tag_1, tag_2],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
    assert "competing_tags_ambiguous" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 7: Two equal doors -> PROVEN_DISTINCT
# ---------------------------------------------------------------------------
def test_two_equal_doors_are_proven_distinct() -> None:
    cand_1 = make_candidate(geometry=(100.0, 100.0, 140.0, 140.0))
    cand_2 = make_candidate(geometry=(300.0, 100.0, 340.0, 140.0))
    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "distinct_physical_locations" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 8: Coincident detections at same location with shared lineage -> PROVEN_SAME
# ---------------------------------------------------------------------------
def test_coincident_detections_are_proven_same() -> None:
    cand_1 = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        source_lineage_root_ids=("root_shared_01",),
    )
    cand_2 = make_candidate(
        geometry=(100.2, 100.2, 140.2, 140.2),  # 0.28 pt delta, well within tolerance
        source_lineage_root_ids=("root_shared_01",),  # Shared lineage!
    )
    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    assert result.proven_same is True
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_RESOLVED
    assert "shared_authenticated_lineage_with_coincident_geometry" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 9: Logo cubic -> rejected by context filter / viewport boundary
# ---------------------------------------------------------------------------
def test_logo_cubic_rejected_by_context_filter() -> None:
    viewport_bbox = (50.0, 50.0, 750.0, 550.0)
    title_block_bbox = (600.0, 480.0, 750.0, 550.0)
    logo_cubic_bbox = (650.0, 500.0, 670.0, 520.0)
    assert CandidateContextFilter.is_title_block_or_logo(logo_cubic_bbox, viewport_bbox, title_block_bbox) is True
    outside_bbox = (10.0, 10.0, 30.0, 30.0)
    assert CandidateContextFilter.is_title_block_or_logo(outside_bbox, viewport_bbox) is True


# ---------------------------------------------------------------------------
# Edge Case 10: Furniture arc -> rejected (not a wall opening)
# ---------------------------------------------------------------------------
def test_furniture_arc_rejected() -> None:
    wall_lines = [(100.0, 0.0, 100.0, 400.0)]
    is_furniture = CandidateContextFilter.is_furniture_arc(
        arc_center=(250.0, 200.0),
        arc_radius=20.0,
        wall_lines=wall_lines,
        tolerance_pt=5.0,
    )
    assert is_furniture is True

    is_door_furniture = CandidateContextFilter.is_furniture_arc(
        arc_center=(100.0, 150.0),
        arc_radius=35.0,
        wall_lines=wall_lines,
        tolerance_pt=5.0,
    )
    assert is_door_furniture is False


# ---------------------------------------------------------------------------
# Edge Case 11: Sanitary arc -> rejected (sanitary fixture context)
# ---------------------------------------------------------------------------
def test_sanitary_arc_rejected() -> None:
    assert CandidateContextFilter.is_sanitary_fixture("arc", layer="A-FIXT-SANITARY") is True
    assert CandidateContextFilter.is_sanitary_fixture("arc", nearby_text="WC 01") is True
    assert CandidateContextFilter.is_sanitary_fixture("arc", nearby_text="Wash Hand Basin") is True
    assert CandidateContextFilter.is_sanitary_fixture("arc", layer="A-WALL", nearby_text="D1") is False


# ---------------------------------------------------------------------------
# Edge Case 12: Schedule sample door -> UNRESOLVED for physical instance identity
# ---------------------------------------------------------------------------
def test_schedule_sample_door_proven_distinct() -> None:
    schedule_sample = make_candidate(
        page_id="page_2",
        viewport_id="vp_sched_01",
        context_kind="schedule_sample",
    )
    plan_instance = make_candidate(
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        context_kind="floor_plan_opening",
    )
    result = OpeningIdentityResolver.compare_candidates(schedule_sample, plan_instance)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "different_context_kinds_not_comparable_for_physical_instance_identity" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 13: Window detail card -> rejected (non-floor-plan detail viewport)
# ---------------------------------------------------------------------------
def test_window_detail_card_rejected() -> None:
    detail_selector = ViewportViewClassSelector(
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        viewport_id="vp_detail_win_01",
    )
    producer = ViewportViewClassProducer.create()
    producer.publish(
        detail_selector,
        view_kind=VIEW_KIND_DETAIL,
        evidence_observation_ids=("obs_detail_title_01",),
    )
    auth = producer.authority()

    vp_detail = SegmentedViewport(
        view_id="vp_detail_win_01",
        page_number=3,
        view_type="detail",
        label="WINDOW DETAIL W1",
        title_bbox=(50.0, 50.0, 200.0, 70.0),
        bounding_box=(50.0, 50.0, 400.0, 400.0),
        status="resolved",
        boundary_source="vector_frame",
        confidence=1.0,
    )

    is_valid, reason = validate_opening_decision_viewport(
        viewport=vp_detail,
        view_class_authority=auth,
        selector=detail_selector,
    )
    assert is_valid is False
    assert "non_floor_plan_view_kind_detail" in reason


# ---------------------------------------------------------------------------
# Edge Case 14: Dimension-chain window with no type mark -> UNRESOLVED
# ---------------------------------------------------------------------------
def test_dimension_chain_window_with_no_type_mark() -> None:
    candidate = make_candidate(
        structural_pattern="dimension_chain_opening",
        geometry=(200.0, 100.0, 260.0, 120.0),
        dimension_mm=(1500.0, 1200.0),
        semantic_family="windows",
    )
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[],
        expected_semantic_family="windows",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
    assert result.bound_tag not in ("W1", "W2")


# ---------------------------------------------------------------------------
# Edge Case 15: Two possible W-tags -> UNRESOLVED (fails closed)
# ---------------------------------------------------------------------------
def test_two_possible_wtags_fails_closed() -> None:
    candidate = make_candidate(
        structural_pattern="dimension_chain_opening",
        geometry=(200.0, 100.0, 260.0, 120.0),
        dimension_mm=(1500.0, 1200.0),
        semantic_family="windows",
    )
    tag_1 = make_tag_obs(tag_text="W1", center=(231.0, 110.0), observation_id="obs_w1")
    tag_2 = make_tag_obs(tag_text="W2", center=(230.0, 111.0), observation_id="obs_w2")
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[tag_1, tag_2],
        expected_semantic_family="windows",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
    assert "competing_tags_ambiguous" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 16: Duplicate plan/elevation observations -> UNRESOLVED context kinds
# ---------------------------------------------------------------------------
def test_duplicate_plan_elevation_observations() -> None:
    plan_cand = make_candidate(
        context_kind="floor_plan_opening",
        geometry=(200.0, 100.0, 260.0, 120.0),
        structural_pattern="dimension_chain_opening",
    )
    elev_cand = make_candidate(
        page_id="page_2",
        viewport_id="vp_elev_01",
        context_kind="elevation_opening",
        geometry=(200.0, 300.0, 260.0, 350.0),
        structural_pattern="elevation_opening_symbol",
    )
    result = OpeningIdentityResolver.compare_candidates(plan_cand, elev_cand)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "different_context_kinds_not_comparable_for_physical_instance_identity" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 17: Same opening in plan and schedule -> distinct contexts
# ---------------------------------------------------------------------------
def test_same_opening_in_plan_and_schedule() -> None:
    plan_cand = make_candidate(context_kind="floor_plan_opening")
    sched_row = make_candidate(
        page_id="page_3",
        viewport_id="vp_sched_01",
        context_kind="schedule_specification",
        structural_pattern="schedule_row",
    )
    result = OpeningIdentityResolver.compare_candidates(plan_cand, sched_row)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "different_context_kinds_not_comparable_for_physical_instance_identity" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 18: Distinct equal-size openings -> PROVEN_DISTINCT
# ---------------------------------------------------------------------------
def test_distinct_equal_size_openings_proven_distinct() -> None:
    win_a = make_candidate(
        geometry=(100.0, 50.0, 160.0, 60.0),
        structural_pattern="dimension_chain_opening",
        dimension_mm=(1500.0, 1200.0),
    )
    win_b = make_candidate(
        geometry=(250.0, 50.0, 310.0, 60.0),
        structural_pattern="dimension_chain_opening",
        dimension_mm=(1500.0, 1200.0),
    )
    result = OpeningIdentityResolver.compare_candidates(win_a, win_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "distinct_physical_locations" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 19: Viewport validation: uncropped floor plan -> accepted
# ---------------------------------------------------------------------------
def test_validate_opening_decision_viewport_unccropped_floor_plan(
    sample_segmented_viewport: SegmentedViewport,
    sample_view_class_authority: ViewportViewClassAuthority,
    floor_plan_selector: ViewportViewClassSelector,
) -> None:
    is_valid, reason = validate_opening_decision_viewport(
        viewport=sample_segmented_viewport,
        view_class_authority=sample_view_class_authority,
        selector=floor_plan_selector,
    )
    assert is_valid is True
    assert reason == "viewport_authenticated"


# ---------------------------------------------------------------------------
# Edge Case 20: Viewport validation: cropped viewport -> rejected
# ---------------------------------------------------------------------------
def test_validate_opening_decision_viewport_cropped(
    sample_view_class_authority: ViewportViewClassAuthority,
    floor_plan_selector: ViewportViewClassSelector,
) -> None:
    cropped_vp = SegmentedViewport(
        view_id="vp_floor_plan_p1",
        page_number=1,
        view_type="floor_plan",
        label="GROUND FLOOR PLAN",
        title_bbox=(50.0, 50.0, 200.0, 70.0),
        bounding_box=(50.0, 50.0, 750.0, 550.0),
        status="cropped",
        boundary_source="vector_frame",
        confidence=1.0,
    )
    is_valid, reason = validate_opening_decision_viewport(
        viewport=cropped_vp,
        view_class_authority=sample_view_class_authority,
        selector=floor_plan_selector,
        require_uncropped=True,
    )
    assert is_valid is False
    assert reason == "viewport_boundary_cropped"


# ---------------------------------------------------------------------------
# Edge Case 21: Viewport validation: unsegmented viewport -> rejected
# ---------------------------------------------------------------------------
def test_validate_opening_decision_viewport_unsegmented(
    sample_view_class_authority: ViewportViewClassAuthority,
    floor_plan_selector: ViewportViewClassSelector,
) -> None:
    is_valid, reason = validate_opening_decision_viewport(
        viewport=None,
        view_class_authority=sample_view_class_authority,
        selector=floor_plan_selector,
    )
    assert is_valid is False
    assert reason == "viewport_segmentation_unresolved"


# ---------------------------------------------------------------------------
# Edge Case 22: Viewport validation: uncorroborated view class -> rejected
# ---------------------------------------------------------------------------
def test_validate_opening_decision_viewport_uncorroborated_view_class(
    sample_segmented_viewport: SegmentedViewport,
) -> None:
    empty_auth = ViewportViewClassProducer.create().authority()
    unpub_selector = ViewportViewClassSelector(
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        viewport_id="vp_unregistered",
    )
    is_valid, reason = validate_opening_decision_viewport(
        viewport=sample_segmented_viewport,
        view_class_authority=empty_auth,
        selector=unpub_selector,
    )
    assert is_valid is False
    assert "viewport_view_class_unresolved" in reason


# ---------------------------------------------------------------------------
# Edge Case 23: Upstream completeness authority integration
# ---------------------------------------------------------------------------
def test_upstream_completeness_authority_integration() -> None:
    producer = OpeningUniverseCompletenessProducer(
        producer_method="evidence_first_test",
        producer_version="1.0.0",
    )
    cov_complete = SourceDecodeCoverageRecord(
        document_id="doc_test",
        revision_id="rev_test_01",
        total_pages=1,
        decoded_pages=(1,),
        failed_pages=(),
        state="complete",
    )
    producer.publish_enumeration(
        decision_scope_id="scope_full_p1",
        decision_scope_kind="page_scope",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_ids=("page_1",),
        viewport_id=None,
        coverage=cov_complete,
        source_primitives=(),
        enumerated_primitives=(),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
    )
    authority = producer.authority()
    sel_full = OpeningUniverseSelector(
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        decision_scope_id="scope_full_p1",
    )
    res_full = authority.resolve(sel_full)
    assert res_full.status == EvidenceResolutionStatus.CORROBORATED


# ---------------------------------------------------------------------------
# Edge Case 24: Statistically grounded tolerance derivation
# ---------------------------------------------------------------------------
def test_source_derived_tolerance_zero_evidence_fails_closed() -> None:
    with pytest.raises(ValueError, match="scale_ratio must be positive"):
        SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=0.0)

    with pytest.raises(ValueError, match="Cannot derive tolerance from zero or missing source evidence"):
        SourceToleranceProvenance.from_scale_and_stroke(
            scale_ratio=100.0,
            stroke_width_pt=None,
            scale_residual_mm=None,
            raster_dpi=None,
        )


def test_source_derived_tolerance_mathematical_correctness() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(
        scale_ratio=100.0,
        stroke_width_pt=0.7,
        scale_residual_mm=1.0,
        raster_dpi=300.0,
    )
    assert tol.derived_tolerance_mm == pytest.approx(24.694, rel=1e-2)
    assert tol.derived_tolerance_pt == pytest.approx(0.7, rel=1e-2)
    assert tol.robust_scale_estimator == "vector_stroke_bounding"


# ---------------------------------------------------------------------------
# Edge Case 25: Sample size rules
# ---------------------------------------------------------------------------
def test_tolerance_sample_size_rules() -> None:
    with pytest.raises(ValueError, match="insufficient_sample_size_for_statistical_tolerance: N=6 < 10"):
        SourceToleranceProvenance.from_residuals(
            scale_ratio=50.0,
            residuals_pt=[0.1, 0.2, 0.15, 0.22, 0.18, 0.19],
        )

    med_residuals = [0.10 + 0.01 * i for i in range(15)]
    tol_mad = SourceToleranceProvenance.from_residuals(
        scale_ratio=50.0,
        residuals_pt=med_residuals,
    )
    assert tol_mad.sample_size == 15
    assert tol_mad.robust_scale_estimator == "median_absolute_deviation"
    assert tol_mad.coverage_factor == pytest.approx(2.576)

    large_residuals = [0.05 + 0.01 * (i % 20) for i in range(35)]
    tol_p99 = SourceToleranceProvenance.from_residuals(
        scale_ratio=50.0,
        residuals_pt=large_residuals,
    )
    assert tol_p99.sample_size == 35
    assert tol_p99.robust_scale_estimator == "empirical_quantile"


# ---------------------------------------------------------------------------
# Edge Case 26: Detector output directly marked CORROBORATED is rejected
# ---------------------------------------------------------------------------
def test_corroborated_candidate_forbidden_at_detector_stage() -> None:
    with pytest.raises(ValueError, match="cannot be directly marked CORROBORATED"):
        make_candidate(status=EvidenceResolutionStatus.CORROBORATED)


# ---------------------------------------------------------------------------
# Edge Case 27: Lineage conversion
# ---------------------------------------------------------------------------
def test_candidate_semantic_opening_lineage_conversion() -> None:
    candidate = make_candidate(
        source_observation_ids=("obs_01", "obs_02"),
        source_lineage_root_ids=("root_01",),
        reason_codes=("candidate_detected",),
    )
    upstream = candidate.to_candidate_semantic_opening()
    assert upstream.candidate_id == candidate.candidate_id
    assert upstream.source_observation_ids == ("obs_01", "obs_02")
    assert upstream.status == EvidenceResolutionStatus.CANDIDATE


# ---------------------------------------------------------------------------
# Edge Case 28: Perpendicular openings inside tolerance envelope are UNRESOLVED
# ---------------------------------------------------------------------------
def test_nearby_perpendicular_openings_inside_tolerance_are_proven_distinct() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=100.0, stroke_width_pt=5.0)
    cand_a = make_candidate(geometry=(100.0, 100.0, 140.0, 102.0), tolerance_provenance=tol)
    cand_b = make_candidate(geometry=(119.0, 81.0, 121.0, 121.0), tolerance_provenance=tol)
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    # Orientation/aspect ratio discrepancy at coincident location fails closed as UNRESOLVED
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


# ---------------------------------------------------------------------------
# Edge Case 29: Conflicting tags inside tolerance are UNRESOLVED (conflicting annotations)
# ---------------------------------------------------------------------------
def test_nearby_openings_with_conflicting_tags_inside_tolerance_are_proven_distinct() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=100.0, stroke_width_pt=5.0)
    cand_1 = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        tolerance_provenance=tol,
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_1",
            bound_mark="D1",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )
    cand_2 = make_candidate(
        geometry=(101.0, 100.0, 141.0, 140.0),
        tolerance_provenance=tol,
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_2",
            bound_mark="D2",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "conflicting_tag_annotations_at_same_location" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 30: Conflicting patterns inside tolerance are UNRESOLVED (differing modalities)
# ---------------------------------------------------------------------------
def test_nearby_openings_with_conflicting_patterns_inside_tolerance_are_proven_distinct() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=100.0, stroke_width_pt=5.0)
    cand_single = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        tolerance_provenance=tol,
    )
    cand_paired = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="paired_door_swing",
        tolerance_provenance=tol,
    )
    result = OpeningIdentityResolver.compare_candidates(cand_single, cand_paired)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "differing_detector_modalities_at_same_location_ambiguous" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 31: Disjoint lineage inside tolerance is UNRESOLVED
# ---------------------------------------------------------------------------
def test_nearby_candidates_with_disjoint_lineage_inside_tolerance_are_unresolved() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=100.0, stroke_width_pt=5.0)
    cand_a = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_a",),
        tolerance_provenance=tol,
    )
    cand_b = make_candidate(
        geometry=(102.0, 100.0, 142.0, 140.0),
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_b",),
        tolerance_provenance=tol,
    )
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "proximate_or_coincident_candidates_with_disjoint_lineage_ambiguous" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Regression Matrix Tests (Tests 33 to 46)
# ---------------------------------------------------------------------------


def test_regression_matrix_1_coincident_geometry_plus_disjoint_lineage_is_unresolved(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    cand_a = make_candidate(
        source_observation_ids=("obs_alpha",),
        source_lineage_root_ids=("lineage_root_alpha",),
    )
    cand_b = make_candidate(
        source_observation_ids=("obs_beta",),
        source_lineage_root_ids=("lineage_root_beta",),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "proximate_or_coincident_candidates_with_disjoint_lineage_ambiguous" in result.reason_codes[0]


def test_regression_matrix_2_same_dimensions_plus_disjoint_lineage_is_unresolved() -> None:
    cand_a = make_candidate(
        structural_pattern="dimension_chain_opening",
        dimension_mm=(1500.0, 1200.0),
        source_observation_ids=("obs_dim_a",),
        source_lineage_root_ids=("root_dim_a",),
    )
    cand_b = make_candidate(
        structural_pattern="dimension_chain_opening",
        dimension_mm=(1500.0, 1200.0),
        source_observation_ids=("obs_dim_b",),
        source_lineage_root_ids=("root_dim_b",),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_regression_matrix_3_different_document_ids_never_proven_same() -> None:
    cand_a = make_candidate(document_id="doc_first_tender")
    cand_b = make_candidate(document_id="doc_second_tender")
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "cross_document_identity_unresolved" in result.reason_codes


def test_regression_matrix_4_different_revision_ids_never_proven_same() -> None:
    cand_a = make_candidate(revision_id="rev_01")
    cand_b = make_candidate(revision_id="rev_02")
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "cross_revision_identity_unresolved" in result.reason_codes


def test_regression_matrix_5_different_source_sha256_never_proven_same() -> None:
    cand_a = make_candidate(source_sha256="a" * 64)
    cand_b = make_candidate(source_sha256="b" * 64)
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "source_sha256_mismatch_unresolved" in result.reason_codes


def test_regression_matrix_6_incompatible_snapshots_never_proven_same() -> None:
    cand_a = make_candidate(snapshot_id="snap_20260901")
    cand_b = make_candidate(snapshot_id="snap_20260902")
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "snapshot_id_mismatch_unresolved" in result.reason_codes


def test_regression_matrix_7_same_page_id_from_different_documents_never_proven_same() -> None:
    cand_a = make_candidate(document_id="doc_alpha", page_id="page_1")
    cand_b = make_candidate(document_id="doc_beta", page_id="page_1")
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "cross_document_identity_unresolved" in result.reason_codes


def test_regression_matrix_8_shared_authenticated_lineage_proven_same_only_when_all_scope_agrees() -> None:
    cand_a = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        source_lineage_root_ids=("lineage_common_root",),
    )
    cand_b = make_candidate(
        geometry=(100.2, 100.2, 140.2, 140.2),
        source_lineage_root_ids=("lineage_common_root",),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is True
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_RESOLVED


def test_regression_matrix_9_identical_geometry_with_no_identity_bridge_is_unresolved() -> None:
    cand_a = make_candidate(
        geometry=(200.0, 200.0, 250.0, 250.0),
        source_observation_ids=("obs_x",),
        source_lineage_root_ids=("root_x",),
    )
    cand_b = make_candidate(
        geometry=(200.0, 200.0, 250.0, 250.0),
        source_observation_ids=("obs_y",),
        source_lineage_root_ids=("root_y",),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_regression_matrix_10_two_equal_w1_windows_remain_distinct_physical_instances() -> None:
    tag_binding_w1_a = OpeningTagBindingResult(
        candidate_id="cand_a",
        bound_mark="W1",
        status=EvidenceResolutionStatus.CORROBORATED,
        identity_state=IdentityState.PROVEN_SAME,
    )
    tag_binding_w1_b = OpeningTagBindingResult(
        candidate_id="cand_b",
        bound_mark="W1",
        status=EvidenceResolutionStatus.CORROBORATED,
        identity_state=IdentityState.PROVEN_SAME,
    )
    win_a = make_candidate(
        geometry=(100.0, 100.0, 150.0, 110.0),
        structural_pattern="dimension_chain_opening",
        dimension_mm=(1500.0, 1200.0),
        semantic_family="windows",
        tag_binding=tag_binding_w1_a,
    )
    win_b = make_candidate(
        geometry=(300.0, 100.0, 350.0, 110.0),
        structural_pattern="dimension_chain_opening",
        dimension_mm=(1500.0, 1200.0),
        semantic_family="windows",
        tag_binding=tag_binding_w1_b,
    )
    result = OpeningIdentityResolver.compare_candidates(win_a, win_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "distinct_physical_locations" in result.reason_codes[0]


def test_regression_matrix_11_plan_physical_opening_vs_schedule_type_definition_never_physical_proven_same() -> None:
    plan_instance = make_candidate(context_kind="floor_plan_opening")
    schedule_def = make_candidate(context_kind="schedule_type_definition")
    result = OpeningIdentityResolver.compare_candidates(plan_instance, schedule_def)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "different_context_kinds_not_comparable_for_physical_instance_identity" in result.reason_codes[0]


def test_regression_matrix_12_plan_opening_vs_legend_example_symbol_never_physical_proven_same() -> None:
    plan_instance = make_candidate(context_kind="floor_plan_opening")
    legend_symbol = make_candidate(context_kind="legend_example_symbol")
    result = OpeningIdentityResolver.compare_candidates(plan_instance, legend_symbol)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "different_context_kinds_not_comparable_for_physical_instance_identity" in result.reason_codes[0]


def test_regression_matrix_13_paired_double_door_vs_single_door_observation_fails_closed() -> None:
    cand_single = make_candidate(structural_pattern="door_swing_arc")
    cand_paired = make_candidate(structural_pattern="paired_door_swing")
    result = OpeningIdentityResolver.compare_candidates(cand_single, cand_paired)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "differing_detector_modalities_at_same_location_ambiguous" in result.reason_codes[0]


def test_regression_matrix_14_two_nearby_distinct_objects_within_tolerance_envelope_never_collapse() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=100.0, stroke_width_pt=5.0)
    cand_1 = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
        tolerance_provenance=tol,
    )
    cand_2 = make_candidate(
        geometry=(101.5, 100.0, 141.5, 140.0),
        source_observation_ids=("obs_2",),
        source_lineage_root_ids=("root_2",),
        tolerance_provenance=tol,
    )
    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


# ---------------------------------------------------------------------------
# Reviewer Mutation & Safety Tests (Item 10)
# ---------------------------------------------------------------------------


def test_caller_supplies_arbitrary_candidate_id_rejected(
    sample_tolerance: SourceToleranceProvenance,
    sample_viewport_decision: AuthenticatedViewportDecision,
) -> None:
    """1. Caller supplies arbitrary candidate ID -> constructor strictly rejects it."""
    with pytest.raises(ValueError, match="caller_supplied_candidate_id_mismatch"):
        create_opening_candidate(
            document_id="doc_test",
            revision_id="rev_01",
            source_sha256="a" * 64,
            snapshot_id="snap_01",
            page_id="page_1",
            viewport_id="vp_floor_plan_p1",
            geometry=(100.0, 100.0, 140.0, 140.0),
            structural_pattern="door_swing_arc",
            source_observation_ids=("obs_1",),
            source_lineage_root_ids=("root_1",),
            tolerance_provenance=sample_tolerance,
            viewport_decision=sample_viewport_decision,
            wall_lines=[(100.0, 0.0, 100.0, 300.0)],
            candidate_id="D1",  # Arbitrary caller ID!
        )

    with pytest.raises(ValueError, match="caller_supplied_candidate_id_mismatch"):
        create_opening_candidate(
            document_id="doc_test",
            revision_id="rev_01",
            source_sha256="a" * 64,
            snapshot_id="snap_01",
            page_id="page_1",
            viewport_id="vp_floor_plan_p1",
            geometry=(100.0, 100.0, 140.0, 140.0),
            structural_pattern="door_swing_arc",
            source_observation_ids=("obs_1",),
            source_lineage_root_ids=("root_1",),
            tolerance_provenance=sample_tolerance,
            viewport_decision=sample_viewport_decision,
            wall_lines=[(100.0, 0.0, 100.0, 300.0)],
            candidate_id="my_candidate",  # Arbitrary caller ID!
        )


def test_candidate_id_changes_with_revision() -> None:
    """2. candidate_id changes with revision."""
    cid_rev1 = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
    )
    cid_rev2 = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_02",  # Changed!
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
    )
    assert cid_rev1 != cid_rev2


def test_candidate_id_changes_with_source_sha() -> None:
    """3. candidate_id changes with source SHA."""
    cid_sha_a = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
    )
    cid_sha_b = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="b" * 64,  # Changed!
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
    )
    assert cid_sha_a != cid_sha_b


def test_candidate_id_stable_under_reordered_lineage_ids() -> None:
    """4. candidate_id is stable under reordered lineage IDs."""
    cid_order_1 = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=["obs_b", "obs_a"],
        source_lineage_root_ids=["root_2", "root_1"],
    )
    cid_order_2 = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=["obs_a", "obs_b"],
        source_lineage_root_ids=["root_1", "root_2"],
    )
    assert cid_order_1 == cid_order_2


def test_raw_tuple_tag_rejected_by_resolve_tag_binding() -> None:
    """5. Raw tuple ('D1', (x, y)) is rejected by resolve_tag_binding."""
    cand = make_candidate()
    with pytest.raises(TypeError, match="nearby_tags must contain only TagObservation instances"):
        OpeningIdentityResolver.resolve_tag_binding(
            candidate=cand,
            nearby_tags=[("D1", (120.0, 120.0))],  # type: ignore[list-item]
            expected_semantic_family="doors",
        )


def test_nearby_d1_without_binding_relation_is_unresolved() -> None:
    """6. Nearby D1 tag without an authenticated binding relation returns UNRESOLVED."""
    cand = make_candidate()
    tag_obs = make_tag_obs(tag_text="D1", center=(120.0, 120.0), observation_id="tag_d1")
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=cand,
        nearby_tags=[tag_obs],
        binding_evidences=[],  # No relation evidence!
        expected_semantic_family="doors",
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert "spatial_proximity_without_authenticated_relation_ambiguous" in result.reason_codes


def test_nearby_d1_with_authenticated_leader_relation_resolves() -> None:
    """7. Nearby D1 tag with authenticated leader relation resolves to PROVEN_SAME."""
    cand = make_candidate()
    tag_obs = make_tag_obs(tag_text="D1", center=(120.0, 120.0), observation_id="tag_d1")
    evidence = TagBindingEvidence(
        tag_observation_id="tag_d1",
        candidate_id=cand.candidate_id,
        relation_kind=TagBindingRelationKind.LEADER_TO_OPENING,
    )
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=cand,
        nearby_tags=[tag_obs],
        binding_evidences=[evidence],
        expected_semantic_family="doors",
    )
    assert result.identity_state == IdentityState.PROVEN_SAME
    assert result.status == EvidenceResolutionStatus.CORROBORATED
    assert result.bound_mark == "D1"
    assert "relation_leader_to_opening" in result.reason_codes


def test_caller_says_view_kind_floor_plan_without_authority_not_candidate(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """8. Caller claiming floor plan without resolved viewport authority remains RAW."""
    cand = create_opening_candidate(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="dimension_chain_opening",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
        tolerance_provenance=sample_tolerance,
        viewport_bbox=(0.0, 0.0, 1000.0, 1000.0),
        # Notice: No viewport_decision or ViewportViewClassAuthority!
    )
    assert cand.status == EvidenceResolutionStatus.RAW
    assert "missing_authenticated_viewport_decision" in cand.reason_codes


def test_missing_viewport_bbox_safety_input_fails_closed(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """9. Missing viewport_bbox fails closed (candidate status RAW)."""
    # Viewport decision with empty bounding_box
    vp_empty_bbox = SegmentedViewport(
        view_id="vp_no_box",
        page_number=1,
        view_type="floor_plan",
        label="GROUND FLOOR PLAN",
        title_bbox=(0.0, 0.0, 50.0, 50.0),
        bounding_box=None,  # Missing bbox!
        status="resolved",
        boundary_source="vector_frame",
        confidence=1.0,
    )
    decision = AuthenticatedViewportDecision(
        viewport=vp_empty_bbox,
        view_kind=VIEW_KIND_FLOOR_PLAN,
    )
    cand = create_opening_candidate(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_no_box",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="dimension_chain_opening",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
        tolerance_provenance=sample_tolerance,
        viewport_decision=decision,
        viewport_bbox=None,  # Missing!
    )
    assert cand.status == EvidenceResolutionStatus.RAW
    assert "missing_viewport_bbox_safety_input" in cand.reason_codes


def test_door_swing_with_missing_wall_host_evidence_not_promoted(
    sample_tolerance: SourceToleranceProvenance,
    sample_viewport_decision: AuthenticatedViewportDecision,
) -> None:
    """10. Door swing arc with missing wall host evidence is not promoted to CANDIDATE."""
    cand = create_opening_candidate(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
        tolerance_provenance=sample_tolerance,
        viewport_decision=sample_viewport_decision,
        wall_lines=None,  # Missing wall host context!
    )
    assert cand.status == EvidenceResolutionStatus.RAW
    assert "door_swing_missing_wall_host_context" in cand.reason_codes


def test_schedule_type_vs_physical_plan_opening_not_proven_distinct_physical_instances() -> None:
    """11. Schedule type vs physical plan opening -> UNRESOLVED for physical instance identity."""
    plan_cand = make_candidate(context_kind="floor_plan_opening")
    sched_type = make_candidate(context_kind="schedule_type_definition")
    result = OpeningIdentityResolver.compare_candidates(plan_cand, sched_type)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_same_physical_door_observed_as_swing_and_jamb_interruption_is_unresolved() -> None:
    """12. Same physical door observed as swing + jamb interruption -> UNRESOLVED."""
    cand_swing = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
    )
    cand_jamb = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="jamb_wall_interruption",
    )
    result = OpeningIdentityResolver.compare_candidates(cand_swing, cand_jamb)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "differing_detector_modalities_at_same_location_ambiguous" in result.reason_codes[0]


def test_coincident_d1_d2_conflicting_annotations_is_unresolved() -> None:
    """13. Coincident D1/D2 conflicting annotations -> UNRESOLVED."""
    cand_d1 = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_1",
            bound_mark="D1",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )
    cand_d2 = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_2",
            bound_mark="D2",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_d1, cand_d2)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "conflicting_tag_annotations_at_same_location" in result.reason_codes[0]


def test_dimension_disagreement_inside_tolerance_is_unresolved() -> None:
    """14. Dimension disagreement inside tolerance -> UNRESOLVED."""
    cand_a = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        dimension_mm=(900.0, 2100.0),
    )
    cand_b = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        dimension_mm=(1200.0, 2100.0),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "conflicting_dimensions_at_same_location_ambiguous" in result.reason_codes[0]


def test_bbox_aspect_ratio_change_cannot_create_physical_distinctness() -> None:
    """15. Bbox aspect ratio change cannot create physical distinctness."""
    tol = SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=100.0, stroke_width_pt=5.0)
    cand_h = make_candidate(geometry=(100.0, 100.0, 140.0, 102.0), tolerance_provenance=tol)  # center (120, 101)
    cand_v = make_candidate(geometry=(119.0, 81.0, 121.0, 121.0), tolerance_provenance=tol)  # center (120, 101)
    result = OpeningIdentityResolver.compare_candidates(cand_h, cand_v)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_same_type_w1_in_two_authenticated_separate_wall_apertures_proven_distinct() -> None:
    """16. Same type W1 in two authenticated separate wall apertures -> PROVEN_DISTINCT."""
    win_1 = make_candidate(
        geometry=(100.0, 50.0, 160.0, 60.0),
        semantic_family="windows",
        tag_binding=OpeningTagBindingResult(
            candidate_id="win_1",
            bound_mark="W1",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )
    win_2 = make_candidate(
        geometry=(400.0, 50.0, 460.0, 60.0),
        semantic_family="windows",
        tag_binding=OpeningTagBindingResult(
            candidate_id="win_2",
            bound_mark="W1",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )
    result = OpeningIdentityResolver.compare_candidates(win_1, win_2)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "distinct_physical_locations" in result.reason_codes[0]


def test_same_physical_aperture_with_two_detector_modalities_not_double_counted() -> None:
    """17. Same physical aperture with two detector modalities: shared lineage resolves to PROVEN_SAME, disjoint fails closed as UNRESOLVED."""
    cand_arc = make_candidate(
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_modal_1",),
        source_lineage_root_ids=("aperture_root_01",),
    )
    # Different detector modality sharing the same aperture lineage
    cand_interruption_same = make_candidate(
        geometry=(100.1, 100.1, 140.1, 140.1),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_modal_2",),
        source_lineage_root_ids=("aperture_root_01",),
    )
    result = OpeningIdentityResolver.compare_candidates(cand_arc, cand_interruption_same)
    assert result.proven_same is True
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_RESOLVED

    # If disjoint lineage, fails closed as UNRESOLVED (never double counted as PROVEN_DISTINCT)
    cand_interruption_disjoint = make_candidate(
        geometry=(100.1, 100.1, 140.1, 140.1),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_modal_3",),
        source_lineage_root_ids=("aperture_root_02",),
    )
    result_disjoint = OpeningIdentityResolver.compare_candidates(cand_arc, cand_interruption_disjoint)
    assert result_disjoint.proven_same is False
    assert result_disjoint.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
