"""Tests for producer-owned cross-project drawing type validation shadow authority (Item 29)."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_cross_project_drawing_type_validation_shadow import (
    ALL_DRAWING_TYPES,
    DRAWING_TYPE_COMMERCIAL,
    DRAWING_TYPE_INDUSTRIAL,
    DRAWING_TYPE_RESIDENTIAL,
    DRAWING_TYPE_STANDARDS_OUTLINED,
    GLOBAL_PRIMITIVE_CAP,
    GLOBAL_SNAP_TOLERANCE_PT,
    PRIMITIVE_CAP_INVARIANT_VERIFIED,
    PROJECT_NAME_BIAS_VETOED,
    ROLE_SEGREGATION_INVARIANT_VERIFIED,
    SNAP_TOLERANCE_INVARIANT_VERIFIED,
    SOURCE_CROSS_PROJECT_VALIDATION_CANDIDATE,
    SOURCE_CROSS_PROJECT_VALIDATION_UNAVAILABLE,
    TOPOLOGICAL_CLOSURE_INVARIANT_VERIFIED,
    UNAUTHENTICATED_DRAWING_TYPE,
    SourceCrossProjectDrawingTypeValidationAuthority,
    SourceCrossProjectDrawingTypeValidationProducer,
    SourceCrossProjectValidationSelector,
    SourceDrawingTypeValidationRecord,
)


def _make_selector(
    *,
    doc="doc-benchmark",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    drawing_type="residential",
) -> SourceCrossProjectValidationSelector:
    return SourceCrossProjectValidationSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        drawing_type=drawing_type,
    )


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceCrossProjectDrawingTypeValidationProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceCrossProjectDrawingTypeValidationAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceDrawingTypeValidationRecord(
            record_id="rec-1",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            drawing_type="residential",
            tested_snap_tolerance_pt=GLOBAL_SNAP_TOLERANCE_PT,
            tested_primitive_cap=GLOBAL_PRIMITIVE_CAP,
            topological_closure_verified=True,
            role_segregation_verified=True,
            project_bias_detected=False,
            reason_codes=(),
        )


def test_all_four_drawing_types_pass_invariants():
    producer = SourceCrossProjectDrawingTypeValidationProducer.create()
    for dtype in (DRAWING_TYPE_RESIDENTIAL, DRAWING_TYPE_COMMERCIAL, DRAWING_TYPE_STANDARDS_OUTLINED, DRAWING_TYPE_INDUSTRIAL):
        producer.register_drawing_type_evaluation(
            document_id="doc-benchmark",
            revision_id="rev-01",
            source_sha256="a" * 64,
            snapshot_id="snap-01",
            drawing_type=dtype,
            tested_snap_tolerance_pt=GLOBAL_SNAP_TOLERANCE_PT,
            tested_primitive_cap=GLOBAL_PRIMITIVE_CAP,
            topological_closure_verified=True,
            role_segregation_verified=True,
            project_name_bias_attempted=False,
        )

    authority = producer.authority()
    for dtype in (DRAWING_TYPE_RESIDENTIAL, DRAWING_TYPE_COMMERCIAL, DRAWING_TYPE_STANDARDS_OUTLINED, DRAWING_TYPE_INDUSTRIAL):
        sel = _make_selector(drawing_type=dtype)
        res = authority.resolve(sel)
        assert res.status == EvidenceResolutionStatus.CANDIDATE.value
        assert SOURCE_CROSS_PROJECT_VALIDATION_CANDIDATE in res.reason_codes
        assert SNAP_TOLERANCE_INVARIANT_VERIFIED in res.reason_codes
        assert PRIMITIVE_CAP_INVARIANT_VERIFIED in res.reason_codes
        assert TOPOLOGICAL_CLOSURE_INVARIANT_VERIFIED in res.reason_codes
        assert ROLE_SEGREGATION_INVARIANT_VERIFIED in res.reason_codes
        assert res.all_types_validated is True
        assert res.records[0].status == EvidenceResolutionStatus.CANDIDATE.value
        assert res.records[0].commercial_projection_allowed is False
        assert res.records[0].takeoff_eligible is False


def test_project_name_bias_attempt_fails_closed():
    producer = SourceCrossProjectDrawingTypeValidationProducer.create()
    producer.register_drawing_type_evaluation(
        document_id="doc-biased",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        drawing_type="commercial",
        project_name_bias_attempted=True,  # Bias attempted!
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(doc="doc-biased", drawing_type="commercial"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert PROJECT_NAME_BIAS_VETOED in res.reason_codes
    assert res.all_types_validated is False
    assert res.resolution_mode == "abstain_project_bias_or_invariant_violation"


def test_snap_tolerance_violation_fails_closed():
    producer = SourceCrossProjectDrawingTypeValidationProducer.create()
    producer.register_drawing_type_evaluation(
        document_id="doc-bad-snap",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        drawing_type="residential",
        tested_snap_tolerance_pt=5.0,  # relaxed tolerance violation!
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(doc="doc-bad-snap", drawing_type="residential"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert "snap_tolerance_invariant_violation" in res.reason_codes
    assert res.all_types_validated is False


def test_primitive_cap_violation_fails_closed():
    producer = SourceCrossProjectDrawingTypeValidationProducer.create()
    producer.register_drawing_type_evaluation(
        document_id="doc-bad-cap",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        drawing_type="residential",
        tested_primitive_cap=50000,  # weakened cap violation!
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(doc="doc-bad-cap", drawing_type="residential"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert "primitive_cap_invariant_violation" in res.reason_codes
    assert res.all_types_validated is False


def test_unauthenticated_drawing_type():
    producer = SourceCrossProjectDrawingTypeValidationProducer.create()
    producer.register_drawing_type_evaluation(
        document_id="doc-unknown",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        drawing_type="spaceship_blueprint",
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(doc="doc-unknown", drawing_type="spaceship_blueprint"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert UNAUTHENTICATED_DRAWING_TYPE in res.reason_codes


def test_unregistered_selector_returns_unavailable():
    producer = SourceCrossProjectDrawingTypeValidationProducer.create()
    authority = producer.authority()
    res = authority.resolve(_make_selector(doc="NON-EXISTENT"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_CROSS_PROJECT_VALIDATION_UNAVAILABLE in res.reason_codes
