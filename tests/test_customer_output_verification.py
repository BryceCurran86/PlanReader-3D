from __future__ import annotations

import copy

import pytest

import pb_quantity_takeoff_adapter as adapter
from pb_customer_output_verification import (
    CustomerOutputVerificationError,
    verify_sealed_customer_output,
)
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import seal_source_closed_run


SHA = "a" * 64


def quantity(
    quantity_id: str,
    entity_id: str,
    *,
    value: float | None = 12.5,
    abstained: bool = False,
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="floor_area",
        semantic_key="floor.area",
        value=value,
        unit="m²",
        input_entity_ids=(entity_id,),
        formula="documented_area",
        formula_version="1",
        evidence_ids=(f"ev-{quantity_id}",),
        authority="documented_dimension",
        status="corroborated" if not abstained else "abstained",
        confidence=0.99,
        abstained=abstained,
        blocking_reasons=("insufficient evidence",) if abstained else (),
        metadata={
            "workspace_id": 7,
            "project_id": "project-7",
            "document_id": "doc-1",
            "source_sha256": SHA,
            "revision_id": "rev-3",
            "section": "Floors",
            "location": "Level 1",
        },
    )


def trace(q: QuantityEvidence, *, include_evidence: bool = True) -> adapter.CommercialTakeoffSourceTrace:
    return adapter.CommercialTakeoffSourceTrace(
        workspace_id=7,
        project_id="project-7",
        document_id="doc-1",
        source_sha256=SHA,
        source_page="A-101 / p3",
        viewport_id=f"vp-{q.quantity_id}",
        revision_id="rev-3",
        current_revision_id="rev-3",
        evidence_ids=tuple(q.evidence_ids) if include_evidence else (),
        canonical_entity_ids=tuple(q.input_entity_ids),
    )


def authority() -> adapter.CommercialMeasurementAuthority:
    return adapter.CommercialMeasurementAuthority(method="direct_evidence")


def sealed_and_rows():
    q1 = quantity("qty-1", "floor-1", value=12.5)
    q2 = quantity("qty-2", "floor-2", value=13.0)
    abstain = quantity("qty-abstain", "floor-3", value=None, abstained=True)
    quantities = (q1, q2, abstain)
    traces = {q.quantity_id: trace(q) for q in quantities}
    authorities = {"qty-1": authority(), "qty-2": authority()}

    sealed = seal_source_closed_run(
        quantities,
        project_id="project-7",
        traces_by_quantity_id=traces,
    )
    rows = adapter.quantities_to_takeoff_output_rows(
        quantities,
        traces_by_quantity_id=traces,
        authorities_by_quantity_id=authorities,
    )
    return sealed, rows


def test_every_valid_sealed_quantity_has_exactly_one_complete_customer_row() -> None:
    sealed, rows = sealed_and_rows()

    report = verify_sealed_customer_output(sealed, rows)

    assert report.to_dict() == {
        "project_id": "project-7",
        "sealed_quantity_count": 3,
        "valid_quantity_count": 2,
        "abstained_quantity_count": 1,
        "customer_row_count": 2,
        "verified_quantity_ids": ["qty-1", "qty-2"],
        "complete": True,
    }


def test_persisted_notes_provenance_is_sufficient_for_lineage_verification() -> None:
    sealed, rows = sealed_and_rows()
    persisted = []
    for row in rows:
        copy_row = dict(row)
        copy_row.pop("commercial_projection_provenance")
        persisted.append(copy_row)

    report = verify_sealed_customer_output(sealed, persisted)

    assert report.verified_quantity_ids == ("qty-1", "qty-2")


def test_missing_valid_customer_row_fails_closed() -> None:
    sealed, rows = sealed_and_rows()

    with pytest.raises(CustomerOutputVerificationError, match="missing customer rows"):
        verify_sealed_customer_output(sealed, rows[:1])


def test_duplicate_customer_row_fails_closed() -> None:
    sealed, rows = sealed_and_rows()

    with pytest.raises(CustomerOutputVerificationError, match="duplicate customer row"):
        verify_sealed_customer_output(sealed, [*rows, dict(rows[0])])


def test_abstained_quantity_cannot_leak_into_customer_output() -> None:
    sealed, rows = sealed_and_rows()
    leaked = dict(rows[0])
    leaked["quantity_id"] = "qty-abstain"

    with pytest.raises(CustomerOutputVerificationError, match="abstained quantities leaked"):
        verify_sealed_customer_output(sealed, [*rows, leaked])


def test_customer_lineage_mismatch_fails_closed() -> None:
    sealed, rows = sealed_and_rows()
    tampered = [dict(row) for row in rows]
    tampered[0]["canonical_entity_ids"] = ["other-floor"]

    with pytest.raises(CustomerOutputVerificationError, match="canonical_entity_ids mismatch"):
        verify_sealed_customer_output(sealed, tampered)


def test_customer_source_revision_mismatch_fails_closed() -> None:
    sealed, rows = sealed_and_rows()
    tampered = [dict(row) for row in rows]
    tampered[0]["revision_id"] = "rev-4"

    with pytest.raises(CustomerOutputVerificationError, match="revision_id mismatch"):
        verify_sealed_customer_output(sealed, tampered)


def test_non_abstained_sealed_quantity_with_incomplete_lineage_fails_closed() -> None:
    q = quantity("qty-1", "floor-1")
    good_trace = trace(q)
    bad_trace = trace(q, include_evidence=False)
    sealed = seal_source_closed_run(
        (q,),
        project_id="project-7",
        traces_by_quantity_id={"qty-1": bad_trace},
    )
    row = adapter.quantity_evidence_to_takeoff_output_row(
        q,
        trace=good_trace,
        authority=authority(),
    )
    assert row is not None

    with pytest.raises(CustomerOutputVerificationError, match="incomplete lineage"):
        verify_sealed_customer_output(sealed, [row])
