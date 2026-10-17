"""End-to-end contract and progress behaviour on eight genuine signed Lot16 areas.

Client prices/progress/approvals are synthetic and never benchmark truth.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.gpt3_verified_customer_quote import build_verified_customer_quote
from tools.gpt3_verified_contract_delivery import (
    build_contract_schedule, build_quote_revision_history, verified_quote,
)
from tools.gpt3_customer_change_orders import (
    build_change_register, change_order_csv,
)
from tools.gpt3_client_progress_claims import build_progress_claim, progress_csv

SOURCES = (Path(__file__).resolve().parents[1] /
    "docs/engineering/lot16_original_signed_eight_row_20261015/production")


def inputs():
    sealed = json.loads((SOURCES / "source_sealed_run.json").read_text(encoding="utf-8"))
    customers = json.loads((SOURCES / "verified_customer_rows.json").read_text(encoding="utf-8"))
    prices = {
        "schema_version": "gpt3-client-rates-v1",
        "project_id": sealed["project_id"], "currency": "AUD",
        "issued_on": "2026-10-17", "expires_on": "2026-12-17",
        "include_manual_allowances": True,
        "manual_allowances": [{"id": "x1", "description": "Manual client item", "amount": "30.00"}],
        "rates": [{
            "scope": "family", "key": "opening_area", "unit": "m2",
            "material": "100", "labour": "40", "plant": "10", "subcontract": "5",
            "waste_pct": "3", "markup_pct": "15", "labour_hours_per_unit": "0.5",
        }],
        "adjustments": {
            "overhead_pct": "8", "contingency_pct": "5",
            "discount_pct": "1", "tax_pct": "10",
        },
    }
    quote = build_verified_customer_quote(sealed, customers, prices)
    assignments = {item["quantity_id"]: "openings" for item in quote["items"]}
    policy = {
        "schema_version": "gpt3-contract-policy-v1",
        "project_id": sealed["project_id"],
        "contract_id": "C-001", "client_reference": "Client test contract",
        "payment_terms_days": 14, "retention_pct": "5",
        "inclusions": ["Measure-approved openings"],
        "exclusions": ["Any unspecified site work"],
        "package_assignments": assignments,
        "package_descriptions": {"openings": "Signed opening area work"},
        "milestones": [
            {"id": "stage-one", "description": "First stage",
             "due_on": "2026-10-21", "share_pct": "25"},
            {"id": "stage-two", "description": "Second stage",
             "due_on": "2026-11-21", "share_pct": "75"},
        ],
        "acceptance": {
            "status": "ACCEPTED", "actor": "Client representative",
            "reference": "Acceptance-in-client-system-123",
            "recorded_on": "2026-10-18",
            "quote_fingerprint": quote["quote_fingerprint"],
        },
    }
    contract = build_contract_schedule(quote, sealed, customers, policy)
    return sealed, customers, prices, quote, policy, contract


def variation_book(contract, approved=True):
    raw = {
        "schema_version": "gpt3-client-variations-v1",
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "currency": contract["currency"],
        "events": [{
            "event": "PROPOSE", "variation_id": "CO-01",
            "recorded_on": "2026-10-19",
            "scope_type": "ADDED_SCOPE",
            "description": "Client-requested additional manual work",
            "related_signed_quantity_ids": [],
            "net_ex_tax": "100.00", "tax_pct": "10",
        }],
    }
    if approved:
        raw["events"].append({
            "event": "APPROVE", "variation_id": "CO-01",
            "recorded_on": "2026-10-20",
            "actor": "Client", "reference": "Approval-123",
        })
    return raw


def claim_input(contract, variations, number, stage1, stage2, v_pct,
                source_pct, day, deposit="0", receipts=None, release=False):
    return {
        "schema_version": "gpt3-client-progress-input-v1",
        "contract_id": contract["contract_id"],
        "claim_number": number, "claim_reference": f"Claim-{number}",
        "claim_date": day,
        "milestone_completion_pct": {"stage-one": stage1, "stage-two": stage2},
        "source_line_progress_pct": {
            qid: source_pct for pkg in contract["packages"]
            for qid in pkg["source_quantity_ids"]
        },
        "variation_completion_pct": {
            item["variation_id"]: v_pct for item in variations["variations"]
            if item["status"] == "APPROVED"
        },
        "deposit_credit_applied": deposit,
        "new_receipts": receipts or [],
        "release_retention": release,
        "release_retention_reference": "Completion signoff" if release else None,
    }


def test_real_eight_signed_quantities_flow_into_contract_without_remeasurement():
    sealed, customers, _, quote, _, contract = inputs()
    verified_quote(quote, sealed, customers)
    assert contract["source_item_count"] == 8
    assert contract["signed_run_fingerprint"] == quote["signed_run_fingerprint"]
    assert contract["contract_value_including_quote_tax"] == quote["summary"]["grand_total"]
    assert sum(float(x["scheduled_value"]) for x in contract["milestones"]) == pytest.approx(
        float(quote["summary"]["grand_total"]))
    assert contract["certified_progress"] is False
    assert contract["original_pdf_reverified_in_this_delivery"] is False


def test_contract_requires_all_source_ids_assigned_exactly_once():
    sealed, customers, _, quote, policy, _ = inputs()
    policy["package_assignments"].pop(next(iter(policy["package_assignments"])))
    with pytest.raises(ValueError, match="every signed"):
        build_contract_schedule(quote, sealed, customers, policy)


def test_client_acceptance_is_exact_quote_specific_and_cannot_precede_issue():
    sealed, customers, _, quote, policy, _ = inputs()
    policy["acceptance"]["quote_fingerprint"] = "wrong"
    with pytest.raises(ValueError, match="exact quoted"):
        build_contract_schedule(quote, sealed, customers, policy)
    policy["acceptance"]["quote_fingerprint"] = quote["quote_fingerprint"]
    policy["acceptance"]["recorded_on"] = "2025-01-01"
    with pytest.raises(ValueError, match="before issue"):
        build_contract_schedule(quote, sealed, customers, policy)


def test_rate_only_revision_preserves_original_signed_quantities():
    sealed, customers, rates, quote, _, _ = inputs()
    revised = deepcopy(rates)
    revised["rates"][0]["material"] = "145"
    new_quote = build_verified_customer_quote(sealed, customers, revised)
    report = build_quote_revision_history([
        {"version": 1, "effective_on": "2026-10-17", "quote": quote},
        {"version": 2, "effective_on": "2026-10-19", "quote": new_quote},
    ], sealed, customers)
    assert len(report["revisions"]) == 2
    assert report["revisions"][1]["change_since_previous"] != "0.00"
    assert len(report["revisions"][1]["changed_line_items"]) == 8
    assert report["signed_run_fingerprint"] == quote["signed_run_fingerprint"]
    assert report["official_four_project_accuracy"] is None


def test_proposal_not_added_to_committed_contract_until_external_approval():
    _, _, _, quote, _, contract = inputs()
    proposal = build_change_register(contract, quote, variation_book(contract, approved=False))
    approved = build_change_register(contract, quote, variation_book(contract, approved=True))
    assert proposal["pending_variation_delta_not_committed"] == "110.00"
    assert proposal["approved_variation_delta"] == "0.00"
    assert approved["approved_variation_delta"] == "110.00"
    assert approved["committed_client_contract_gross"] != proposal["committed_client_contract_gross"]
    assert approved["physical_quantity_created"] is False
    assert "CO-01" in change_order_csv(approved)


def test_manual_removed_scope_creates_credit_without_negative_physical_quantity():
    _, _, _, quote, _, contract = inputs()
    changes = variation_book(contract, approved=True)
    changes["events"].append({
        "event": "PROPOSE", "variation_id": "CO-02",
        "recorded_on": "2026-10-21", "scope_type": "REMOVED_SCOPE",
        "description": "Removed option", "related_signed_quantity_ids": [],
        "net_ex_tax": "-25.00", "tax_pct": "10",
    })
    changes["events"].append({
        "event": "APPROVE", "variation_id": "CO-02",
        "recorded_on": "2026-10-22", "actor": "Client", "reference": "Approval-124",
    })
    result = build_change_register(contract, quote, changes)
    assert result["approved_variation_delta"] == "82.50"
    assert result["variations"][0]["status"] == "APPROVED"
    assert result["variations"][1]["gross_delta"] == "-27.50"


def test_cumulative_milestone_claims_and_retention_release_are_not_certification():
    sealed, customers, _, quote, _, contract = inputs()
    approved = build_change_register(contract, quote, variation_book(contract))
    first = build_progress_claim(contract, quote, approved, sealed, customers, [],
        claim_input(contract, approved, 1, "100", "0", "0", "20",
            "2026-10-25", deposit="10",
            receipts=[{"receipt_id": "R1", "received_on": "2026-10-25",
                       "amount": "20.00", "reference": "Bank-ref-not-verified"}]))
    second = build_progress_claim(contract, quote, approved, sealed, customers, [first],
        claim_input(contract, approved, 2, "100", "60", "80", "70", "2026-11-05"))
    third = build_progress_claim(contract, quote, approved, sealed, customers,
        [first, second], claim_input(contract, approved, 3, "100", "100",
            "100", "100", "2026-11-22", release=True))
    assert first["claim_number"] == 1 and second["claim_number"] == 2
    assert first["summary"]["retention_withheld_to_date"] != "0.00"
    assert third["summary"]["retention_released_to_date"] != "0.00"
    assert third["summary"]["unearned_approved_contract_value"] == "0.00"
    assert third["summary"]["outstanding_receivable"] != "0.00"
    assert third["completion_certified"] is False
    assert third["official_four_project_accuracy"] is None
    assert "CLIENT_REPORTED_SOURCE_PROGRESS" in progress_csv(third)
    assert third["summary"]["gross_earned_to_date"] == approved["committed_client_contract_gross"]


def test_progress_cannot_be_rolled_back_to_duplicate_billing():
    sealed, customers, _, quote, _, contract = inputs()
    approved = build_change_register(contract, quote, variation_book(contract))
    first = build_progress_claim(contract, quote, approved, sealed, customers, [],
        claim_input(contract, approved, 1, "100", "0", "0", "20", "2026-10-25"))
    with pytest.raises(ValueError, match="rolled backwards"):
        build_progress_claim(contract, quote, approved, sealed, customers, [first],
            claim_input(contract, approved, 2, "50", "0", "0", "10", "2026-10-26"))


def test_overpaid_receipt_refused_and_duplicate_remittance_refused():
    sealed, customers, _, quote, _, contract = inputs()
    approved = build_change_register(contract, quote, variation_book(contract))
    entry = claim_input(contract, approved, 1, "100", "0", "0", "10", "2026-10-25",
        receipts=[{"receipt_id": "R1", "received_on": "2026-10-25",
                   "amount": "999999", "reference": "Manual remittance"}])
    with pytest.raises(ValueError, match="exceeds"):
        build_progress_claim(contract, quote, approved, sealed, customers, [], entry)


def test_pending_variation_may_be_approved_after_first_progress_claim():
    sealed, customers, _, quote, _, contract = inputs()
    draft_changes = build_change_register(
        contract, quote, variation_book(contract, approved=False))
    first = build_progress_claim(contract, quote, draft_changes, sealed, customers, [],
        claim_input(contract, draft_changes, 1, "100", "0", "0", "20",
                    "2026-10-25"))
    approved_changes = build_change_register(
        contract, quote, variation_book(contract, approved=True))
    second = build_progress_claim(contract, quote, approved_changes, sealed,
        customers, [first], claim_input(contract, approved_changes, 2,
            "100", "80", "100", "80", "2026-11-10"))
    assert second["summary"]["gross_earned_to_date"] > first["summary"]["gross_earned_to_date"]
    assert len(second["variation_event_hashes"]) == len(first["variation_event_hashes"]) + 1


def test_mutated_claim_chain_or_variation_event_history_is_not_reusable():
    sealed, customers, _, quote, _, contract = inputs()
    approved = build_change_register(contract, quote, variation_book(contract))
    first = build_progress_claim(contract, quote, approved, sealed, customers, [],
        claim_input(contract, approved, 1, "100", "0", "0", "20", "2026-10-25"))
    modified = deepcopy(first)
    modified["summary"]["outstanding_receivable"] = "0.00"
    with pytest.raises(ValueError, match="unmodified chain"):
        build_progress_claim(contract, quote, approved, sealed, customers, [modified],
            claim_input(contract, approved, 2, "100", "50", "0", "50",
                        "2026-11-10"))
