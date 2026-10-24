"""A scope preview may accompany V1 customer projection but never authenticate a PDF.

The producer metadata in these tests is SYNTHETIC, intentionally self-attested.
"""
from dataclasses import replace
import copy
import json

import pytest

import pb_quantity_takeoff_adapter as adapter
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import (
    SourceClosedRunConflictError, seal_source_closed_run,
)
from pb_source_scope_sidecar_v2_preview import (
    build_v2_preview_scope_sidecar,
    verify_v2_preview_scope_customer_receipts,
    verify_v2_preview_scope_sidecar,
)
from test_customer_output_verification import (
    authority, quantity, trace,
)


def _fixtures():
    quantities = []
    traces = {}
    for idx in (1, 2):
        q = quantity(f"qty-{idx}", f"floor-{idx}", value=12.5 + idx)
        q = replace(q, metadata={
            **q.metadata,
            "evidence_snapshot_id": "snapshot-immutable",
            "decision_scope_id": f"scope-{idx}",
            "source_scope_record_id": f"source-record-{idx}",
        })
        t = replace(trace(q), metadata={
            "source_snapshot_id": "snapshot-immutable",
            "decision_scope_id": f"scope-{idx}",
            "source_scope_record_id": f"source-record-{idx}",
        })
        quantities.append(q)
        traces[q.quantity_id] = t
    sealed = seal_source_closed_run(
        quantities,
        project_id="project-7",
        traces_by_quantity_id=traces,
    )
    sidecar = build_v2_preview_scope_sidecar(sealed, quantities, traces)
    rows = adapter.quantities_to_takeoff_output_rows(
        quantities,
        traces_by_quantity_id=traces,
        authorities_by_quantity_id={q.quantity_id: authority() for q in quantities},
    )
    assert len(rows) == 2
    return sealed, sidecar, rows


def _rewrite_provenance(row, *, location, field, new_value):
    changed = copy.deepcopy(row)
    changed["commercial_projection_provenance"][location]["metadata"][field] = new_value
    # Both independently persisted copies agree: this passes ordinary
    # V1/commercial checks because optional producer metadata is not covered
    # by the unchanged stable commercial projection fingerprint.
    changed["notes"] = json.dumps(changed["commercial_projection_provenance"])
    return changed


def test_exact_customer_scope_receipts_bind_two_original_v1_quantities():
    sealed, sidecar, rows = _fixtures()
    original_fingerprint = sealed.fingerprint
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 2
    assert verify_v2_preview_scope_customer_receipts(sidecar, sealed, rows) is True
    assert sidecar["source_authenticated"] is False
    assert sidecar["publication_status"] == "UNPUBLISHED"
    assert sealed.fingerprint == original_fingerprint


def test_notes_only_persisted_customer_provenance_retains_scope_receipts():
    sealed, sidecar, rows = _fixtures()
    persisted = []
    for row in rows:
        copy_row = dict(row)
        copy_row.pop("quantity_id", None)
        copy_row.pop("commercial_projection_provenance", None)
        persisted.append(copy_row)
    assert verify_v2_preview_scope_customer_receipts(sidecar, sealed, persisted) is True


@pytest.mark.parametrize(("location", "field", "new_value"), [
    ("quantity", "decision_scope_id", "scope-other"),
    ("source_trace", "decision_scope_id", "scope-other"),
    ("quantity", "source_scope_record_id", "source-record-stale"),
    ("source_trace", "source_scope_record_id", "source-record-stale"),
    ("quantity", "evidence_snapshot_id", "superseded-snapshot"),
    ("source_trace", "source_snapshot_id", "superseded-snapshot"),
])
def test_conflicting_customer_metadata_cannot_inherit_preview_source_scope(
    location, field, new_value,
):
    sealed, sidecar, rows = _fixtures()
    changed = [_rewrite_provenance(
        rows[0], location=location, field=field, new_value=new_value,
    ), rows[1]]
    # Existing V1/customer parity still verifies physical quantity lineage;
    # the additional optional scope check must reject inconsistent metadata.
    assert verify_sealed_customer_output(sealed, changed).valid_quantity_count == 2
    with pytest.raises(SourceClosedRunConflictError, match="receipt conflicts"):
        verify_v2_preview_scope_customer_receipts(sidecar, sealed, changed)


def test_missing_customer_scope_receipt_fails_preview_without_hurting_v1():
    sealed, sidecar, rows = _fixtures()
    changed = [_rewrite_provenance(
        rows[0], location="source_trace", field="decision_scope_id", new_value="",
    ), rows[1]]
    assert verify_sealed_customer_output(sealed, changed).valid_quantity_count == 2
    with pytest.raises(SourceClosedRunConflictError, match="malformed"):
        verify_v2_preview_scope_customer_receipts(sidecar, sealed, changed)


def test_duplicate_customer_projection_fails_before_preview_scope_check():
    sealed, sidecar, rows = _fixtures()
    with pytest.raises(Exception, match="duplicate customer row"):
        verify_v2_preview_scope_customer_receipts(
            sidecar, sealed, [rows[0], rows[1], copy.deepcopy(rows[0])],
        )


def test_cross_revision_sealed_run_cannot_reuse_prior_preview_or_customer_rows():
    sealed, sidecar, rows = _fixtures()
    altered = copy.deepcopy(sidecar)
    altered["scope_records"][0]["revision_id"] = "rev-999"
    with pytest.raises(SourceClosedRunConflictError, match="integrity fingerprint"):
        verify_v2_preview_scope_customer_receipts(altered, sealed, rows)


def test_manual_estimator_row_does_not_invalidate_source_customer_scope_bijection():
    sealed, sidecar, rows = _fixtures()
    manually_entered = {"description": "manual allowance", "quantity": 1.0}
    assert verify_v2_preview_scope_customer_receipts(
        sidecar, sealed, [*rows, manually_entered],
    ) is True


def test_preview_customer_receipt_check_does_not_upgrade_self_attested_authority():
    sealed, sidecar, rows = _fixtures()
    assert verify_v2_preview_scope_sidecar(sidecar, sealed)
    assert verify_v2_preview_scope_customer_receipts(sidecar, sealed, rows)
    assert sidecar["source_authenticated"] is False
    assert all(
        record["source_record_authentication"]
        == "SOURCE_PRODUCER_AUTHORITY_NOT_INDEPENDENTLY_VERIFIED"
        for record in sidecar["scope_records"]
    )
