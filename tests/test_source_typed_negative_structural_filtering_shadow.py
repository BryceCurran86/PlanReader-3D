import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_typed_negative_structural_filtering_shadow import (
    SourceTypedNegativeStructuralFilteringShadowAuthority,
    TypedNegativeFilteringReceipt,
    NegativeEvidenceKind,
    StructuralCandidacyStatus,
    SCHEMA_VERSION,
)


def test_positive_structural_wall_retained_against_witness():
    authority = SourceTypedNegativeStructuralFilteringShadowAuthority()

    # Register witness line atom touching one end of the wall
    authority.register_negative_evidence_atom(
        kind=NegativeEvidenceKind.DIMENSION_WITNESS_LINE,
        start_pt=(100.0, 200.0),
        end_pt=(100.0, 250.0),
        stroke_width_pt=0.25,
        confidence=0.5,
        reason_code="DIMENSION_WITNESS_PROXIMITY",
    )

    # Evaluate thick structural wall segment touching at (100.0, 200.0)
    eval_res = authority.evaluate_candidate_segment(
        segment_id="WALL_SEG_01",
        start_pt=(100.0, 200.0),
        end_pt=(300.0, 200.0),
        stroke_width_pt=0.96,
        is_closed_hatch_boundary=True,
        has_parallel_corroboration=True,
    )

    assert eval_res.status == StructuralCandidacyStatus.CONFIRMED_STRUCTURAL_WALL
    assert eval_res.positive_structural_score >= 0.7
    assert eval_res.decision_reason_code == "CONFIRMED_WALL_POSITIVE_EVIDENCE_DOMINATES"
    assert len(eval_res.opposing_atoms) == 1


def test_thin_witness_disqualified_by_negative_evidence():
    authority = SourceTypedNegativeStructuralFilteringShadowAuthority()

    authority.register_negative_evidence_atom(
        kind=NegativeEvidenceKind.DIMENSION_WITNESS_LINE,
        start_pt=(50.0, 50.0),
        end_pt=(50.0, 150.0),
        stroke_width_pt=0.2,
        confidence=0.9,
        reason_code="COLLINEAR_WITH_DIM_STRING",
        metadata={"target_segment_id": "WITNESS_SEG_01"},
    )

    eval_res = authority.evaluate_candidate_segment(
        segment_id="WITNESS_SEG_01",
        start_pt=(50.0, 50.0),
        end_pt=(50.0, 150.0),
        stroke_width_pt=0.2,
        is_closed_hatch_boundary=False,
        has_parallel_corroboration=False,
    )

    assert eval_res.status == StructuralCandidacyStatus.DISQUALIFIED_BY_NEGATIVE_EVIDENCE
    assert eval_res.negative_evidence_score >= 0.8
    assert "DISQUALIFIED" in eval_res.decision_reason_code


def test_zero_length_primitive_disqualified():
    authority = SourceTypedNegativeStructuralFilteringShadowAuthority()

    eval_res = authority.evaluate_candidate_segment(
        segment_id="ZERO_LEN",
        start_pt=(10.0, 10.0),
        end_pt=(10.0, 10.0),
        stroke_width_pt=0.5,
    )

    assert eval_res.status == StructuralCandidacyStatus.DISQUALIFIED_BY_NEGATIVE_EVIDENCE
    assert eval_res.decision_reason_code == "ZERO_LENGTH_PRIMITIVE"


def test_compile_filtering_receipt():
    authority = SourceTypedNegativeStructuralFilteringShadowAuthority()

    e1 = authority.evaluate_candidate_segment(
        segment_id="W1",
        start_pt=(0.0, 0.0),
        end_pt=(100.0, 0.0),
        stroke_width_pt=0.8,
        is_closed_hatch_boundary=True,
    )

    authority.register_negative_evidence_atom(
        kind=NegativeEvidenceKind.GRID_LINE,
        start_pt=(20.0, 0.0),
        end_pt=(20.0, 500.0),
        stroke_width_pt=0.2,
        confidence=0.9,
        reason_code="GRID_AXIS_DASH_DOT",
        metadata={"target_segment_id": "GRID_SEG"},
    )

    e2 = authority.evaluate_candidate_segment(
        segment_id="GRID_SEG",
        start_pt=(20.0, 0.0),
        end_pt=(20.0, 500.0),
        stroke_width_pt=0.2,
    )

    receipt = authority.compile_filtering_receipt(
        document_id="DOC_TYPED_NEG",
        revision_id="REV_1",
        source_sha256="12345678" * 8,
        evaluations=[e1, e2],
    )

    assert isinstance(receipt, TypedNegativeFilteringReceipt)
    assert receipt.total_evaluated_segments == 2
    assert receipt.retained_structural_count == 1
    assert receipt.disqualified_count == 1
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_TYPED_NEG"
    assert len(d["evaluations"]) == 2


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        TypedNegativeFilteringReceipt(
            receipt_id="FAKE",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_evaluated_segments=0,
            retained_structural_count=0,
            disqualified_count=0,
            evaluations=(),
            status=EvidenceResolutionStatus.CANDIDATE,
        )
