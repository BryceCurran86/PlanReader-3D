"""Self-hashed payment and delivery reports must replay from source and client book."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from test_gpt3_client_procurement import fixtures
from tools.gpt3_client_procurement_awards import build_procurement_plan, _hash
from tools.gpt3_client_procurement_receipts import build_procurement_receipts
from tools.gpt3_verify_procurement_receipt_replay import (
    verify_procurement_receipt_source_replay,
    build_procurement_receipt_replay_report,
    main,
)


def _inputs():
    sealed, customers, quote, book = fixtures()
    plan = build_procurement_plan(quote, sealed, customers, book)
    po = plan["purchase_order_drafts"][0]["po_draft_id"]
    events = {
        "schema_version": "gpt3-client-procurement-events-v1",
        "procurement_fingerprint": plan["procurement_fingerprint"],
        "events": [
            {"event": "RECORD_PO_SENT", "po_draft_id": po,
             "recorded_on": "2026-10-20", "reference": "client-sent-01",
             "recorded_by": "Client"},
            {"event": "SHIPMENT_NOTICE", "po_draft_id": po,
             "requisition_id": "REQ-01", "recorded_on": "2026-10-21",
             "reference": "shipment-01", "shipped_quantity": "4"},
            {"event": "RECEIVE_DELIVERY", "po_draft_id": po,
             "requisition_id": "REQ-01", "recorded_on": "2026-10-22",
             "reference": "delivery-01", "receipt_id": "RCPT-01",
             "accepted_quantity": "4", "rejected_quantity": "0"},
        ],
    }
    received = build_procurement_receipts(plan, events)
    return {
        "sealed_run": sealed, "customers": customers, "client_quote": quote,
        "procurement_book": book, "procurement_plan": plan,
        "client_events": events, "candidate_receipts": received,
    }


def test_archived_eight_original_signed_areas_replay_client_delivery_without_authenticating_it():
    data = _inputs()
    report = verify_procurement_receipt_source_replay(**data)
    assert report["result"] == "EXACT_SIGNED_V1_CLIENT_PROCUREMENT_EVENT_REPLAY"
    assert report["client_event_count"] == 3
    assert report["supplier_delivery_independently_verified"] is False
    assert report["bank_payments_independently_verified"] is False
    assert report["external_order_sent_by_this_audit"] is False
    assert report["official_v2_accuracy"] is None


def test_rehashed_fake_received_quantity_cannot_become_actual_client_delivery():
    data = _inputs()
    fake = deepcopy(data["candidate_receipts"])
    fake["line_status"][0]["net_accepted_quantity"] = "9999"
    fake["fulfillment_fingerprint"] = _hash(fake, "fulfillment_fingerprint")
    data["candidate_receipts"] = fake
    with pytest.raises(ValueError, match="differs from exact"):
        verify_procurement_receipt_source_replay(**data)


def test_rehashed_modified_supplier_event_book_requires_corresponding_actual_receipt():
    data = _inputs()
    data["client_events"]["events"][2]["accepted_quantity"] = "3"
    with pytest.raises(ValueError, match="differs from exact"):
        verify_procurement_receipt_source_replay(**data)


def test_rehashed_procurement_fingerprint_does_not_override_original_client_bid_book():
    data = _inputs()
    wrong = deepcopy(data["procurement_plan"])
    wrong["purchase_order_drafts"][0]["gross_total"] = "999.00"
    wrong["procurement_fingerprint"] = _hash(wrong, "procurement_fingerprint")
    data["procurement_plan"] = wrong
    with pytest.raises(ValueError, match="procurement plan differs"):
        verify_procurement_receipt_source_replay(**data)


def test_create_only_cli_does_not_mutate_immutable_signed_or_client_delivery_bytes(tmp_path):
    data = _inputs()
    paths = {}
    for name, source in data.items():
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
        paths[name] = path
    original = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                for name, path in paths.items()}
    output = tmp_path / "new-fulfillment-audit.json"
    argv = []
    for name, path in paths.items():
        switch = "quote" if name == "client_quote" else (
            name.replace("_", "-")
        )
        argv.extend(["--" + switch, str(path)])
    argv.extend(["--output", str(output)])
    assert main(argv) == 0
    result = json.loads(output.read_text())
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["source_authenticated"] is False
    assert original == {name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for name, path in paths.items()}
    with pytest.raises(FileExistsError):
        main(argv)


def test_duplicate_keys_in_event_book_rejected_before_client_payment_replay(tmp_path):
    data = _inputs()
    paths = {}
    for name, item in data.items():
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(item, sort_keys=True), encoding="utf-8")
        paths[name] = path
    path = paths["client_events"]
    path.write_text(
        path.read_text().replace(
            '"schema_version":', '"schema_version": "forged", "schema_version":', 1,
        ), encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        build_procurement_receipt_replay_report(
            sealed_path=paths["sealed_run"], customer_path=paths["customers"],
            quote_path=paths["client_quote"],
            procurement_book_path=paths["procurement_book"],
            procurement_plan_path=paths["procurement_plan"],
            client_events_path=paths["client_events"],
            candidate_receipts_path=paths["candidate_receipts"],
        )
