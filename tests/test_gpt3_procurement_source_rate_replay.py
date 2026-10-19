"""Supplier PO drafts must not accept a rehashed but repriced source quote."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from tools import gpt3_client_procurement_awards as procurement
from tools.gpt3_verified_customer_quote import build_verified_customer_quote
from test_gpt3_verified_customer_quote import fixture as quote_fixture
from test_gpt3_client_procurement import fixtures as procurement_fixture


def _inputs():
    sealed, customer, rates = quote_fixture()
    quote = build_verified_customer_quote(sealed, customer, rates)
    _, _, _, book = procurement_fixture()
    book["quote_fingerprint"] = quote["quote_fingerprint"]
    return quote, sealed, customer, book, rates


def test_exact_original_client_rates_create_unsent_po_with_replay_receipt():
    quote, sealed, customer, book, rates = _inputs()
    original = procurement.build_procurement_plan(quote, sealed, customer, book)
    audited = procurement.build_procurement_plan(
        quote, sealed, customer, book, client_rate_book=rates,
    )
    assert len(audited["purchase_order_drafts"]) == 1
    assert audited["order_transmitted"] is False
    assert audited["material_requirement_authenticated_from_drawings"] is False
    assert audited["official_four_project_accuracy"] is None
    assert "client_rate_source_replay_status" not in original
    assert audited["client_rate_source_replay_status"] == (
        "EXACT_V1_CUSTOMER_RATE_REPLAY_NOT_SOURCE_PDF_AUTHORITY"
    )
    assert audited["original_source_pdf_reverified"] is False


def test_new_client_rate_without_a_reissued_quote_cannot_authorize_po():
    quote, sealed, customer, book, rates = _inputs()
    old = deepcopy(rates)
    old["rates"][0]["material"] = "999.00"
    with pytest.raises(ValueError, match="does not reproduce"):
        procurement.build_procurement_plan(
            quote, sealed, customer, book, client_rate_book=old,
        )


def test_rehashed_quote_material_budget_cannot_bypass_original_rate_replay():
    quote, sealed, customer, book, rates = _inputs()
    forged = deepcopy(quote)
    forged["items"][0]["cost_components"]["material"] = "9999.00"
    altered = dict(forged)
    altered.pop("quote_fingerprint")
    forged["quote_fingerprint"] = hashlib.sha256(json.dumps(
        altered, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    book["quote_fingerprint"] = forged["quote_fingerprint"]
    with pytest.raises(ValueError, match="does not reproduce"):
        procurement.build_procurement_plan(
            forged, sealed, customer, book, client_rate_book=rates,
        )


def test_scope_preview_requires_rate_book_even_before_procurement_source_run():
    quote, sealed, customer, book, rates = _inputs()
    with pytest.raises(ValueError, match="requires original client rate"):
        procurement.build_procurement_plan(
            quote, sealed, customer, book, scope_preview={"issuer": "untrusted"},
        )


def test_real_signed_original_source_quantities_never_convert_to_purchase_units():
    quote, sealed, customer, book, rates = _inputs()
    original = deepcopy(quote)
    plan = procurement.build_procurement_plan(
        quote, sealed, customer, book, client_rate_book=rates,
    )
    assert quote == original
    assert plan["requisitions"][0]["authority"] == (
        "CLIENT_PLANNED_MATERIAL_DEMAND_NOT_SOURCE_MEASUREMENT"
    )
    assert plan["purchase_order_drafts"][0]["lines"][0][
        "purchase_order_measurement_authority"
    ] == "CLIENT_PLANNED_PURCHASE_NOT_SIGNED_AREA"


def test_procurement_cli_replays_rate_book_and_never_replaces_existing_source(tmp_path):
    quote, sealed, customer, book, rates = _inputs()
    payloads = {
        "quote": quote, "sealed-run": sealed, "customers": customer,
        "procurement-book": book, "client-rates": rates,
    }
    paths = {}
    for key, value in payloads.items():
        path = tmp_path / (key + ".json")
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[key] = path
    output = tmp_path / "order-draft.json"
    args = []
    for key, path in paths.items():
        args.extend(("--" + key, str(path)))
    args.extend(("--output", str(output)))
    assert procurement.main(args) == 0
    report = json.loads(output.read_text())
    assert report["client_rate_source_replay_status"].startswith("EXACT_V1")
    assert report["order_transmitted"] is False
    with pytest.raises(FileExistsError):
        procurement.main(args)

def test_expired_client_quote_cannot_trigger_new_supplier_award():
    quote, sealed, customer, book, rates = _inputs()
    book["as_of"] = "2026-12-01"
    with pytest.raises(ValueError, match="quote expired"):
        procurement.build_procurement_plan(
            quote, sealed, customer, book, client_rate_book=rates,
        )


def test_future_issued_quote_cannot_authorize_past_procurement_approval():
    quote, sealed, customer, book, rates = _inputs()
    book["as_of"] = "2026-10-16"
    with pytest.raises(ValueError, match="not yet issued"):
        procurement.build_procurement_plan(
            quote, sealed, customer, book, client_rate_book=rates,
        )


def test_client_quote_with_no_expiry_can_be_source_rate_replayed():
    quote, sealed, customer, book, rates = _inputs()
    new_rates = deepcopy(rates)
    new_rates["expires_on"] = None
    new_quote = build_verified_customer_quote(sealed, customer, new_rates)
    book["quote_fingerprint"] = new_quote["quote_fingerprint"]
    plan = procurement.build_procurement_plan(
        new_quote, sealed, customer, book, client_rate_book=new_rates,
    )
    assert plan["client_rate_source_replay_status"].startswith("EXACT_V1")
    assert plan["purchase_order_drafts"][0]["status"] == "DRAFT_NOT_TRANSMITTED"
