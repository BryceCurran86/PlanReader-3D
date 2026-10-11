"""V2 diagnostics cross-check optional signed source receipts without using gold."""
import pytest
from pb_source_closed_run_export import seal_source_closed_quantity
from test_source_closed_run_export import quantity,trace
from scripts.report_full_plan_v2_readiness import produced_sealed_parity_blockers


def _original():
    row=seal_source_closed_quantity(quantity(),trace=trace())
    produced={
        "quantity_id":row.quantity_id,
        "trade_category":"flooring",
        "value":row.value,
        "unit":row.unit,
        "object_refs":list(row.object_identity_refs),
        "lineage_ok":row.lineage_ok,
        "abstained":row.abstained,
        "family":row.family,
        "semantic_key":row.semantic_key,
        "source_document_id":row.document_id,
        "source_sha256":row.source_sha256,
        "revision_id":row.revision_id,
        "sealed_quantity_fingerprint":row.fingerprint,
    }
    return row,produced


def test_exact_source_and_quantity_signatures_pass_diagnostic_projection():
    signed,produced=_original()
    assert produced_sealed_parity_blockers([produced],(signed,))==[]


@pytest.mark.parametrize(("field","value"),[
    ("family","invented-family"),
    ("semantic_key","different-room-semantics"),
    ("source_document_id","another-document"),
    ("source_sha256","b"*64),
    ("revision_id","stale-revision"),
    ("sealed_quantity_fingerprint","0"*64),
])
def test_present_source_scope_receipt_cannot_drift_from_signed_quantity(field,value):
    signed,produced=_original()
    produced[field]=value
    assert f"projection_{field}_mismatch:{signed.quantity_id}" in (
        produced_sealed_parity_blockers([produced],(signed,))
    )


def test_unprovided_legacy_optional_fields_do_not_fabricate_a_source_scope():
    signed,produced=_original()
    for field in (
        "family","semantic_key","source_document_id","source_sha256",
        "revision_id","sealed_quantity_fingerprint",
    ):
        produced.pop(field)
    assert produced_sealed_parity_blockers([produced],(signed,))==[]


def test_null_source_document_receipt_is_mismatch_not_implicit_authority():
    signed,produced=_original()
    produced["source_document_id"]=None
    assert f"projection_source_document_id_mismatch:{signed.quantity_id}" in (
        produced_sealed_parity_blockers([produced],(signed,))
    )
