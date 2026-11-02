"""Tests for Milestone 2: Lot 16 2142 BIFOLD plan-to-elevation structural authority."""

from pathlib import Path

import pytest

from pb_bifold_plan_elevation_structural_authority import (
    BifoldPlanElevationStructuralAuthority,
    BifoldPlanElevationStructuralProducer,
    DividerStructuralRole,
    ElevationEvidenceRecord,
    PlanOpeningGeometry,
)
from pb_migration_contracts import EvidenceResolutionStatus


@pytest.fixture
def producer() -> BifoldPlanElevationStructuralProducer:
    return BifoldPlanElevationStructuralProducer(
        document_id="doc_test_lot16",
        revision_id="rev_test_lot16",
        source_sha256="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
    )


@pytest.fixture
def authority(
    producer: BifoldPlanElevationStructuralProducer,
) -> BifoldPlanElevationStructuralAuthority:
    return BifoldPlanElevationStructuralAuthority(producer)


def test_sealed_permission_boundaries(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    plan = PlanOpeningGeometry(
        physical_opening_id="opening_lot16_bifold",
        gap_box_pt=(969.36, 295.20, 972.72, 413.28),
        span_pt=118.08,
    )
    record = authority.assess_opening(plan_geometry=plan)
    assert record.commercial_projection_allowed is False
    assert record.takeoff_eligible is False
    assert record.shadow_only is True
    assert record.assessment_id.startswith("bifold_plan_elevation_assessment_")

    # Invalid arguments must raise ValueError
    with pytest.raises(ValueError, match="physical_opening_id required"):
        PlanOpeningGeometry(
            physical_opening_id="", gap_box_pt=(0, 0, 10, 10), span_pt=10.0
        )

    with pytest.raises(ValueError, match="span_pt must be positive"):
        PlanOpeningGeometry(
            physical_opening_id="valid_id", gap_box_pt=(0, 0, 10, 10), span_pt=0.0
        )


def test_synthetic_positive_matched_elevation_and_schedule(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    plan = PlanOpeningGeometry(
        physical_opening_id="opening_positive_bifold",
        gap_box_pt=(100.0, 200.0, 110.0, 318.08),
        span_pt=118.08,
        native_text_records=("2142", "BIFOLD"),
    )
    elevation = ElevationEvidenceRecord(
        document_id="doc_test_lot16",
        sheet_number=4,
        elevation_title="ELEVATION 2 - REAR",
        opening_tags_found=("2142 BIFOLD",),
        direct_identifier_witnessed=True,
    )
    record = authority.assess_opening(
        plan_geometry=plan,
        elevation_records=(elevation,),
        schedule_evidence_ids=("schedule_row_2142_bifold",),
    )
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.first_remaining_gate == "none"
    assert record.elevation_identity_proven is True
    assert record.axis_order_resolved is True
    assert record.opening_kind_granted is True
    assert record.competing_frame_assemblies_detected is False


def test_lot16_missing_elevation_cross_view_tag_abstains(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    # Lot 16 case without competing dimension chains: Sheet 4 and 5 have other tags
    plan = PlanOpeningGeometry(
        physical_opening_id="physical_opening_existence_00d50eb9ef77840451522efdc25f2df5",
        gap_box_pt=(969.36, 295.20, 972.72, 413.28),
        span_pt=118.08,
        native_text_records=("2142", "BIFOLD"),
    )
    elev_sheet_4 = ElevationEvidenceRecord(
        document_id="doc_test_lot16",
        sheet_number=4,
        elevation_title="ELEVATION 1",
        opening_tags_found=("1218 SGW", "0630 FG", "0906 SGW obs"),
    )
    elev_sheet_5 = ElevationEvidenceRecord(
        document_id="doc_test_lot16",
        sheet_number=5,
        elevation_title="ELEVATION 3",
        opening_tags_found=("0615 SGW", "1215 SGW obs", "2127 STACKER"),
    )
    record = authority.assess_opening(
        plan_geometry=plan,
        elevation_records=(elev_sheet_4, elev_sheet_5),
    )
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert record.first_remaining_gate == "cross_view_elevation_role_unproven"
    assert record.elevation_identity_proven is False


def test_competing_frame_assemblies_and_70mm_divider_conflict(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    # Lot 16 actual geometry: 70 mm divider with competing 2210 mm, 3310 mm, and 4165.6 mm spans
    plan = PlanOpeningGeometry(
        physical_opening_id="physical_opening_existence_00d50eb9ef77840451522efdc25f2df5",
        gap_box_pt=(969.36, 295.20, 972.72, 413.28),
        span_pt=118.08,
        native_text_records=("2142", "BIFOLD"),
        dimension_chain_spans_mm=(1050.0, 70.0, 1090.0, 2210.0, 1030.0, 3310.0),
        has_divider_tick=True,
        divider_width_mm=70.0,
    )
    record = authority.assess_opening(plan_geometry=plan)
    assert record.status is EvidenceResolutionStatus.CONFLICT
    assert record.first_remaining_gate == "competing_frame_assemblies_unresolved"
    assert record.competing_frame_assemblies_detected is True
    assert (
        record.divider_role is DividerStructuralRole.AMBIGUOUS_COMPETING_FRAME_SEPARATOR
    )
    assert 2210.0 in record.candidate_frame_spans_mm
    assert 3310.0 in record.candidate_frame_spans_mm
    assert any(
        pytest.approx(4165.6, abs=5.0) == s for s in record.candidate_frame_spans_mm
    )


def test_elevation_without_schedule_withholds_axis_order_and_kind(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    plan = PlanOpeningGeometry(
        physical_opening_id="opening_no_sched",
        gap_box_pt=(100.0, 200.0, 110.0, 318.08),
        span_pt=118.08,
        native_text_records=("2142", "BIFOLD"),
    )
    elevation = ElevationEvidenceRecord(
        document_id="doc_test_lot16",
        sheet_number=4,
        elevation_title="ELEVATION 2",
        opening_tags_found=("2142 BIFOLD",),
        direct_identifier_witnessed=True,
    )
    # Elevation matched, but schedule missing
    record = authority.assess_opening(
        plan_geometry=plan,
        elevation_records=(elevation,),
        schedule_evidence_ids=(),
    )
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert record.first_remaining_gate == "dimension_ownership_unproven"
    assert record.elevation_identity_proven is True
    assert record.axis_order_resolved is False
    assert record.opening_kind_granted is False


def test_visual_similarity_cannot_grant_elevation_identity(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    plan = PlanOpeningGeometry(
        physical_opening_id="opening_lookalike",
        gap_box_pt=(100.0, 200.0, 110.0, 318.08),
        span_pt=118.08,
        native_text_records=("2142", "BIFOLD"),
    )
    # Elevation has 2127 STACKER which looks similar (multi-panel sliding)
    elevation = ElevationEvidenceRecord(
        document_id="doc_test_lot16",
        sheet_number=5,
        elevation_title="ELEVATION 4",
        opening_tags_found=("2127 STACKER",),
        direct_identifier_witnessed=False,
    )
    record = authority.assess_opening(
        plan_geometry=plan,
        elevation_records=(elevation,),
    )
    assert record.elevation_identity_proven is False
    assert record.status is EvidenceResolutionStatus.ABSTAINED


def test_metamorphic_transformation_invariance(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    p1 = PlanOpeningGeometry(
        physical_opening_id="op_meta",
        gap_box_pt=(100.0, 200.0, 110.0, 318.08),
        span_pt=118.08,
        dimension_chain_spans_mm=(2210.0, 3310.0),
        has_divider_tick=True,
        divider_width_mm=70.0,
    )
    # Translated by (500, 300)
    p2 = PlanOpeningGeometry(
        physical_opening_id="op_meta",
        gap_box_pt=(600.0, 500.0, 610.0, 618.08),
        span_pt=118.08,
        dimension_chain_spans_mm=(2210.0, 3310.0),
        has_divider_tick=True,
        divider_width_mm=70.0,
    )
    r1 = authority.assess_opening(plan_geometry=p1)
    r2 = authority.assess_opening(plan_geometry=p2)
    assert r1.status == r2.status
    assert r1.first_remaining_gate == r2.first_remaining_gate
    assert r1.assessment_id == r2.assessment_id
    assert r1.candidate_frame_spans_mm == r2.candidate_frame_spans_mm


def test_input_ordering_invariance(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    plan1 = PlanOpeningGeometry(
        physical_opening_id="op_order",
        gap_box_pt=(100.0, 200.0, 110.0, 318.08),
        span_pt=118.08,
        dimension_chain_spans_mm=(3310.0, 2210.0),
        has_divider_tick=True,
        divider_width_mm=70.0,
    )
    plan2 = PlanOpeningGeometry(
        physical_opening_id="op_order",
        gap_box_pt=(100.0, 200.0, 110.0, 318.08),
        span_pt=118.08,
        dimension_chain_spans_mm=(2210.0, 3310.0),
        has_divider_tick=True,
        divider_width_mm=70.0,
    )
    r1 = authority.assess_opening(plan_geometry=plan1)
    r2 = authority.assess_opening(plan_geometry=plan2)
    assert r1.assessment_id == r2.assessment_id
    assert r1.candidate_frame_spans_mm == r2.candidate_frame_spans_mm


def test_lot16_actual_pdf_source_regression(
    authority: BifoldPlanElevationStructuralAuthority,
) -> None:
    pdf_path = Path(
        r"C:\claude-work\main-ref\documents\sources\1. Construction Plans - Lot 16 Power (REV E).pdf"
    )
    if not pdf_path.exists():
        pytest.skip("Lot 16 original PDF not available locally")

    import fitz

    doc = fitz.open(pdf_path)
    # Verify Page 3 has 2142 and BIFOLD
    p3_text = doc[2].get_text()
    assert "2142" in p3_text
    assert "BIFOLD" in p3_text

    # Verify Page 4 and Page 5 do NOT have 2142 or BIFOLD
    p4_text = doc[3].get_text()
    p5_text = doc[4].get_text()
    assert "2142" not in p4_text
    assert "BIFOLD" not in p4_text
    assert "2142" not in p5_text
    assert "BIFOLD" not in p5_text

    # Extract tags from Pages 4 and 5
    tags_p4 = [
        w[4] for w in doc[3].get_text("words") if any(k in w[4] for k in ["SGW", "FG"])
    ]
    tags_p5 = [
        w[4]
        for w in doc[4].get_text("words")
        if any(k in w[4] for k in ["SGW", "STACKER"])
    ]

    elev_p4 = ElevationEvidenceRecord(
        document_id="doc_lot16_power",
        sheet_number=4,
        elevation_title="ELEVATIONS 1 & 2",
        opening_tags_found=tuple(tags_p4),
    )
    elev_p5 = ElevationEvidenceRecord(
        document_id="doc_lot16_power",
        sheet_number=5,
        elevation_title="ELEVATIONS 3 & 4",
        opening_tags_found=tuple(tags_p5),
    )

    plan = PlanOpeningGeometry(
        physical_opening_id="physical_opening_existence_00d50eb9ef77840451522efdc25f2df5",
        gap_box_pt=(969.36, 295.20, 972.72, 413.28),
        span_pt=118.08,
        native_text_records=("2142", "BIFOLD"),
        dimension_chain_spans_mm=(1050.0, 70.0, 1090.0, 2210.0, 1030.0, 3310.0),
        has_divider_tick=True,
        divider_width_mm=70.0,
    )

    record = authority.assess_opening(
        plan_geometry=plan,
        elevation_records=(elev_p4, elev_p5),
    )
    # The competing frame assemblies and 70 mm divider result in CONFLICT
    assert record.status is EvidenceResolutionStatus.CONFLICT
    assert record.first_remaining_gate == "competing_frame_assemblies_unresolved"
    assert record.elevation_identity_proven is False
    assert record.competing_frame_assemblies_detected is True
    assert record.commercial_projection_allowed is False
    assert record.takeoff_eligible is False
