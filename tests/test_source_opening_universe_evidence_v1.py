"""tests/test_source_opening_universe_evidence_v1.py — Comprehensive adversarial tests.

Validates the clean, evidence-first opening candidate authority across all required edge cases:
1. One arc with no tag -> UNRESOLVED (never assumes D1).
2. One arc beside D1 -> PROVEN_SAME (binds unambiguously).
3. Tag binding rejected when viewport unauthenticated.
4. Tag binding rejected when revision mismatched.
5. Tag binding filters incompatible semantic trade tags (e.g. W1 ignored for door swing).
6. One arc beside two plausible tags -> UNRESOLVED (fails closed).
7. Two equal doors -> PROVEN_DISTINCT (distinct physical openings).
8. Coincident detections at same location -> PROVEN_SAME.
9. Logo cubic -> rejected by context filter / viewport boundary.
10. Furniture arc -> rejected (not hosted at wall jamb).
11. Sanitary arc -> rejected (sanitary fixture context/layers).
12. Schedule sample door -> PROVEN_DISTINCT from plan room instances.
13. Window detail card -> rejected by viewport view-class authority.
14. Dimension-chain window with no type mark -> UNRESOLVED (never assumes W1/W2).
15. Two possible W-tags -> UNRESOLVED (fails closed).
16. Duplicate plan/elevation observations -> cross-referencing does not double count.
17. Same opening in plan and schedule -> distinct contexts, no double counting.
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
"""
from __future__ import annotations

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
    CandidateContextFilter,
    IdentityState,
    OpeningIdentityResolver,
    OpeningTagBindingResult,
    PhysicalOpeningCandidateRecord,
    SourceToleranceProvenance,
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
        bounding_box=(50.0, 50.0, 750.0, 550.0),
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


# ---------------------------------------------------------------------------
# Edge Case 1: One arc with no tag -> UNRESOLVED (never assumes D1)
# ---------------------------------------------------------------------------
def test_one_arc_with_no_tag_remains_unresolved(sample_tolerance: SourceToleranceProvenance) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_arc_01",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_arc_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

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
    # Crucial guarantee: Never assumes D1!
    assert result.bound_tag != "D1"


# ---------------------------------------------------------------------------
# Edge Case 2: One arc beside D1 -> PROVEN_SAME (unambiguous)
# ---------------------------------------------------------------------------
def test_one_arc_beside_d1_binds_unambiguously(sample_tolerance: SourceToleranceProvenance) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_arc_02",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_arc_02",),
        source_lineage_root_ids=("root_02",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )


    nearby_tags = [("D1", (122.0, 121.0))]
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=nearby_tags,
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )

    assert result.identity_state == IdentityState.PROVEN_SAME
    assert result.bound_tag == "D1"
    assert "unambiguous_tag_proven" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 3: Tag binding rejected when viewport unauthenticated
