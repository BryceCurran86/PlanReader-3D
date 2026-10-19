"""Cost scenarios may be priced only from real signed quantities and explicit budgets."""
from __future__ import annotations

from copy import deepcopy

import pytest

from pb_source_closed_run_export import seal_source_closed_run
from tools.gpt3_customer_quote_scenarios import build_scenario_comparison
from test_gpt3_customer_quote_scenarios import fixture, bundle


def test_archived_eight_signed_client_scenarios_report_exact_budgets():
    sealed, customer, rates = fixture()
    inputs = bundle(rates)
    result = build_scenario_comparison(sealed, customer, inputs)
    assert result["publication_status"] == "SCENARIOS_PRICED"
    assert result["client_budget_approval_granted"] is False
    assert result["over_budget_scenarios"] == []
    assert result["official_four_project_accuracy"] is None
    for row in result["comparison"]:
        assert row["client_budget_status"] == "WITHIN_CLIENT_BUDGET"
        assert row["client_budget_shortfall"] == "0.00"


def test_overbudget_scenario_discloses_shortfall_without_fabricating_approval():
    sealed, customer, rates = fixture()
    inputs = bundle(rates)
    inputs["budgets"] = {"Premium": "1", "Budget": "100000"}
    result = build_scenario_comparison(sealed, customer, inputs)
    assert result["over_budget_scenarios"] == ["Premium"]
    premium = next(x for x in result["comparison"] if x["scenario"] == "Premium")
    assert premium["client_budget_status"] == "EXCEEDS_CLIENT_BUDGET"
    assert float(premium["client_budget_shortfall"]) > 0
    assert result["client_budget_approval_granted"] is False


def test_unpriced_scenario_is_indeterminate_not_within_client_budget():
    sealed, customer, rates = fixture()
    inputs = bundle(rates)
    inputs["scenarios"][0]["client_rates"]["rates"] = []
    report = build_scenario_comparison(sealed, customer, inputs)
    pending = next(x for x in report["comparison"] if x["scenario"] == "Premium")
    assert pending["client_budget_status"] == "UNPRICED_CANNOT_ASSESS_BUDGET"
    assert pending["client_budget_shortfall"] is None
    assert pending["total"] is None
    assert report["client_budget_approval_granted"] is False


def test_no_budget_is_explicit_not_an_infinite_budget():
    sealed, customer, rates = fixture()
    inputs = bundle(rates)
    inputs["budgets"] = {}
    result = build_scenario_comparison(sealed, customer, inputs)
    assert result["over_budget_scenarios"] == []
    assert all(x["client_budget_status"] == "NOT_SUPPLIED" for x in result["comparison"])
    assert all(x["client_budget_shortfall"] is None for x in result["comparison"])


def test_two_valid_but_empty_source_seals_do_not_make_complete_zero_cost_scenarios():
    sealed, customer, rates = fixture()
    empty = seal_source_closed_run(
        [], project_id=sealed["project_id"], traces_by_quantity_id={},
    )
    with pytest.raises(ValueError, match="empty signed source universe"):
        build_scenario_comparison(empty.to_dict(), [], bundle(rates))
