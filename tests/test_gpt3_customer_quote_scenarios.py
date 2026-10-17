"""Price scenarios are actual client rate alternatives, never benchmark scores."""
from copy import deepcopy

import pytest

from tools import gpt3_customer_quote_scenarios as scenarios
import json
from pathlib import Path

def fixture():
    root = Path(__file__).resolve().parents[1]
    folder = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    sealed = json.loads((folder / "source_sealed_run.json").read_text(encoding="utf-8"))
    rows = json.loads((folder / "verified_customer_rows.json").read_text(encoding="utf-8"))
    rates = {
        "schema_version": "gpt3-client-rates-v1", "project_id": sealed["project_id"],
        "currency": "AUD", "issued_on": "2026-10-17", "expires_on": "2026-11-17",
        "include_manual_allowances": False, "manual_allowances": [],
        "rates": [{
            "scope": "family", "key": "opening_area", "unit": "m2",
            "material": "40", "labour": "20", "plant": "10", "subcontract": "5",
            "markup_pct": "15", "waste_pct": "2", "labour_hours_per_unit": "1.25",
        }],
        "adjustments": {
            "overhead_pct": "5", "contingency_pct": "2",
            "discount_pct": "0", "tax_pct": "10",
        },
    }
    return sealed, rows, rates


def bundle(rate_book):
    budget = deepcopy(rate_book)
    premium = deepcopy(rate_book)
    premium["rates"][0]["material"] = "200.00"
    return {
        "schema_version": "gpt3-client-scenarios-v1",
        "baseline": "Budget",
        "scenarios": [
            {"name": "Premium", "client_rates": premium},
            {"name": "Budget", "client_rates": budget},
        ],
        "budgets": {"Budget": "100000", "Premium": "100000"},
    }


def test_genuine_archived_eight_are_repriced_as_two_alternatives():
    signed, rows, rates = fixture()
    result = scenarios.build_scenario_comparison(signed, rows, bundle(rates))
    assert result["publication_status"] == "SCENARIOS_PRICED"
    assert result["official_four_project_accuracy"] is None
    assert len(result["comparison"]) == 2
    budget, premium = result["comparison"]
    assert budget["scenario"] == "Budget" and premium["scenario"] == "Premium"
    assert budget["total_vs_baseline"] == "0.00"
    assert float(premium["total_vs_baseline"]) > 0
    assert len(premium["rate_only_changed_items"]) == 8
    assert all(row["budget_remaining"] is not None for row in result["comparison"])
    assert "scenario" in scenarios.scenario_csv(result)


def test_unpriced_alternative_does_not_become_zero_or_budget_win():
    signed, rows, rates = fixture()
    inputs = bundle(rates)
    inputs["scenarios"][0]["client_rates"]["rates"] = []
    result = scenarios.build_scenario_comparison(signed, rows, inputs)
    assert result["publication_status"] == "SCENARIOS_INCOMPLETE"
    premium = result["comparison"][1]
    assert premium["total"] is None
    assert premium["budget_remaining"] is None
    assert result["supplier_rate_requests"][0]["family"] == "opening_area"
    assert len(result["supplier_rate_requests"][0]["unpriced_quantity_ids"]) == 8


def test_scenario_cannot_switch_to_a_different_project_or_currency():
    signed, rows, rates = fixture()
    inputs = bundle(rates)
    inputs["scenarios"][0]["client_rates"]["currency"] = "USD"
    with pytest.raises(ValueError, match="one currency"):
        scenarios.build_scenario_comparison(signed, rows, inputs)
    inputs = bundle(rates)
    inputs["scenarios"][0]["client_rates"]["project_id"] = "au_qld_maryborough_service_station"
    with pytest.raises(ValueError, match="does not match"):
        scenarios.build_scenario_comparison(signed, rows, inputs)


def test_budget_must_be_exact_decimal_and_names_owned():
    signed, rows, rates = fixture()
    inputs = bundle(rates)
    inputs["budgets"] = {"Ghost": "100"}
    with pytest.raises(ValueError, match="baseline/budget"):
        scenarios.build_scenario_comparison(signed, rows, inputs)
    inputs["budgets"] = {"Budget": "NaN"}
    with pytest.raises(ValueError, match="finite"):
        scenarios.build_scenario_comparison(signed, rows, inputs)


def test_supplier_rate_request_is_source_family_linked_and_not_a_zero_bid():
    signed, rows, rates = fixture()
    inputs = bundle(rates)
    inputs["scenarios"][0]["client_rates"]["rates"] = []
    report = scenarios.build_scenario_comparison(signed, rows, inputs)
    csv_text = scenarios.supplier_rfq_csv(report)
    assert "CLIENT_SUPPLIER_RATE_REQUIRED_NOT_ZERO" in csv_text
    assert "opening_area" in csv_text
    assert "m2" in csv_text
    assert report["comparison"][1]["total"] is None
