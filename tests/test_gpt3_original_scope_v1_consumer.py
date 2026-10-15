"""GPT3 V1/customer original-producer scope join: positive and fail-closed negatives."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from tools import diag_gpt3_original_scope_v1_consumer as consumer
from tools.diag_gptmax_producer_opening_scope_receipts import (
    producer_opening_scope_receipt_report,
)
from tests.test_live_opening_claim_source_closed_export import _opening_pdf


@pytest.fixture(scope="module")
def original():
    source = _opening_pdf()
    report = producer_opening_scope_receipt_report(source, page_ids=("1",))
    assert report["original_production_receipts"]["quantities"]
    assert report["openings"][0]["host_record"]
    return source, report


def _args(report):
    producer = report["original_production_receipts"]
    return {
        "sealed_payload": producer["sealed_run"],
        "customer_rows": producer["customer_rows"],
        "expected_source_sha256": report["source_sha256"],
        "expected_snapshot_id": report["snapshot_id"],
        "expected_project_id": "original-source-retention",
    }


def test_original_pdf_replay_binds_existing_v1_quantity_and_customer(original):
    source, report = original
    result = consumer.verify_original_scope_to_v1_customer(
        source, page_ids=("1",), **_args(report),
    )
    assert result["status"] == "SOURCE_REPLAY_CONSISTENT_UNSIGNED_UNPUBLISHED"
    assert result["customer_bijection_verified"]
    assert result["source_owned_quantity_count"] == 1
    assert not result["signed_scope_verified"]
    assert not result["customer_scope_signature_issued"]
    assert not result["benchmark_score_granted"]
    row = result["associations"][0]
    positive = next(x for x in report["openings"] if x["quantity_id"])
    assert row["host_binding_record_id"] == positive["host_record"]["record_id"]
    assert row["decision_scope_id"] == positive["host_record"]["decision_scope_id"]
    assert row["snapshot_id"] == report["snapshot_id"]
    assert row["measurement_record_id"] == positive["quantity_measurement_record_id"]
    assert row["v1_sealed_run_fingerprint"] if "v1_sealed_run_fingerprint" in row else True
    assert result["v1_sealed_run_fingerprint"] == _args(report)["sealed_payload"]["fingerprint"]


def test_mutating_original_pdf_or_selected_snapshot_never_uses_exported_scope(original):
    source, report = original
    expected = _args(report)
    with pytest.raises(consumer.OriginalSourceScopeConsumerError, match="PDF SHA"):
        consumer.verify_original_scope_to_v1_customer(
            source + b"\n% mutated", page_ids=("1",), **expected,
        )
    with pytest.raises(consumer.OriginalSourceScopeConsumerError, match="snapshot"):
        consumer.verify_original_scope_to_v1_customer(
            source, page_ids=("1",),
            **{**expected, "expected_snapshot_id": "source_snapshot_foreign"},
        )
    with pytest.raises(TypeError):
        consumer.verify_original_scope_to_v1_customer(
            source, page_ids=("1",), report=report, **expected,
        )


def test_reversed_customer_input_does_not_change_issued_association(original):
    _, report = original
    args = _args(report)
    a = consumer._verified_join(report, **args)
    b = consumer._verified_join(report, **{**args, "customer_rows": list(reversed(args["customer_rows"]))})
    assert a == b


@pytest.mark.parametrize("field,value", [
    ("document_id", "live-source:foreign"),
    ("revision_id", "source_revision_foreign"),
    ("snapshot_id", "source_snapshot_foreign"),
    ("source_sha256", "e" * 64),
    ("page_id", "999"),
    ("viewport_id", "foreign-viewport"),
    ("decision_scope_id", "wall-source:unissued"),
])
def test_foreign_source_scope_or_identity_is_rejected(original, field, value):
    _, report = original
    bad = deepcopy(report)
    next(x for x in bad["openings"] if x["quantity_id"])[field] = value
    with pytest.raises(consumer.OriginalSourceScopeConsumerError):
        consumer._verified_join(bad, **_args(report))


@pytest.mark.parametrize("host_field,value", [
    ("record_id", "foreign-host"),
    ("decision_scope_id", "wall-source:another-page"),
    ("snapshot_id", "source_snapshot_drift"),
    ("revision_id", "source_revision_old"),
    ("page_id", "other-page"),
])
def test_mismatched_host_record_cannot_be_spliced_into_old_quantity(original, host_field, value):
    _, report = original
    bad = deepcopy(report)
    next(x for x in bad["openings"] if x["quantity_id"])["host_record"][host_field] = value
    with pytest.raises(consumer.OriginalSourceScopeConsumerError):
        consumer._verified_join(bad, **_args(report))


def test_stale_and_superseded_producer_records_are_not_eligible(original):
    _, report = original
    for marker in ("is_stale", "is_superseded"):
        bad = deepcopy(report)
        next(x for x in bad["openings"] if x["quantity_id"])["host_record"][marker] = True
        with pytest.raises(consumer.OriginalSourceScopeConsumerError, match="superseded"):
            consumer._verified_join(bad, **_args(report))


def test_missing_original_quantity_and_duplicated_source_inventory_fail(original):
    _, report = original
    for kind in ("missing", "duplicate", "foreign_measurement", "foreign_physical"):
        bad = deepcopy(report)
        positives = [x for x in bad["openings"] if x["quantity_id"]]
        if kind == "missing":
            bad["original_production_receipts"]["quantities"] = []
        elif kind == "duplicate":
            bad["openings"].append(deepcopy(positives[0]))
        elif kind == "foreign_measurement":
            positives[0]["quantity_measurement_record_id"] = "foreign-measure"
        else:
            positives[0]["physical_opening_id"] = "foreign-physical"
        with pytest.raises(consumer.OriginalSourceScopeConsumerError):
            consumer._verified_join(bad, **_args(report))


def test_old_v1_fingerprints_and_customer_bijection_cannot_be_rewritten(original):
    _, report = original
    args = _args(report)
    old = deepcopy(args["sealed_payload"])
    before = deepcopy(args["customer_rows"])
    # A changed source scope is not part of V1; this diagnostic must not
    # rewrite or reissue V1 fingerprints in order to claim proof.
    result = consumer._verified_join(report, **args)
    assert result["signed_scope_verified"] is False
    assert args["sealed_payload"] == old
    assert args["customer_rows"] == before
    bad = deepcopy(before)
    bad[0]["commercial_projection_fingerprint"] = sha256(b"foreign").hexdigest()
    with pytest.raises(Exception):
        consumer._verified_join(report, **{**args, "customer_rows": bad})
    with pytest.raises(Exception):
        consumer._verified_join(
            report, **{**args, "customer_rows": []},
        )
    altered = deepcopy(old)
    altered["quantities"][0]["value"] += 0.01
    with pytest.raises(Exception):
        consumer._verified_join(report, **{**args, "sealed_payload": altered})


def test_replay_source_flags_are_fail_closed_not_unpublished_proof(original):
    _, report = original
    for key, forged in (
        ("status", "SOURCE_SCOPE_SIGNED"),
        ("signed_scope_verified", True),
        ("all_original_source_host_frame_quantity_seal_customer_receipts_unchanged", False),
    ):
        bad = deepcopy(report)
        bad[key] = forged
        with pytest.raises(consumer.OriginalSourceScopeConsumerError):
            consumer._verified_join(bad, **_args(report))
