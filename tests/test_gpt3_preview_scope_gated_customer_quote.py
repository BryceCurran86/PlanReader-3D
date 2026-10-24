"""Client pricing can opt in to scope parity, never issuer authentication."""
from __future__ import annotations

import copy
import json

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_scope_sidecar_v2_preview import SourceClosedRunConflictError
from tools import gpt3_verified_customer_quote as quote
from test_gpt3_scope_customer_receipt_parity import _fixtures
from test_gpt3_verified_customer_quote import fixture as archived_quote_fixture


def _rates(project_id="project-7"):
    return {
        "schema_version": "gpt3-client-rates-v1",
        "project_id": project_id,
        "currency": "AUD",
        "issued_on": "2026-10-19",
        "expires_on": "2026-11-19",
        "include_manual_allowances": False,
        "manual_allowances": [],
        "rates": [{
            "scope": "family", "key": "floor_area", "unit": "m²",
            "material": "10", "labour": "20", "plant": "5", "subcontract": "0",
            "markup_pct": "15", "waste_pct": "0",
        }],
        "adjustments": {
            "overhead_pct": "0", "contingency_pct": "0",
            "discount_pct": "0", "tax_pct": "10",
        },
    }


def test_scope_preview_opt_in_prices_same_v1_quantities_without_issuer_claim():
    sealed, scope, customers = _fixtures()
    rates = _rates()
    old = quote.build_verified_customer_quote(sealed.to_dict(), customers, rates)
    priced = quote.build_verified_customer_quote(
        sealed.to_dict(), customers, rates, scope_preview=scope,
    )
    assert old["signed_quantity_count"] == priced["signed_quantity_count"] == 2
    assert [x["quantity_fingerprint"] for x in old["items"]] == [
        x["quantity_fingerprint"] for x in priced["items"]]
    assert old["summary"]["grand_total"] == priced["summary"]["grand_total"]
    assert "scope_preview_customer_parity" not in old
    assert priced["scope_preview_customer_parity"] == "SELF_ATTESTED_MATCH_ONLY"
    assert priced["scope_preview_source_authenticated"] is False
    assert priced["scope_preview_sealed_run_fingerprint"] == sealed.fingerprint
    assert priced["official_four_project_accuracy"] is None
    assert old["quote_fingerprint"] != priced["quote_fingerprint"]


def test_scope_disagreement_blocks_client_pricing_even_when_old_v1_still_verifies():
    sealed, scope, customers = _fixtures()
    altered = copy.deepcopy(customers)
    altered[0]["commercial_projection_provenance"]["quantity"]["metadata"][
        "decision_scope_id"] = "scope-different"
    altered[0]["notes"] = json.dumps(altered[0]["commercial_projection_provenance"])
    assert verify_sealed_customer_output(sealed, altered).valid_quantity_count == 2
    with pytest.raises(SourceClosedRunConflictError, match="receipt conflicts"):
        quote.build_verified_customer_quote(
            sealed.to_dict(), altered, _rates(), scope_preview=scope,
        )


def test_scope_preview_from_other_v1_run_cannot_price_current_run():
    sealed, scope, customers = _fixtures()
    other = copy.deepcopy(scope)
    other["sealed_run_fingerprint"] = "0" * 64
    with pytest.raises(SourceClosedRunConflictError):
        quote.build_verified_customer_quote(
            sealed.to_dict(), customers, _rates(), scope_preview=other,
        )


def test_absent_preview_never_changes_valid_archived_customer_quotes():
    sealed, customers, rates = archived_quote_fixture()
    priced = quote.build_verified_customer_quote(sealed, customers, rates)
    assert priced["publication_status"] == "CLIENT_PRICED_QUOTE"
    assert priced["signed_quantity_count"] == 8
    assert "scope_preview_customer_parity" not in priced
    assert priced["official_four_project_accuracy"] is None


def test_scope_gated_quote_cli_writes_create_only_when_metadata_matches(tmp_path):
    sealed, scope, customers = _fixtures()
    paths = {
        "sealed": tmp_path / "sealed.json",
        "customers": tmp_path / "customers.json",
        "rates": tmp_path / "rates.json",
        "scope": tmp_path / "scope.json",
        "output": tmp_path / "quote.json",
    }
    for key, payload in (
        ("sealed", sealed.to_dict()),
        ("customers", customers),
        ("rates", _rates()),
        ("scope", scope),
    ):
        paths[key].write_text(json.dumps(payload), encoding="utf-8")
    argv = [
        "--sealed-run", str(paths["sealed"]),
        "--customers", str(paths["customers"]),
        "--client-rates", str(paths["rates"]),
        "--scope-preview", str(paths["scope"]),
        "--output", str(paths["output"]),
    ]
    assert quote.main(argv) == 0
    report = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert report["scope_preview_customer_parity"] == "SELF_ATTESTED_MATCH_ONLY"
    assert report["official_four_project_accuracy"] is None
    with pytest.raises(FileExistsError):
        quote.main(argv)
