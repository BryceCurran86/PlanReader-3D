"""Archived eight signed Lot16 source rows feed CLIENT supplied procurement only."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.gpt3_verified_customer_quote import build_verified_customer_quote
from tools.gpt3_client_procurement_awards import (
    build_procurement_plan, rfq_csv, draft_po_csv,
)
from tools.gpt3_client_procurement_receipts import (
    build_procurement_receipts, fulfillment_csv,
)

ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015/production"


def fixtures():
    signed = json.loads((ARCHIVED / "source_sealed_run.json").read_text(encoding="utf-8"))
    rows = json.loads((ARCHIVED / "verified_customer_rows.json").read_text(encoding="utf-8"))
    rates = {
        "schema_version": "gpt3-client-rates-v1",
        "project_id": signed["project_id"], "currency": "AUD",
        "issued_on": "2026-10-17", "expires_on": "2026-11-17",
        "include_manual_allowances": False,
        "manual_allowances": [],
        "rates": [{
            "scope": "family", "key": "opening_area", "unit": "m2",
            "material": "40.00", "labour": "20.00", "plant": "10.00",
            "subcontract": "5.00", "markup_pct": "15", "waste_pct": "2",
            "labour_hours_per_unit": "1",
        }],
        "adjustments": {"overhead_pct": "5", "contingency_pct": "2",
                        "discount_pct": "0", "tax_pct": "10"},
    }
    quote = build_verified_customer_quote(signed, rows, rates)
    source_id = quote["items"][0]["quantity_id"]
    book = {
        "schema_version": "gpt3-client-procurement-v1",
        "project_id": signed["project_id"],
        "quote_fingerprint": quote["quote_fingerprint"],
        "currency": "AUD", "as_of": "2026-10-20",
        "suppliers": [
            {"supplier_id": "supplier-A", "supplier_name": "Synthetic supplier A",
             "currency": "AUD", "eligible_for_award": True,
             "payment_terms_days": 14},
            {"supplier_id": "supplier-B", "supplier_name": "Synthetic supplier B",
             "currency": "AUD", "eligible_for_award": True,
             "payment_terms_days": 7},
        ],
        "requisitions": [{
            "requisition_id": "REQ-01", "description": "Client planned purchased framing units",
            "purchase_unit": "each", "requested_purchase_quantity": "3.2",
            "related_signed_quantity_ids": [source_id],
            "needed_by": "2026-11-05", "delivery_location": "Example client site",
            "maximum_approved_gross": "100.00",
        }],
        "supplier_offers": [
            {"offer_id": "OFFER-001", "requisition_id": "REQ-01",
             "supplier_id": "supplier-A", "purchase_unit": "each",
             "unit_price_ex_tax": "10.00", "freight_ex_tax": "5.00",
             "minimum_order_quantity": "0", "pack_multiple": "2",
             "lead_days": 5, "tax_pct": "10", "valid_through": "2026-10-28"},
            {"offer_id": "OFFER-002", "requisition_id": "REQ-01",
             "supplier_id": "supplier-B", "purchase_unit": "each",
             "unit_price_ex_tax": "20.00", "freight_ex_tax": "0",
             "minimum_order_quantity": "0", "pack_multiple": "1",
             "lead_days": 4, "tax_pct": "10", "valid_through": "2026-10-28"},
        ],
        "client_awards": [{
            "requisition_id": "REQ-01", "offer_id": "OFFER-001",
            "approved_by": "Synthetic client", "approval_reference": "client-approval",
            "approved_on": "2026-10-20",
        }],
    }
    return signed, rows, quote, book


def test_client_planned_material_and_source_quantity_are_separate():
    signed, rows, quote, book = fixtures()
    result = build_procurement_plan(quote, signed, rows, book)
    assert result["material_requirement_authenticated_from_drawings"] is False
    assert result["official_four_project_accuracy"] is None
    assert len(result["purchase_order_drafts"]) == 1
    assert result["purchase_order_drafts"][0]["status"] == "DRAFT_NOT_TRANSMITTED"
    assert result["offers"][0]["purchase_quantity"] == "4"
    assert result["offers"][0]["overbuy_quantity"] == "0.8"
    assert result["offers"][0]["gross_cost"] == "49.50"
    assert result["purchase_order_drafts"][0]["lines"][0]["related_signed_quantity_ids"] == [
        quote["items"][0]["quantity_id"]
    ]
    assert "REQ-01" in rfq_csv(result)
    assert "draft-po-" in draft_po_csv(result)


def test_bid_compare_does_not_auto_award_and_no_zero_cost_shortcut():
    signed, rows, quote, book = fixtures()
    book["client_awards"] = []
    result = build_procurement_plan(quote, signed, rows, book)
    assert result["supplier_bid_comparison"][0]["lowest_eligible_offer_id"] == "OFFER-001"
    assert result["purchase_order_drafts"] == []
    assert result["unawarded_requisition_ids"] == ["REQ-01"]


def test_expired_late_and_over_budget_offers_cannot_be_awarded():
    signed, rows, quote, book = fixtures()
    book["supplier_offers"][0]["valid_through"] = "2026-10-19"
    with pytest.raises(ValueError, match="invalid supplier offer"):
        build_procurement_plan(quote, signed, rows, book)
    book["supplier_offers"][0]["valid_through"] = "2026-10-28"
    book["requisitions"][0]["maximum_approved_gross"] = "1.00"
    with pytest.raises(ValueError, match="invalid supplier offer"):
        build_procurement_plan(quote, signed, rows, book)


def test_suppliers_in_other_currency_not_silently_ranked():
    signed, rows, quote, book = fixtures()
    book["suppliers"][0]["currency"] = "USD"
    with pytest.raises(ValueError, match="currencies"):
        build_procurement_plan(quote, signed, rows, book)


def test_accepted_receipts_rejections_returns_invoices_payments():
    signed, rows, quote, book = fixtures()
    procurement = build_procurement_plan(quote, signed, rows, book)
    pid = procurement["purchase_order_drafts"][0]["po_draft_id"]
    event_book = {
        "schema_version": "gpt3-client-procurement-events-v1",
        "procurement_fingerprint": procurement["procurement_fingerprint"],
        "events": [
            {"event": "RECORD_PO_SENT", "po_draft_id": pid,
             "recorded_on": "2026-10-20", "reference": "sent-mail-01",
             "recorded_by": "Client"},
            {"event": "SHIPMENT_NOTICE", "po_draft_id": pid,
             "requisition_id": "REQ-01", "recorded_on": "2026-10-23",
             "reference": "advice-note-001", "shipped_quantity": "4"},
            {"event": "RECEIVE_DELIVERY", "po_draft_id": pid,
             "requisition_id": "REQ-01", "recorded_on": "2026-10-25",
             "reference": "client-check-in", "receipt_id": "RCPT-1",
             "accepted_quantity": "3", "rejected_quantity": "1"},
            {"event": "RETURN_ACCEPTED", "po_draft_id": pid,
             "requisition_id": "REQ-01", "recorded_on": "2026-10-25",
             "reference": "client-return", "return_id": "RETURN-01",
             "returned_quantity": "1"},
            {"event": "SUPPLIER_INVOICE", "po_draft_id": pid,
             "requisition_id": "REQ-01", "recorded_on": "2026-10-26",
             "reference": "supplier-invoice", "invoice_id": "INV-01",
             "gross_amount": "25.00"},
            {"event": "RECORD_SUPPLIER_PAYMENT", "po_draft_id": pid,
             "recorded_on": "2026-10-27", "reference": "client-payment-reference",
             "invoice_id": "INV-01", "payment_id": "PAY-01",
             "amount": "10.00"},
        ],
    }
    fulfillment = build_procurement_receipts(procurement, event_book)
    assert fulfillment["line_status"][0]["net_accepted_quantity"] == "2"
    assert fulfillment["line_status"][0]["outstanding_purchase_quantity"] == "2"
    assert fulfillment["line_status"][0]["status"] == "PARTIALLY_RECEIVED"
    assert fulfillment["supplier_financial_summary"]["outstanding_payable_gross"] == "15.00"
    assert fulfillment["external_orders_sent_by_this_tool"] is False
    assert fulfillment["bank_payments_verified"] is False
    assert fulfillment["signed_source_measurements_changed"] is False
    assert "PARTIALLY_RECEIVED" in fulfillment_csv(fulfillment)
    bad = deepcopy(event_book)
    bad["events"].append(deepcopy(bad["events"][-1]))
    with pytest.raises(ValueError, match="duplicate|cannot reuse"):
        build_procurement_receipts(procurement, bad)


def test_no_supplier_invoice_without_actual_client_recorded_receipt():
    signed, rows, quote, book = fixtures()
    procurement = build_procurement_plan(quote, signed, rows, book)
    pid = procurement["purchase_order_drafts"][0]["po_draft_id"]
    events = {"schema_version": "gpt3-client-procurement-events-v1",
              "procurement_fingerprint": procurement["procurement_fingerprint"],
              "events": [
                  {"event": "RECORD_PO_SENT", "po_draft_id": pid,
                   "recorded_on": "2026-10-20", "reference": "sent",
                   "recorded_by": "Client"},
                  {"event": "SUPPLIER_INVOICE", "po_draft_id": pid,
                   "requisition_id": "REQ-01", "recorded_on": "2026-10-21",
                   "reference": "invoice", "invoice_id": "i",
                   "gross_amount": "10.00"},
              ]}
    with pytest.raises(ValueError, match="requires net accepted"):
        build_procurement_receipts(procurement, events)
