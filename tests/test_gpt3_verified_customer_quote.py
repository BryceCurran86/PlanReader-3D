"""Pricing is source-closed V1 only: rates never create measured quantities."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools import gpt3_verified_customer_quote as quote


ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015/production"


def fixture():
    sealed = json.loads((ARCHIVED / "source_sealed_run.json").read_text(encoding="utf-8"))
    customers = json.loads((ARCHIVED / "verified_customer_rows.json").read_text(encoding="utf-8"))
    rates = {
        "schema_version": "gpt3-client-rates-v1",
        "project_id": sealed["project_id"],
        "currency": "AUD",
        "issued_on": "2026-10-17",
        "expires_on": "2026-11-17",
        "include_manual_allowances": False,
        "manual_allowances": [{"id": "m1", "description": "Manual option", "amount": "100"}],
        "rates": [{
            "scope": "family", "key": "opening_area", "unit": "m2",
            "material": "40.00", "labour": "20.00", "plant": "10.00",
            "subcontract": "5.00", "markup_pct": "15",
            "waste_pct": "2", "labour_hours_per_unit": "1.25",
        }],
        "adjustments": {
            "overhead_pct": "5", "contingency_pct": "2",
            "discount_pct": "0", "tax_pct": "10",
        },
    }
    return sealed, customers, rates


def test_archived_eight_signed_original_quantities_can_be_customer_priced():
    sealed, customers, rates = fixture()
    priced = quote.build_verified_customer_quote(sealed, customers, rates)
    assert priced["publication_status"] == "CLIENT_PRICED_QUOTE"
    assert priced["signed_quantity_count"] == 8
    assert priced["unpriced_quantity_count"] == 0
    assert len(priced["items"]) == 8
    assert all(row["pricing_status"] == "PRICED_FROM_CLIENT_RATE" for row in priced["items"])
    assert priced["official_four_project_accuracy"] is None
    assert priced["quote_fingerprint"] == quote.build_verified_customer_quote(
        sealed, list(reversed(customers)), rates)["quote_fingerprint"]


def test_no_client_rate_does_not_claim_total_or_free_physical_work():
    sealed, customers, rates = fixture()
    rates["rates"] = []
    priced = quote.build_verified_customer_quote(sealed, customers, rates)
    assert priced["unpriced_quantity_count"] == 8
    assert priced["summary"]["grand_total"] is None
    assert priced["publication_status"] == "INCOMPLETE_UNPRICED_QUANTITIES"


def test_original_measurements_cannot_be_changed_by_rate_override():
    sealed, customers, rates = fixture()
    original = quote.build_verified_customer_quote(sealed, customers, rates)
    qid = original["items"][0]["quantity_id"]
    rates["rates"].append({
        "scope": "quantity", "key": qid, "unit": "m2",
        "material": "999", "labour": "0", "plant": "0", "subcontract": "0",
    })
    repriced = quote.build_verified_customer_quote(sealed, customers, rates)
    assert repriced["items"][0]["physical_quantity"] == original["items"][0]["physical_quantity"]
    assert repriced["items"][0]["quantity_fingerprint"] == original["items"][0]["quantity_fingerprint"]
    assert repriced["items"][0]["sell_amount"] != original["items"][0]["sell_amount"]
    diff = quote.compare_verified_quotes(original, repriced)
    assert diff["issuer_comparison"] == "SAME_SIGNED_ISSUER"
    assert len(diff["item_changes"]) == 1
    assert diff["item_changes"][0]["change"] == "CLIENT_RATE_OR_PRICING_CHANGED"


def test_manual_allowance_is_always_explicitly_separate_from_source_measurement():
    sealed, customers, rates = fixture()
    initial = quote.build_verified_customer_quote(sealed, customers, rates)
    rates["include_manual_allowances"] = True
    included = quote.build_verified_customer_quote(sealed, customers, rates)
    assert included["signed_quantity_count"] == initial["signed_quantity_count"]
    assert included["summary"]["manual_allowance_included_amount"] == "100.00"
    assert included["summary"]["grand_total"] != initial["summary"]["grand_total"]
    assert included["manual_allowances"][0]["authority"] == "CLIENT_MANUAL_NOT_SOURCE_VERIFIED"


@pytest.mark.parametrize("bad", ["NaN", "-1", "Infinity", "1e10000", 0.1, None, True])
def test_client_money_requires_exact_safe_decimal(bad):
    sealed, customers, rates = fixture()
    rates["rates"][0]["material"] = bad
    with pytest.raises(ValueError):
        quote.build_verified_customer_quote(sealed, customers, rates)


def test_wrong_signed_project_rate_book_is_not_reused():
    sealed, customers, rates = fixture()
    rates["project_id"] = "au_qld_3laurel"
    with pytest.raises(ValueError, match="does not match"):
        quote.build_verified_customer_quote(sealed, customers, rates)


def test_exported_csv_contains_exact_quantity_ids_and_no_source_pdf():
    sealed, customers, rates = fixture()
    priced = quote.build_verified_customer_quote(sealed, customers, rates)
    csv_text = quote.quote_csv(priced)
    assert "quantity_id" in csv_text
    assert priced["items"][0]["quantity_id"] in csv_text
    assert "source_sha256" in csv_text
    assert "%PDF" not in csv_text


def test_overwriting_signed_evidence_is_forbidden(tmp_path):
    source = tmp_path / "sealed.json"
    source.write_text('{"immutable": true}', encoding="utf-8")
    with pytest.raises(FileExistsError):
        quote._write_new(source, '{"quote":true}', (source,))
    assert source.read_text(encoding="utf-8") == '{"immutable": true}'


def test_tampered_archived_customer_quantity_fails_instead_of_being_priced():
    sealed, customers, rates = fixture()
    customers[0]["ai_baseline_quantity"] = 999
    with pytest.raises(Exception):
        quote.build_verified_customer_quote(sealed, customers, rates)
