"""Original producer receipts cannot be replaced by matching caller metadata."""
from dataclasses import replace
from types import MappingProxyType

import pytest

import tools.diag_gptmax_producer_opening_scope_receipts as module
from tests.test_live_opening_claim_source_closed_export import _opening_pdf
from tests.test_live_wall_opening_authority_composition import _two_page_host_pdf


@pytest.fixture(scope="module")
def original():
    return _opening_pdf()


def test_actual_pdf_issues_original_scope_and_existing_quantity_without_signing_it(original):
    r = module.producer_opening_scope_receipt_report(original, page_ids=("1",))
    assert r["status"] == "SOURCE_REPLAY_UNSIGNED_UNPUBLISHED"
    assert len(r["openings"]) == 1
    row = r["openings"][0]
    host = row["host_record"]
    assert row["source_scope_record_replayed"]
    assert host["decision_scope_id"] == row["decision_scope_id"]
    assert host["snapshot_id"] == row["snapshot_id"] == r["snapshot_id"]
    assert host["opening_identity_id"] == row["physical_opening_id"]
    assert host["record_id"] == row["frame_record"]["host_binding_record_id"]
    assert row["first_failing_authority_stage"] == "versioned_signed_scope_consumer"
    q = r["original_production_receipts"]["quantities"][0]
    assert q["quantity_id"] == row["quantity_id"]
    assert row["quantity_measurement_record_id"] in q["evidence_ids"]
    assert host["record_id"] in q["evidence_ids"]
    assert r["all_original_source_host_frame_quantity_seal_customer_receipts_unchanged"]
    assert r["original_production_receipts"]["customer_verification"]["valid_quantity_count"] == 1
    assert not row["signed_scope_verified"]
    assert not any(r[k] for k in ("signed_scope_verified", "new_host_granted",
        "new_quantity_granted", "count_granted", "benchmark_score_granted"))


def test_same_source_deterministic_replay_and_no_metadata_input(original):
    a = module.producer_opening_scope_receipt_report(original, page_ids=("1",))
    b = module.producer_opening_scope_receipt_report(original, page_ids=("1",))
    assert a == b
    with pytest.raises(TypeError):
        module.producer_opening_scope_receipt_report(
            {"snapshot_id": a["snapshot_id"], "source_sha256": a["source_sha256"]}, page_ids=("1",))
    with pytest.raises(TypeError):
        module.producer_opening_scope_receipt_report(original, page_ids=("1",),
            canonical_openings=a["openings"])


@pytest.mark.parametrize("field,value", [("snapshot_id", "foreign"),
    ("revision_id", "foreign"), ("document_id", "foreign"),
    ("source_sha256", "a" * 64), ("page_id", "2"),
    ("decision_scope_id", "unissued-scope")])
def test_original_positive_cannot_bless_foreign_or_unissued_selector(original, monkeypatch, field, value):
    compose = module.compose_live_wall_opening_authority
    def damaged(**kwargs):
        c = compose(**kwargs)
        selectors = {k: replace(v, **{field: value}) for k, v in c.binding_selectors.items()}
        return replace(c, binding_selectors=MappingProxyType(selectors))
    monkeypatch.setattr(module, "compose_live_wall_opening_authority", damaged)
    with pytest.raises((RuntimeError, ValueError)):
        module.producer_opening_scope_receipt_report(original, page_ids=("1",))


def test_duplicate_producer_physical_inventory_is_not_collapsed(original, monkeypatch):
    compose = module.compose_live_physical_opening_voids
    def damaged(**kwargs):
        v = compose(**kwargs)
        return replace(v, canonical_openings=v.canonical_openings + v.canonical_openings)
    monkeypatch.setattr(module, "compose_live_physical_opening_voids", damaged)
    with pytest.raises((RuntimeError, ValueError)):
        module.producer_opening_scope_receipt_report(original, page_ids=("1",))


def test_missing_producer_trace_cannot_make_partial_inventory_complete(original, monkeypatch):
    compose = module.compose_live_physical_opening_voids
    def damaged(**kwargs):
        return replace(compose(**kwargs), traces=())
    monkeypatch.setattr(module, "compose_live_physical_opening_voids", damaged)
    with pytest.raises(RuntimeError, match="inventory disagreement"):
        module.producer_opening_scope_receipt_report(original, page_ids=("1",))


def test_warm_source_mutation_during_observation_never_escapes(original, monkeypatch):
    observe = module._observe
    def damaged(source, pub, *args):
        rows = observe(source, pub, *args)
        source._producer._store.source_bytes_by_revision[pub.revision.revision_id] = b"foreign bytes"
        return rows
    monkeypatch.setattr(module, "_observe", damaged)
    with pytest.raises((RuntimeError, ValueError)):
        module.producer_opening_scope_receipt_report(original, page_ids=("1",))


def test_decoded_source_roots_are_never_aliased_by_same_pdf_or_page():
    data = _two_page_host_pdf()
    a = module.producer_opening_scope_receipt_report(data, page_ids=("2",))
    b = module.producer_opening_scope_receipt_report(data, page_ids=("2",), decoded_page_ids=("2",))
    assert a["source_sha256"] == b["source_sha256"]
    assert a["snapshot_id"] != b["snapshot_id"]
    assert a["decoded_page_ids"] == ("1", "2")
    assert b["decoded_page_ids"] == ("2",)
    for r in (a, b):
        assert r["openings"]
        assert all(x["snapshot_id"] == r["snapshot_id"] for x in r["openings"])
        assert all(x["quantity_id"] is None for x in r["openings"])
        assert not r["new_quantity_granted"]


@pytest.mark.parametrize("pages", [(), ("01",), ("0",), ("1", "1"), (1,), ("missing",), "12"])
def test_invalid_source_selectors_are_not_normalized_into_original_scope(original, pages):
    with pytest.raises(ValueError):
        module.producer_opening_scope_receipt_report(original, page_ids=pages)


def test_undecoded_page_cannot_borrow_source_root(original):
    with pytest.raises(ValueError):
        module.producer_opening_scope_receipt_report(original, page_ids=("2",), decoded_page_ids=("1",))


def test_nonexistent_source_page_is_not_a_successful_empty_census(original):
    with pytest.raises(ValueError, match="not decoded"):
        module.producer_opening_scope_receipt_report(original, page_ids=("2",))
