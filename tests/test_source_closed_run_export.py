"""Production regressions for benchmark-neutral source-closed run export."""
from __future__ import annotations

import inspect
import json

import pytest

import pb_source_closed_run_export as export
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace


SHA_A = "a" * 64
SHA_B = "b" * 64


def quantity(**overrides) -> QuantityEvidence:
    data = {
        "quantity_id": "qty-1",
        "family": "room_area",
        "semantic_key": "room:food-prep:area",
        "value": 13.270425,
        "unit": "m2",
        "input_entity_ids": ("canonical-floor-1",),
        "formula": "figured_length*figured_width",
        "formula_version": "1",
        "evidence_ids": ("ev-room-1",),
        "authority": "figured_dimension",
        "status": "firm",
        "confidence": 1.0,
        "metadata": {
            "project_id": "project-a",
            "document_id": "doc-a",
            "source_sha256": SHA_A,
            "revision_id": "rev-a",
        },
    }
    data.update(overrides)
    return QuantityEvidence(**data)


def trace(**overrides) -> CommercialTakeoffSourceTrace:
    data = {
        "workspace_id": 1,
        "project_id": "project-a",
        "document_id": "doc-a",
        "source_sha256": SHA_A,
        "source_page": "A140 / p8",
        "viewport_id": "vp-a140-main",
        "revision_id": "rev-a",
        "current_revision_id": "rev-a",
        "evidence_ids": ("ev-room-1",),
        "canonical_entity_ids": ("canonical-floor-1",),
    }
    data.update(overrides)
    return CommercialTakeoffSourceTrace(**data)


def test_sealed_quantity_preserves_production_identity_and_source_lineage() -> None:
    row = export.seal_source_closed_quantity(quantity(), trace=trace())
    assert row.project_id == "project-a"
    assert row.value == pytest.approx(13.270425)
    assert row.object_identity_refs == ("canonical-floor-1",)
    assert row.trace_canonical_entity_ids == ("canonical-floor-1",)
    assert row.source_sha256 == SHA_A
    assert row.revision_id == "rev-a"
    assert row.evidence_ids == ("ev-room-1",)
    assert row.lineage_ok is True
    assert len(row.fingerprint) == 64


def test_abstention_remains_none_and_is_never_coerced_to_zero() -> None:
    q = quantity(
        value=None,
        input_entity_ids=(),
        evidence_ids=(),
        abstained=True,
        blocking_reasons=("source_geometry_open",),
        status="abstained",
    )
    row = export.seal_source_closed_quantity(
        q,
        trace=trace(evidence_ids=(), canonical_entity_ids=()),
    )
    assert row.abstained is True
    assert row.value is None
    assert row.object_identity_refs == ()
    assert row.lineage_ok is True


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("project_id", "other-project", "project_id_mismatch"),
        ("document_id", "other-doc", "document_id_mismatch"),
        ("source_sha256", SHA_B, "source_sha256_mismatch"),
        ("revision_id", "rev-b", "revision_id_mismatch"),
    ],
)
def test_metadata_lineage_mismatch_is_sealed_as_blocked_not_hidden(
    field: str,
    value: object,
    reason: str,
) -> None:
    metadata = dict(quantity().metadata)
    metadata[field] = value
    row = export.seal_source_closed_quantity(
        quantity(metadata=metadata),
        trace=trace(),
    )
    assert row.lineage_ok is False
    assert reason in row.lineage_reason_codes


def test_missing_canonical_or_evidence_trace_blocks_lineage() -> None:
    row = export.seal_source_closed_quantity(
        quantity(),
        trace=trace(canonical_entity_ids=(), evidence_ids=()),
    )
    assert row.lineage_ok is False
    assert "canonical_entity_trace_incomplete" in row.lineage_reason_codes
    assert "evidence_trace_incomplete" in row.lineage_reason_codes


def test_non_abstained_quantity_without_identity_is_not_scoreable() -> None:
    row = export.seal_source_closed_quantity(
        quantity(input_entity_ids=(), evidence_ids=("ev-room-1",)),
        trace=trace(canonical_entity_ids=()),
    )
    assert row.lineage_ok is False
    assert "quantity_identity_missing" in row.lineage_reason_codes