# ---------------------------------------------------------------------------
def test_tag_binding_rejected_when_viewport_unauthenticated(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_arc_unauth_vp",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_unauth",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[("D1", (122.0, 121.0))],
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
def test_tag_binding_rejected_when_revision_mismatched(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_arc_rev_mismatch",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[("D1", (122.0, 121.0))],
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
def test_tag_binding_semantic_family_filtering(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_door_family_test",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    # Window tag W1 is near the door swing, but should be ignored for doors
    result_window_tag = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[("W1", (122.0, 121.0))],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result_window_tag.identity_state == IdentityState.UNRESOLVED
    assert result_window_tag.bound_tag is None

    # Both W1 and D1 present: W1 is ignored as incompatible trade, D1 unambiguously binds
    result_both = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=[
            ("W1", (122.0, 121.0)),
            ("D1", (120.0, 120.0)),
        ],
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result_both.identity_state == IdentityState.PROVEN_SAME
    assert result_both.bound_tag == "D1"


# ---------------------------------------------------------------------------
# Edge Case 6: One arc beside two plausible tags -> UNRESOLVED (fails closed)
# ---------------------------------------------------------------------------
def test_one_arc_beside_two_plausible_tags_fails_closed(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_arc_03",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_arc_03",),
        source_lineage_root_ids=("root_03",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )


    nearby_tags = [
        ("D1", (121.0, 120.0)),
        ("D2", (120.0, 122.0)),
    ]
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=nearby_tags,
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
def test_two_equal_doors_are_proven_distinct(sample_tolerance: SourceToleranceProvenance) -> None:
    cand_1 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_door_01",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_2 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_door_02",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(300.0, 100.0, 340.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_02",),
        source_lineage_root_ids=("root_02",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "distinct_locations" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 8: Coincident detections at same location -> PROVEN_SAME
# ---------------------------------------------------------------------------
def test_coincident_detections_are_proven_same(sample_tolerance: SourceToleranceProvenance) -> None:
    cand_1 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_det_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_2 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_det_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.2, 100.2, 140.2, 140.2),  # 0.28 pt delta, well within 0.70 pt tolerance
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_02",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    assert result.proven_same is True
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_RESOLVED
    assert "coincident_geometry" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 9: Logo cubic -> rejected by context filter / viewport authority
# ---------------------------------------------------------------------------
def test_logo_cubic_rejected_by_context_filter() -> None:
    viewport_bbox = (50.0, 50.0, 750.0, 550.0)
    title_block_bbox = (600.0, 480.0, 750.0, 550.0)

    # Arc inside title block logo
    logo_cubic_bbox = (650.0, 500.0, 670.0, 520.0)
    is_logo = CandidateContextFilter.is_title_block_or_logo(
        logo_cubic_bbox, viewport_bbox, title_block_bbox
    )
    assert is_logo is True

    # Arc outside viewport
    outside_bbox = (10.0, 10.0, 30.0, 30.0)
    assert CandidateContextFilter.is_title_block_or_logo(outside_bbox, viewport_bbox) is True


# ---------------------------------------------------------------------------
# Edge Case 10: Furniture arc -> rejected (not a wall opening)
# ---------------------------------------------------------------------------
def test_furniture_arc_rejected() -> None:
    # Wall line is at x=100, y in [0, 400]
    wall_lines = [(100.0, 0.0, 100.0, 400.0)]
    # Swivel chair arc in middle of room at (250, 200), radius 20
    is_furniture = CandidateContextFilter.is_furniture_arc(
        arc_center=(250.0, 200.0),
        arc_radius=20.0,
        wall_lines=wall_lines,
        tolerance_pt=5.0,
    )
    assert is_furniture is True

    # Actual door swing anchored at wall jamb at (100, 150), radius 35
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
# Edge Case 12: Schedule sample door -> PROVEN_DISTINCT from plan room instances
# ---------------------------------------------------------------------------
def test_schedule_sample_door_proven_distinct(sample_tolerance: SourceToleranceProvenance) -> None:
    schedule_sample = PhysicalOpeningCandidateRecord(
        candidate_id="cand_sched_sample_d1",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_2",
        viewport_id="vp_sched_01",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="schedule_sample",
        source_observation_ids=("obs_sched_01",),
        source_lineage_root_ids=("root_sched_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    plan_instance = PhysicalOpeningCandidateRecord(
        candidate_id="cand_plan_d1",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_plan_01",),
        source_lineage_root_ids=("root_plan_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(schedule_sample, plan_instance)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "different_context_kinds" in result.reason_codes


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
# Edge Case 14: Dimension-chain window with no type mark -> UNRESOLVED (never assumes W1/W2)
# ---------------------------------------------------------------------------
def test_dimension_chain_window_with_no_type_mark(sample_tolerance: SourceToleranceProvenance) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_win_dim_01",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(200.0, 100.0, 260.0, 120.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_dim_01",),
        source_lineage_root_ids=("root_dim_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
        dimension_mm=(1500.0, 1200.0),
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
    # Crucial guarantee: Never assumes W1 or W2 from dimensions alone!
    assert result.bound_tag not in ("W1", "W2")


# ---------------------------------------------------------------------------
# Edge Case 15: Two possible W-tags -> UNRESOLVED (fails closed)
# ---------------------------------------------------------------------------
def test_two_possible_wtags_fails_closed(sample_tolerance: SourceToleranceProvenance) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_win_dim_02",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(200.0, 100.0, 260.0, 120.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_dim_02",),
        source_lineage_root_ids=("root_dim_02",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
        dimension_mm=(1500.0, 1200.0),
    )


    nearby_tags = [
        ("W1", (231.0, 110.0)),
        ("W2", (230.0, 111.0)),
    ]
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=nearby_tags,
        expected_semantic_family="windows",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag is None
    assert "competing_tags_ambiguous" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Edge Case 16: Duplicate plan/elevation observations -> cross-referencing does not double count
# ---------------------------------------------------------------------------
def test_duplicate_plan_elevation_observations(sample_tolerance: SourceToleranceProvenance) -> None:
    plan_cand = PhysicalOpeningCandidateRecord(
        candidate_id="cand_plan_win_01",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(200.0, 100.0, 260.0, 120.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_plan_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    elev_cand = PhysicalOpeningCandidateRecord(
        candidate_id="cand_elev_win_01",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_2",
        viewport_id="vp_elev_01",
        geometry=(200.0, 300.0, 260.0, 350.0),
        structural_pattern="elevation_opening_symbol",
        context_kind="elevation_opening",
        source_observation_ids=("obs_elev_01",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(plan_cand, elev_cand)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "different_context_kinds" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 17: Same opening in plan and schedule -> distinct contexts
# ---------------------------------------------------------------------------
def test_same_opening_in_plan_and_schedule(sample_tolerance: SourceToleranceProvenance) -> None:
    plan_cand = PhysicalOpeningCandidateRecord(
        candidate_id="cand_plan_d1",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_plan_d1",),
        source_lineage_root_ids=("root_d1",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    sched_row = PhysicalOpeningCandidateRecord(
        candidate_id="cand_sched_d1",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_3",
        viewport_id="vp_sched_01",
        geometry=(50.0, 200.0, 500.0, 220.0),
        structural_pattern="schedule_row",
        context_kind="schedule_specification",
        source_observation_ids=("obs_sched_row_01",),
        source_lineage_root_ids=("root_d1",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(plan_cand, sched_row)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "different_context_kinds" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 18: Distinct equal-size openings -> PROVEN_DISTINCT, count is 2
# ---------------------------------------------------------------------------
def test_distinct_equal_size_openings_proven_distinct(sample_tolerance: SourceToleranceProvenance) -> None:
    win_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_win_1500_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 50.0, 160.0, 60.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_w1",),
        source_lineage_root_ids=("root_w1",),
        tolerance_provenance=sample_tolerance,
        dimension_mm=(1500.0, 1200.0),
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    win_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_win_1500_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(250.0, 50.0, 310.0, 60.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_w2",),
        source_lineage_root_ids=("root_w2",),
        tolerance_provenance=sample_tolerance,
        dimension_mm=(1500.0, 1200.0),
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(win_a, win_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "distinct_locations" in result.reason_codes[0]


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
# Edge Case 20: Viewport validation: cropped viewport -> rejected (fails closed)
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
# Edge Case 21: Viewport validation: unsegmented viewport -> rejected (fails closed)
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
# Edge Case 22: Viewport validation: uncorroborated view class -> rejected (fails closed)
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
# Edge Case 23: Upstream opening-universe completeness authority integration
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

    # 1. Full-scope enumeration with known visible content -> CORROBORATED
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

    # 2. Local viewport scope -> VIEWPORT_LIMITED_SCOPE -> fails closed (ABSTAINED)
    producer.publish_enumeration(
        decision_scope_id="scope_vp_p1",
        decision_scope_kind="viewport_scope",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_ids=("page_1",),
        viewport_id="vp_floor_plan_p1",
        coverage=cov_complete,
        source_primitives=(),
        enumerated_primitives=(),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
    )

    authority = producer.authority()

    # Full scope resolves to CORROBORATED
    sel_full = OpeningUniverseSelector(
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        decision_scope_id="scope_full_p1",
    )
    res_full = authority.resolve(sel_full)
    assert res_full.status == EvidenceResolutionStatus.CORROBORATED
    assert res_full.decision_scope_complete is True
    assert res_full.source_decode_complete is True

    # Viewport-limited scope resolves to ABSTAINED (fails closed)
    sel_vp = OpeningUniverseSelector(
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        decision_scope_id="scope_vp_p1",
    )
    res_vp = authority.resolve(sel_vp)
    assert res_vp.status == EvidenceResolutionStatus.ABSTAINED
    assert res_vp.decision_scope_complete is False
    assert "opening_universe_viewport_limited_scope" in res_vp.reason_codes

    # Unrecorded selector resolves to ABSTAINED
    unrecorded_selector = OpeningUniverseSelector(
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        decision_scope_id="scope_unknown",
    )
    res_unrecorded = authority.resolve(unrecorded_selector)
    assert res_unrecorded.status == EvidenceResolutionStatus.ABSTAINED
    assert res_unrecorded.decision_scope_complete is None


# ---------------------------------------------------------------------------
# Edge Case 24: Statistically grounded tolerance: physical scale/stroke derivation
# ---------------------------------------------------------------------------
def test_source_derived_tolerance_zero_evidence_fails_closed() -> None:
    with pytest.raises(ValueError, match="scale_ratio must be positive"):
        SourceToleranceProvenance.from_scale_and_stroke(scale_ratio=0.0)

    with pytest.raises(ValueError, match="Cannot derive tolerance from zero or missing source evidence"):
        SourceToleranceProvenance.from_scale_and_stroke(
            scale_ratio=100.0,
            stroke_width_pt=0.0,
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
    # 3 * 1.0mm = 3.0mm
    # raster: 25.4 / 300 * 100 = 8.467mm
    # stroke: 0.7 * (25.4/72) * 100 = 24.694mm
    # max is stroke_width ~24.694 mm
    assert tol.derived_tolerance_mm == pytest.approx(24.694, rel=1e-2)
    assert tol.derived_tolerance_pt == pytest.approx(0.7, rel=1e-2)
    assert tol.robust_scale_estimator == "vector_stroke_bounding"
    assert tol.sample_size == 1


# ---------------------------------------------------------------------------
# Edge Case 25: Statistically grounded tolerance: sample size rules
# ---------------------------------------------------------------------------
def test_tolerance_sample_size_rules() -> None:
    # Rule 1: N < 10 fails closed
    with pytest.raises(ValueError, match="insufficient_sample_size_for_statistical_tolerance: N=6 < 10"):
        SourceToleranceProvenance.from_residuals(
            scale_ratio=50.0,
            residuals_pt=[0.1, 0.2, 0.15, 0.22, 0.18, 0.19],
        )

    # Rule 2: 10 <= N < 30 applies MAD with Gaussian k=2.576
    med_residuals = [0.10 + 0.01 * i for i in range(15)]  # N=15
    tol_mad = SourceToleranceProvenance.from_residuals(
        scale_ratio=50.0,
        residuals_pt=med_residuals,
    )
    assert tol_mad.sample_size == 15
    assert tol_mad.robust_scale_estimator == "median_absolute_deviation"
    assert tol_mad.coverage_rule == "mad_gaussian_k2.576"
    assert tol_mad.coverage_factor == pytest.approx(2.576)

    # Rule 3: N >= 30 applies empirical 99th percentile
    large_residuals = [0.05 + 0.01 * (i % 20) for i in range(35)]  # N=35
    tol_p99 = SourceToleranceProvenance.from_residuals(
        scale_ratio=50.0,
        residuals_pt=large_residuals,
    )
    assert tol_p99.sample_size == 35
    assert tol_p99.robust_scale_estimator == "empirical_quantile"
    assert tol_p99.coverage_rule == "empirical_p99"
    assert tol_p99.coverage_factor == pytest.approx(0.99)


# ---------------------------------------------------------------------------
# Edge Case 26: Forbidden pattern from PR #534: detector output directly marked CORROBORATED
# ---------------------------------------------------------------------------
def test_corroborated_candidate_forbidden_at_detector_stage(sample_tolerance: SourceToleranceProvenance) -> None:
    with pytest.raises(ValueError, match="cannot be directly marked CORROBORATED"):
        PhysicalOpeningCandidateRecord(
            candidate_id="cand_illegal",
            document_id="doc_test",
            revision_id="rev_test_01",
            source_sha256="a" * 64,
            snapshot_id="snap_01",
            page_id="page_1",
            viewport_id="vp_floor_plan_p1",
            geometry=(100.0, 100.0, 140.0, 140.0),
            structural_pattern="door_swing_arc",
            context_kind="floor_plan_opening",
            source_observation_ids=("obs_01",),
            source_lineage_root_ids=("root_01",),
            tolerance_provenance=sample_tolerance,
            status=EvidenceResolutionStatus.CORROBORATED,  # Forbidden!
        )


# ---------------------------------------------------------------------------
# Edge Case 27: Lineage preservation: conversion to upstream CandidateSemanticOpening contract
# ---------------------------------------------------------------------------
def test_candidate_semantic_opening_lineage_conversion(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id="cand_lineage_01",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_01", "obs_02"),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("candidate_detected",),
    )

    upstream_opening: CandidateSemanticOpening = candidate.to_candidate_semantic_opening()
    assert upstream_opening.candidate_id == "cand_lineage_01"
    assert upstream_opening.source_observation_ids == ("obs_01", "obs_02")
    assert upstream_opening.source_lineage_root_ids == ("root_01",)
    assert upstream_opening.document_id == "doc_test"
    assert upstream_opening.revision_id == "rev_test_01"
    assert upstream_opening.source_sha256 == "a" * 64
    assert upstream_opening.snapshot_id == "snap_01"
    assert upstream_opening.page_id == "page_1"
    assert upstream_opening.viewport_id == "vp_floor_plan_p1"
    assert upstream_opening.structural_pattern == "door_swing_arc"
    assert upstream_opening.status == EvidenceResolutionStatus.CANDIDATE
    assert upstream_opening.reason_codes == ("candidate_detected",)


# ---------------------------------------------------------------------------
# Edge Case 28: Mutation test: nearby perpendicular openings within tolerance are PROVEN_DISTINCT
# ---------------------------------------------------------------------------
def test_nearby_perpendicular_openings_inside_tolerance_are_proven_distinct() -> None:
    # Derived tolerance is 5.0 pt
    tol = SourceToleranceProvenance.from_scale_and_stroke(
        scale_ratio=100.0,
        stroke_width_pt=5.0,
    )
    assert tol.derived_tolerance_pt == pytest.approx(5.0)

    # Door A in horizontal wall: bbox [100, 100, 140, 110] (width 40 >> height 10 -> H)
    # Center is (120.0, 105.0)
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_corner_h",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 110.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_h",),
        source_lineage_root_ids=("root_h",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    # Door B in vertical wall at the same corner: bbox [100, 100, 110, 140] (height 40 >> width 10 -> V)
    # Center is (105.0, 120.0). Distance = hypot(15, 15) = 21.21 pt.
    # Shift B slightly so center distance is 3.0 pt: e.g. [117, 105, 123, 145] -> center (120.0, 125.0)
    # Center distance is 2.0 pt, well inside 5.0 pt tolerance!
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_corner_v",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(118.0, 90.0, 122.0, 124.0),  # width 4, height 34 -> V, center (120.0, 107.0)
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_v",),
        source_lineage_root_ids=("root_v",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    # Center distance is hypot(0, 2.0) = 2.0 pt <= 5.0 pt tolerance!
    # Because orientations are perpendicular (H vs V), it must NEVER force PROVEN_SAME!
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "conflicting_structural_orientations_perpendicular" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 29: Mutation test: nearby openings with conflicting tags inside tolerance are PROVEN_DISTINCT
# ---------------------------------------------------------------------------
def test_nearby_openings_with_conflicting_tags_inside_tolerance_are_proven_distinct() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(
        scale_ratio=100.0,
        stroke_width_pt=0.7,
        scale_residual_mm=1.5,
    )
    # Two adjacent doors sharing a frame, centers 2.0 pt apart (within derived tolerance ~12.75 pt)
    # but one has validated tag D1 and one has validated tag D2
    cand_1 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_frame_d1",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_d1",),
        source_lineage_root_ids=("root_d1",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_frame_d1",
            bound_mark="D1",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )
    cand_2 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_frame_d2",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(102.0, 100.0, 142.0, 140.0),  # center is (122, 120), delta 2.0 pt <= tol
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_d2",),
        source_lineage_root_ids=("root_d2",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_frame_d2",
            bound_mark="D2",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
    )

    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "conflicting_validated_tags_D1_vs_D2" in result.reason_codes[0]



# ---------------------------------------------------------------------------
# Edge Case 30: Mutation test: nearby openings with conflicting structural patterns are PROVEN_DISTINCT
# ---------------------------------------------------------------------------
def test_nearby_openings_with_conflicting_patterns_inside_tolerance_are_proven_distinct() -> None:
    tol = SourceToleranceProvenance.from_scale_and_stroke(
        scale_ratio=100.0,
        stroke_width_pt=0.7,
        scale_residual_mm=1.5,
    )
    # Single swing vs paired double swing detected at same location
    cand_single = PhysicalOpeningCandidateRecord(
        candidate_id="cand_single_swing",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_single",),
        source_lineage_root_ids=("root_single",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_paired = PhysicalOpeningCandidateRecord(
        candidate_id="cand_paired_swing",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="paired_door_swing",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_paired",),
        source_lineage_root_ids=("root_paired",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_single, cand_paired)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "conflicting_structural_patterns" in result.reason_codes


# ---------------------------------------------------------------------------
# Edge Case 31: Mutation test: nearby candidates with disjoint lineage and non-coincident offset are UNRESOLVED
# ---------------------------------------------------------------------------
def test_nearby_candidates_with_disjoint_lineage_inside_tolerance_are_unresolved() -> None:
    # 14 varying residuals yield MAD-derived tolerance ~11.5 pt
    tol = SourceToleranceProvenance.from_residuals(
        scale_ratio=100.0,
        residuals_pt=[float(i) for i in range(1, 15)],
        stroke_width_pt=0.7,
    )
    assert tol.derived_tolerance_pt > 5.0
    # Two distinct detections with disjoint lineages whose centers are 2.5 pt apart
    # (within 12.75 pt tolerance envelope, but exceeding 0.7 pt stroke coincidence threshold)
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_disjoint_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_a",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_disjoint_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(102.5, 100.0, 142.5, 140.0),  # center offset = 2.5 pt <= 12.75 pt tol
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_b",),  # Disjoint lineage!
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    # Tolerance envelope alone DOES NOT prove identity!
    # Without shared lineage or coincident stroke, the ambiguous cluster fails closed as UNRESOLVED.
    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert "disjoint_lineage_ambiguous" in result.reason_codes[0]


# ---------------------------------------------------------------------------
# Requirement 7: Regression Matrix (Tests 33 to 46)
# ---------------------------------------------------------------------------


def test_regression_matrix_1_coincident_geometry_plus_disjoint_lineage_is_unresolved(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """1. coincident geometry + disjoint lineage -> UNRESOLVED."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_geom_coincident_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("lineage_root_alpha",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_geom_coincident_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),  # Exactly identical geometry
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("lineage_root_beta",),  # Disjoint lineage!
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert "proximate_or_coincident_candidates_with_disjoint_lineage_ambiguous" in result.reason_codes[0]


def test_regression_matrix_2_same_dimensions_plus_disjoint_lineage_is_unresolved(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """2. same dimensions + disjoint lineage -> UNRESOLVED."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_dim_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_dim_a",),
        tolerance_provenance=sample_tolerance,
        dimension_mm=(1500.0, 1200.0),
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_dim_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.1, 100.1, 140.1, 140.1),  # Inside tolerance
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_dim_b",),  # Disjoint lineage!
        tolerance_provenance=sample_tolerance,
        dimension_mm=(1500.0, 1200.0),  # Exactly same dimensions!
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_regression_matrix_3_different_document_ids_never_proven_same(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """3. different document IDs + coincident geometry -> never PROVEN_SAME (UNRESOLVED)."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_doc_a",
        document_id="doc_first_tender",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_doc_b",
        document_id="doc_second_tender",  # Different document!
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "cross_document_identity_unresolved" in result.reason_codes[0]


def test_regression_matrix_4_different_revision_ids_never_proven_same(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """4. different revision IDs + coincident geometry -> never PROVEN_SAME (UNRESOLVED)."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_rev_a",
        document_id="doc_test",
        revision_id="rev_architectural_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_rev_b",
        document_id="doc_test",
        revision_id="rev_architectural_02",  # Different revision!
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "cross_revision_identity_unresolved" in result.reason_codes[0]


def test_regression_matrix_5_different_source_sha256_never_proven_same(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """5. different source SHA256 + coincident geometry -> never PROVEN_SAME (UNRESOLVED)."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_sha_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="1" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_sha_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="2" * 64,  # Different SHA256 hash!
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "source_sha256_mismatch_unresolved" in result.reason_codes[0]


def test_regression_matrix_6_incompatible_snapshots_never_proven_same(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """6. incompatible snapshots -> never PROVEN_SAME (UNRESOLVED)."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_snap_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_run_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_snap_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_run_02",  # Different snapshot!
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert "snapshot_id_mismatch_unresolved" in result.reason_codes[0]


def test_regression_matrix_7_same_page_id_from_different_documents_never_proven_same(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """7. same page_id string from different documents -> never PROVEN_SAME."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_same_page_doc_a",
        document_id="doc_first_tender",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",  # Same page ID string!
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_a",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_same_page_doc_b",
        document_id="doc_second_tender",  # Different document!
        revision_id="rev_test_01",
        source_sha256="b" * 64,
        snapshot_id="snap_01",
        page_id="page_1",  # Same page ID string!
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_b",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_regression_matrix_8_shared_authenticated_lineage_proven_same_only_when_all_scope_agrees(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """8. identical geometry + shared authenticated observation lineage -> PROVEN_SAME only if every hard scope constraint agrees."""
    base_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_scope_a",
        document_id="doc_authoritative",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_lineage_shared",),
        source_lineage_root_ids=("root_lineage_shared",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    base_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_scope_b",
        document_id="doc_authoritative",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_lineage_shared",),
        source_lineage_root_ids=("root_lineage_shared",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    # All scopes agree + shared lineage -> PROVEN_SAME
    res_agree = OpeningIdentityResolver.compare_candidates(base_a, base_b)
    assert res_agree.proven_same is True
    assert res_agree.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_RESOLVED

    # Scope mutation: different revision -> immediately flips to UNRESOLVED
    mut_rev = PhysicalOpeningCandidateRecord(
        candidate_id="cand_scope_b_mut",
        document_id=base_b.document_id,
        revision_id="rev_02",  # Mismatch!
        source_sha256=base_b.source_sha256,
        snapshot_id=base_b.snapshot_id,
        page_id=base_b.page_id,
        viewport_id=base_b.viewport_id,
        geometry=base_b.geometry,
        structural_pattern=base_b.structural_pattern,
        context_kind=base_b.context_kind,
        source_observation_ids=base_b.source_observation_ids,
        source_lineage_root_ids=base_b.source_lineage_root_ids,
        tolerance_provenance=base_b.tolerance_provenance,
    )
    res_disagree = OpeningIdentityResolver.compare_candidates(base_a, mut_rev)
    assert res_disagree.proven_same is False
    assert res_disagree.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_regression_matrix_9_identical_geometry_with_no_identity_bridge_is_unresolved(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """9. identical geometry + no identity bridge -> UNRESOLVED."""
    cand_a = PhysicalOpeningCandidateRecord(
        candidate_id="cand_no_bridge_a",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=(),  # Empty observation ids
        source_lineage_root_ids=(),  # Empty lineage
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_b = PhysicalOpeningCandidateRecord(
        candidate_id="cand_no_bridge_b",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=(),
        source_lineage_root_ids=(),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_a, cand_b)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED


def test_regression_matrix_10_two_equal_w1_windows_remain_distinct_physical_instances(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """10. two equal W1 windows -> two physical instances, never collapsed by type equality."""
    win_1 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_w1_room_north",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 50.0, 160.0, 60.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_w1_north",),
        source_lineage_root_ids=("root_w1_north",),
        tolerance_provenance=sample_tolerance,
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_w1_room_north",
            bound_mark="W1",
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    win_2 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_w1_room_south",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(350.0, 50.0, 410.0, 60.0),
        structural_pattern="dimension_chain_opening",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_w1_south",),
        source_lineage_root_ids=("root_w1_south",),
        tolerance_provenance=sample_tolerance,
        tag_binding=OpeningTagBindingResult(
            candidate_id="cand_w1_room_south",
            bound_mark="W1",  # Same W1 type mark!
            status=EvidenceResolutionStatus.CORROBORATED,
            identity_state=IdentityState.PROVEN_SAME,
        ),
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(win_1, win_2)
    # Must remain distinct instances! Type equality must NEVER collapse them!
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "distinct_locations" in result.reason_codes[0]


def test_regression_matrix_11_plan_physical_opening_vs_schedule_type_definition_never_physical_proven_same(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """11. plan physical opening vs schedule TYPE_DEFINITION -> never physical PROVEN_SAME."""
    plan_door = PhysicalOpeningCandidateRecord(
        candidate_id="cand_room_101_door",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_plan_d1",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    sched_type_card = PhysicalOpeningCandidateRecord(
        candidate_id="cand_sched_type_d1",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_5",
        viewport_id="vp_schedule_page",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="schedule_type_definition",  # Type definition in schedule
        source_observation_ids=("obs_sched_d1",),
        source_lineage_root_ids=("root_01",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(plan_door, sched_type_card)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "different_context_kinds" in result.reason_codes


def test_regression_matrix_12_plan_opening_vs_legend_example_symbol_never_physical_proven_same(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """12. plan opening vs legend/example symbol -> never physical PROVEN_SAME."""
    plan_door = PhysicalOpeningCandidateRecord(
        candidate_id="cand_room_102_door",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_plan_d2",),
        source_lineage_root_ids=("root_02",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    legend_symbol = PhysicalOpeningCandidateRecord(
        candidate_id="cand_legend_symbol_door",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(550.0, 50.0, 590.0, 90.0),
        structural_pattern="door_swing_arc",
        context_kind="legend_example_symbol",  # Sample symbol in legend definition
        source_observation_ids=("obs_legend_d",),
        source_lineage_root_ids=("root_02",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(plan_door, legend_symbol)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "different_context_kinds" in result.reason_codes


def test_regression_matrix_13_paired_double_door_vs_single_door_observation_fails_closed(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """13. paired/double door vs two adjacent single-door observations -> UNRESOLVED unless structural evidence independently resolves it."""
    cand_paired = PhysicalOpeningCandidateRecord(
        candidate_id="cand_paired_door",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 180.0, 140.0),
        structural_pattern="paired_door_swing",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_paired",),
        source_lineage_root_ids=("root_paired",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_single = PhysicalOpeningCandidateRecord(
        candidate_id="cand_single_leaf",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",  # Different structural pattern!
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_leaf_1",),
        source_lineage_root_ids=("root_leaf_1",),
        tolerance_provenance=sample_tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_paired, cand_single)
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT
    assert "conflicting_structural_patterns" in result.reason_codes


def test_regression_matrix_14_two_nearby_distinct_objects_within_tolerance_envelope_never_collapse(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """14. two nearby distinct objects both within the same tolerance envelope -> tolerance alone cannot collapse them."""
    tol = SourceToleranceProvenance.from_residuals(
        scale_ratio=100.0,
        residuals_pt=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
        stroke_width_pt=0.7,
    )
    cand_1 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_near_1",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("lineage_1",),
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )
    cand_2 = PhysicalOpeningCandidateRecord(
        candidate_id="cand_near_2",
        document_id="doc_test",
        revision_id="rev_test_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(101.5, 100.0, 141.5, 140.0),  # 1.5 pt offset <= tol (~11 pt)
        structural_pattern="door_swing_arc",
        context_kind="floor_plan_opening",
        source_observation_ids=("obs_2",),
        source_lineage_root_ids=("lineage_2",),  # Disjoint lineage!
        tolerance_provenance=tol,
        status=EvidenceResolutionStatus.CANDIDATE,
    )

    result = OpeningIdentityResolver.compare_candidates(cand_1, cand_2)
    # Tolerance envelope alone DOES NOT establish identity!
    assert result.proven_same is False
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert result.status == EvidenceResolutionStatus.ABSTAINED


# ---------------------------------------------------------------------------
# Lawful Candidate Constructor & Context Filter Enforcement Tests
# ---------------------------------------------------------------------------


def test_create_opening_candidate_enforces_schedule_context_filter(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """Candidate constructor marks candidate ABSTAINED when constructed in schedule context."""
    candidate = create_opening_candidate(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_2",
        viewport_id="vp_sched_01",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
        tolerance_provenance=sample_tolerance,
        view_kind=VIEW_KIND_SCHEDULE,  # Schedule viewport!
    )
    assert candidate.status == EvidenceResolutionStatus.ABSTAINED
    assert "non_floor_plan_context_schedule" in candidate.reason_codes


def test_create_opening_candidate_enforces_title_block_filter(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """Candidate constructor marks candidate ABSTAINED when inside title block."""
    candidate = create_opening_candidate(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(650.0, 500.0, 670.0, 520.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
        tolerance_provenance=sample_tolerance,
        viewport_bbox=(50.0, 50.0, 750.0, 550.0),
        title_block_bbox=(600.0, 480.0, 750.0, 550.0),  # Inside title block!
    )
    assert candidate.status == EvidenceResolutionStatus.ABSTAINED
    assert "title_block_or_outside_viewport" in candidate.reason_codes


def test_create_opening_candidate_enforces_sanitary_filter(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """Candidate constructor marks candidate ABSTAINED when matching sanitary fixture."""
    candidate = create_opening_candidate(
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
        layer="A-FIXT-SANITARY",
        nearby_text="WC Toilet",
    )
    assert candidate.status == EvidenceResolutionStatus.ABSTAINED
    assert "sanitary_fixture_context" in candidate.reason_codes


def test_create_opening_candidate_enforces_furniture_arc_filter(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """Candidate constructor marks candidate ABSTAINED when furniture arc is not hosted at wall jamb."""
    wall_lines = [(100.0, 0.0, 100.0, 400.0)]
    candidate = create_opening_candidate(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
        geometry=(230.0, 180.0, 270.0, 220.0),  # In room center
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
        tolerance_provenance=sample_tolerance,
        wall_lines=wall_lines,
    )
    assert candidate.status == EvidenceResolutionStatus.ABSTAINED
    assert "furniture_arc_not_at_wall_jamb" in candidate.reason_codes


def test_deterministic_candidate_id_is_reproducible_and_content_derived(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """Deterministic candidate ID is identical for identical evidence and distinct when evidence varies."""
    cid1 = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
    )
    cid2 = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_01",
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
    )
    assert cid1 == cid2
    assert cid1.startswith("cand_op_")

    cid_diff_rev = derive_deterministic_candidate_id(
        document_id="doc_test",
        revision_id="rev_02",  # Changed revision
        source_sha256="a" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_1",
        geometry=(100.0, 100.0, 140.0, 140.0),
        structural_pattern="door_swing_arc",
        source_observation_ids=("obs_1",),
        source_lineage_root_ids=("root_1",),
    )
    assert cid1 != cid_diff_rev


def test_tag_observation_source_scope_mismatch_is_ignored(
    sample_tolerance: SourceToleranceProvenance,
) -> None:
    """Tag observation from incompatible document/revision cannot bind to candidate."""
    cand = create_opening_candidate(
        document_id="doc_tender_1",
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
    )
    tag_obs_diff_doc = TagObservation(
        observation_id="tag_obs_diff_doc",
        raw_tag_text="D1",
        bounding_box=(110.0, 110.0, 130.0, 130.0),
        document_id="doc_tender_2",  # Different document!
        revision_id="rev_01",
        source_sha256="b" * 64,
        snapshot_id="snap_01",
        page_id="page_1",
        viewport_id="vp_floor_plan_p1",
    )

    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=cand,
        nearby_tags=[tag_obs_diff_doc],
        expected_semantic_family="doors",
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_mark is None
    assert "no_tag_within_source_tolerance" in result.reason_codes