def test_conflict_and_blockers_are_preserved_as_lineage_failures() -> None:
    row = export.seal_source_closed_quantity(
        quantity(
            status="conflict",
            blocking_reasons=("manual_review_required",),
            reason_codes=("source_conflict",),
        ),
        trace=trace(),
    )
    assert row.lineage_ok is False
    assert "quantity_publication_blocked" in row.lineage_reason_codes
    assert "quantity_status_conflict" in row.lineage_reason_codes
    assert "quantity_reason_conflict" in row.lineage_reason_codes


def test_run_is_deterministic_sorted_and_content_bound() -> None:
    q1 = quantity(quantity_id="qty-b", semantic_key="b")
    q2 = quantity(quantity_id="qty-a", semantic_key="a")
    traces = {"qty-a": trace(), "qty-b": trace()}
    run1 = export.seal_source_closed_run(
        [q1, q2],
        project_id="project-a",
        traces_by_quantity_id=traces,
    )
    run2 = export.seal_source_closed_run(
        [q2, q1],
        project_id="project-a",
        traces_by_quantity_id=traces,
    )
    assert [row.quantity_id for row in run1.quantities] == ["qty-a", "qty-b"]
    assert run1.run_id == run2.run_id
    assert run1.fingerprint == run2.fingerprint
    payload = json.loads(run1.to_json())
    assert payload["source_sha256s"] == [SHA_A]
    assert payload["fingerprint"] == run1.fingerprint


def test_sealed_fingerprint_is_invariant_to_provenance_collection_order() -> None:
    q1 = quantity(
        input_entity_ids=("canonical-floor-1", "canonical-floor-2"),
        evidence_ids=("ev-room-1", "ev-room-2"),
        reason_codes=("b", "a"),
    )
    q2 = quantity(
        input_entity_ids=("canonical-floor-2", "canonical-floor-1"),
        evidence_ids=("ev-room-2", "ev-room-1"),
        reason_codes=("a", "b"),
    )
    t1 = trace(
        evidence_ids=("ev-room-1", "ev-room-2"),
        canonical_entity_ids=("canonical-floor-1", "canonical-floor-2"),
    )
    t2 = trace(
        evidence_ids=("ev-room-2", "ev-room-1"),
        canonical_entity_ids=("canonical-floor-2", "canonical-floor-1"),
    )
    row1 = export.seal_source_closed_quantity(q1, trace=t1)
    row2 = export.seal_source_closed_quantity(q2, trace=t2)
    assert row1.fingerprint == row2.fingerprint
    assert row1.object_identity_refs == ("canonical-floor-1", "canonical-floor-2")
    assert row1.evidence_ids == ("ev-room-1", "ev-room-2")


def test_sealed_fingerprint_does_not_collapse_distinct_canonical_instances() -> None:
    first = export.seal_source_closed_quantity(
        quantity(input_entity_ids=("canonical-floor-1",)),
        trace=trace(canonical_entity_ids=("canonical-floor-1",)),
    )
    second = export.seal_source_closed_quantity(
        quantity(input_entity_ids=("canonical-floor-2",)),
        trace=trace(canonical_entity_ids=("canonical-floor-2",)),
    )
    assert first.object_identity_refs != second.object_identity_refs
    assert first.fingerprint != second.fingerprint

def test_duplicate_quantity_ids_fail_closed() -> None:
    q1 = quantity(quantity_id="qty-duplicate")
    q2 = quantity(quantity_id="qty-duplicate", semantic_key="other")
    with pytest.raises(export.SourceClosedRunConflictError, match="unique"):
        export.seal_source_closed_run(
            [q1, q2],
            project_id="project-a",
            traces_by_quantity_id={"qty-duplicate": trace()},
        )


def test_missing_trace_fails_closed() -> None:
    with pytest.raises(export.MissingSourceClosedRunTraceError, match="qty-1"):
        export.seal_source_closed_run(
            [quantity()],
            project_id="project-a",
            traces_by_quantity_id={},
        )


def test_cross_project_trace_fails_closed() -> None:
    with pytest.raises(export.SourceClosedRunConflictError, match="other-project"):
        export.seal_source_closed_run(
            [quantity()],
            project_id="project-a",
            traces_by_quantity_id={"qty-1": trace(project_id="other-project")},
        )


def test_export_has_no_benchmark_or_truth_dependency() -> None:
    source = inspect.getsource(export)
    forbidden = (
        "benchmarks.",
        "full_plan_v2",
        "reference_takeoff",
        "expected_quantity",
        "golden",
    )
    for value in forbidden:
        assert value not in source
