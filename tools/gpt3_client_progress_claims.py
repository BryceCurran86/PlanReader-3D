"""Cumulative, non-certifying client progress/payment claims against signed V1 quotes.

Customer-entered percentages and receipts are claims, not proof of installation,
certification, a new signed physical quantity, or a frozen V2 benchmark score.
All amounts are already tax-inclusive contract/variation gross; no second GST.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import csv
import io
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_verified_contract_delivery import (
    CENT, HUNDRED, _date, _identifier, digest, verified_quote, verify_contract,
)
from tools.gpt3_customer_change_orders import verify_variations
from tools.gpt3_verified_customer_quote import (
    _csv_text, _decimal, _money, _number, _write_new,
)
from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys


def _percentage_map(raw: Any, expected: set[str], label: str) -> dict[str, Decimal]:
    if type(raw) is not dict or set(raw) != expected:
        raise ValueError(f"{label} must explicitly cover every source-owned key")
    return {
        key: _decimal(raw[key], f"{label}/{key}", cap=HUNDRED)
        for key in sorted(raw)
    }


def _receipts(raw: Any, claim_date: Any, previous_ids: set[str]) -> list[dict]:
    if type(raw) is not list:
        raise ValueError("cash receipt entries must be an explicit list")
    result = []
    seen = set(previous_ids)
    for entry in raw:
        if type(entry) is not dict:
            raise ValueError("cash receipt entry must be an object")
        ref = _identifier(entry.get("receipt_id"), "payment receipt ID")
        if ref in seen:
            raise ValueError("payment receipt cannot be duplicated or reused")
        seen.add(ref)
        received = _date(entry.get("received_on"), "cash received date")
        if received > claim_date:
            raise ValueError("future payment receipt cannot be claimed as received")
        amount = _decimal(entry.get("amount"), "cash receipt amount")
        if amount <= 0:
            raise ValueError("cash receipt must represent positive actual funds")
        result.append({
            "receipt_id": ref, "received_on": received.isoformat(),
            "amount": _money(amount),
            "reference": _identifier(entry.get("reference"), "remittance reference"),
            "authority": "CLIENT_RECORDED_PAYMENT_NOT_BANK_VERIFIED",
        })
    return result


def _validate_claim_chain(previous: list[dict], contract: Mapping[str, Any],
                          variations: Mapping[str, Any]) -> None:
    prior = None
    for index, item in enumerate(previous, 1):
        if (type(item) is not dict
            or item.get("schema_version") != "gpt3-client-progress-claim-v1"
            or item.get("claim_fingerprint") != digest(item, "claim_fingerprint")
            or item.get("claim_number") != index
            or item.get("contract_fingerprint") != contract["contract_fingerprint"]
            or item.get("variation_register_fingerprint")
                != variations["variation_register_fingerprint"]
            or item.get("previous_claim_fingerprint")
                != (prior["claim_fingerprint"] if prior else None)):
            raise ValueError("previous claims do not form a sequential unmodified chain")
        if prior is not None and _date(item["claim_date"], "claim date") < _date(
            prior["claim_date"], "previous claim date"
        ):
            raise ValueError("historical progress claim dates are not monotonic")
        prior = item


def _earnings(contracts: list[dict], progress: dict[str, Decimal],
              key: str, price: str) -> tuple[Decimal, list[dict]]:
    total = Decimal("0")
    rows = []
    for item in contracts:
        ident = item[key]
        value = Decimal(item[price])
        percent = progress[ident]
        earned = (value * percent / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
        total += earned
        rows.append({
            key: ident, "contracted_gross": _money(value),
            "client_reported_completion_pct": _number(percent),
            "client_claimed_earned_to_date": _money(earned),
            "client_reported_remaining_gross": _money(value - earned),
        })
    return total, rows


def _aging(claims: list[dict], cash: Decimal, as_of: Any) -> dict:
    """Allocate recorded receipts FIFO across net claims without inventing cash."""
    buckets = {"CURRENT": Decimal("0"), "OVERDUE_1_30": Decimal("0"),
               "OVERDUE_31_60": Decimal("0"), "OVERDUE_61_PLUS": Decimal("0")}
    remaining_cash = cash
    aging = []
    for claim in claims:
        balance = Decimal(claim["summary"]["amount_due_from_this_claim"])
        allocated = min(balance, remaining_cash)
        remaining_cash -= allocated
        unpaid = balance - allocated
        due = _date(claim["due_on"], "claim due date")
        delay = max(0, (_date(as_of, "as-of date") - due).days)
        band = ("CURRENT" if delay == 0 else "OVERDUE_1_30" if delay <= 30
                else "OVERDUE_31_60" if delay <= 60 else "OVERDUE_61_PLUS")
        buckets[band] += unpaid
        aging.append({
            "claim_number": claim["claim_number"],
            "due_on": claim["due_on"],
            "remaining_unpaid": _money(unpaid),
            "days_overdue": delay if unpaid else 0,
            "aging_band": band if unpaid else "SETTLED",
        })
    return {
        "outstanding_by_age": {key: _money(value) for key, value in buckets.items()},
        "per_claim": aging, "unallocated_cash": _money(remaining_cash),
    }


def build_progress_claim(
    contract: dict, quote: dict, variation_register: dict,
    sealed_run: dict, customer_rows: list[dict],
    previous_claims: list[dict], new_claim: dict,
) -> dict:
    """Cumulative completion declarations, payment liability and cash receipts."""
    _, signed_lines = verified_quote(quote, sealed_run, customer_rows)
    verify_contract(contract, quote)
    verify_variations(variation_register, contract)
    if contract["acceptance"]["status"] != "ACCEPTED":
        raise ValueError("cannot progress-bill a quote without recorded client acceptance")
    if type(previous_claims) is not list or type(new_claim) is not dict:
        raise ValueError("client claim inputs must be explicit objects")
    _validate_claim_chain(previous_claims, contract, variation_register)
    expected_number = len(previous_claims) + 1
    if new_claim.get("schema_version") != "gpt3-client-progress-input-v1":
        raise ValueError("claim form needs explicit schema version")
    if new_claim.get("contract_id") != contract["contract_id"]:
        raise ValueError("claim is not for the accepted contract")
    if type(new_claim.get("claim_number")) is not int or new_claim["claim_number"] != expected_number:
        raise ValueError("claim numbering must be strictly sequential")
    claim_date = _date(new_claim.get("claim_date"), "client claim date")
    if previous_claims and claim_date < _date(previous_claims[-1]["claim_date"], "previous date"):
        raise ValueError("claim date cannot precede previous claim")
    name = _identifier(new_claim.get("claim_reference"), "claim reference")
    retention = _decimal(contract["retention_pct"], "retention percentage", cap=HUNDRED)
    milestones = contract["milestones"]
    accepted_changes = [
        row for row in variation_register["variations"]
        if row["status"] == "APPROVED"
    ]
    source = _percentage_map(
        new_claim.get("source_line_progress_pct"),
        {row["quantity_id"] for row in signed_lines}, "source client progress",
    )
    milestone = _percentage_map(
        new_claim.get("milestone_completion_pct"),
        {row["id"] for row in milestones}, "contract milestone progress",
    )
    change = _percentage_map(
        new_claim.get("variation_completion_pct"),
        {row["variation_id"] for row in accepted_changes},
        "approved variation progress",
    )
    prior_source = previous_claims[-1]["source_line_progress_pct"] if previous_claims else {}
    prior_milestone = previous_claims[-1]["milestone_completion_pct"] if previous_claims else {}
    prior_variation = previous_claims[-1]["variation_completion_pct"] if previous_claims else {}
    for current, past in ((source, prior_source), (milestone, prior_milestone), (change, prior_variation)):
        if any(value < Decimal(str(past.get(key, "0"))) for key, value in current.items()):
            raise ValueError("cumulative reported completion cannot be rolled backwards")
    milestone_earned, milestone_rows = _earnings(
        milestones, milestone, "id", "scheduled_value")
    variation_earned, change_rows = _earnings(
        accepted_changes, change, "variation_id", "gross_delta")
    # Price totals are already gross/tax-inclusive. This is a staged schedule,
    # not a new assessment of physical installed quantities.
    gross_to_date = milestone_earned + variation_earned
    prior_gross = (
        Decimal(previous_claims[-1]["summary"]["gross_earned_to_date"])
        if previous_claims else Decimal("0")
    )
    gross_delta = gross_to_date - prior_gross
    if gross_delta < 0:
        raise ValueError("progress earnings cannot decrease")
    withheld_total = (gross_to_date * retention / HUNDRED).quantize(
        CENT, rounding=ROUND_HALF_UP)
    past_withheld = (
        Decimal(previous_claims[-1]["summary"]["retention_withheld_to_date"])
        if previous_claims else Decimal("0")
    )
    release_already = (
        Decimal(previous_claims[-1]["summary"]["retention_released_to_date"])
        if previous_claims else Decimal("0")
    )
    all_complete = (
        all(value == HUNDRED for value in milestone.values())
        and all(value == HUNDRED for value in change.values())
    )
    release = new_claim.get("release_retention")
    if type(release) is not bool:
        raise ValueError("retention release requires explicit client instruction")
    if release and not all_complete:
        raise ValueError("retention cannot be released before all approved scheduled work")
    released_to_date = withheld_total if release else release_already
    if release_already and not release and all_complete:
        released_to_date = release_already
    if released_to_date < release_already:
        raise ValueError("retention releases cannot be reversed")
    retention_delta = withheld_total - past_withheld
    release_delta = released_to_date - release_already
    deposit = _decimal(new_claim.get("deposit_credit_applied"), "new deposit credit")
    past_deposit = (
        Decimal(previous_claims[-1]["summary"]["deposit_credit_applied_to_date"])
        if previous_claims else Decimal("0")
    )
    current_due = gross_delta - retention_delta + release_delta - deposit
    if current_due < 0:
        raise ValueError("client deposit credit cannot exceed positive payable value")
    prior_invoiced = (
        Decimal(previous_claims[-1]["summary"]["net_invoiced_to_date"])
        if previous_claims else Decimal("0")
    )
    net_to_date = prior_invoiced + current_due
    old_receipts = [
        row for prior in previous_claims for row in prior["new_receipts"]
    ]
    receipt_ids = {row["receipt_id"] for row in old_receipts}
    if len(receipt_ids) != len(old_receipts):
        raise ValueError("historical payment receipts have duplicated identities")
    added_receipts = _receipts(new_claim.get("new_receipts"), claim_date, receipt_ids)
    all_receipts = old_receipts + added_receipts
    received = sum((Decimal(row["amount"]) for row in all_receipts), Decimal("0"))
    if received > net_to_date:
        raise ValueError("customer receipt total exceeds verified claim liability")
    due_date = claim_date + timedelta(days=contract["payment_terms_days"])
    if type(new_claim.get("release_retention_reference")) not in (str, type(None)):
        raise ValueError("invalid release reference")
    if release and not _identifier(new_claim.get("release_retention_reference"),
                                   "retention release authority reference"):
        raise ValueError("retention release reference required")
    equivalences = []
    for row in signed_lines:
        qid = row["quantity_id"]
        value = Decimal(row["physical_quantity"])
        equivalences.append({
            "quantity_id": qid, "unit": row["unit"],
            "original_signed_physical_quantity": row["physical_quantity"],
            "client_reported_pct": _number(source[qid]),
            "client_reported_equivalent_quantity": _number(
                value * source[qid] / HUNDRED),
            "authority": "CLIENT_REPORTED_PROGRESS_NOT_SOURCE_REMEASUREMENT",
        })
    answer = {
        "schema_version": "gpt3-client-progress-claim-v1",
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "quote_fingerprint": contract["quote_fingerprint"],
        "signed_run_fingerprint": contract["signed_run_fingerprint"],
        "variation_register_fingerprint":
            variation_register["variation_register_fingerprint"],
        "previous_claim_fingerprint": (
            previous_claims[-1]["claim_fingerprint"] if previous_claims else None
        ),
        "currency": contract["currency"],
        "claim_number": expected_number,
        "claim_reference": name, "claim_date": claim_date.isoformat(),
        "due_on": due_date.isoformat(),
        "source_line_progress_pct": {k: _number(v) for k, v in source.items()},
        "milestone_completion_pct": {k: _number(v) for k, v in milestone.items()},
        "variation_completion_pct": {k: _number(v) for k, v in change.items()},
        "source_line_progress_equivalents": equivalences,
        "milestone_earned_breakdown": milestone_rows,
        "approved_variation_earned_breakdown": change_rows,
        "new_receipts": added_receipts,
        "release_retention": release,
        "release_retention_reference": new_claim.get("release_retention_reference"),
        "summary": {
            "gross_earned_to_date": _money(gross_to_date),
            "gross_earned_in_period": _money(gross_delta),
            "retention_withheld_to_date": _money(withheld_total),
            "retention_withheld_in_period": _money(retention_delta),
            "retention_released_to_date": _money(released_to_date),
            "retention_released_in_period": _money(release_delta),
            "deposit_credit_applied_in_period": _money(deposit),
            "deposit_credit_applied_to_date": _money(past_deposit + deposit),
            "amount_due_from_this_claim": _money(current_due),
            "net_invoiced_to_date": _money(net_to_date),
            "recorded_cash_received_to_date": _money(received),
            "outstanding_receivable": _money(net_to_date - received),
            "unearned_approved_contract_value": _money(
                Decimal(variation_register["committed_client_contract_gross"]) - gross_to_date),
        },
        "claimed_status": "CLIENT_RECORDED_UNCERTIFIED_PROGRESS",
        "completion_certified": False,
        "original_pdf_remeasured": False,
        "official_four_project_accuracy": None,
    }
    if Decimal(answer["summary"]["unearned_approved_contract_value"]) < 0:
        raise ValueError("claims exceed approved scope and milestones")
    # Use the full previous ledger for FIFO cash-aging, never future receipts.
    answer["aging"] = _aging([*previous_claims, answer], received, claim_date.isoformat())
    answer["claim_fingerprint"] = digest(answer, "claim_fingerprint")
    return answer


def progress_csv(report: Mapping[str, Any]) -> str:
    """Invoice/claim ledger with totals and clear uncertified source distinctions."""
    columns = ("row_type", "reference", "source_quantity_id",
               "unit", "reported_pct", "reported_quantity",
               "gross_amount", "currency", "claim_fingerprint", "authority")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    base = {"currency": report["currency"], "claim_fingerprint": report["claim_fingerprint"]}
    def emit(row):
        writer.writerow({
            key: _csv_text(row.get(key)) if key in (
                "row_type", "reference", "source_quantity_id", "unit",
                "currency", "claim_fingerprint", "authority"
            ) else row.get(key) for key in columns
        })
    for item in report["source_line_progress_equivalents"]:
        emit({**base, "row_type": "CLIENT_REPORTED_SOURCE_PROGRESS",
              "source_quantity_id": item["quantity_id"], "unit": item["unit"],
              "reported_pct": item["client_reported_pct"],
              "reported_quantity": item["client_reported_equivalent_quantity"],
              "authority": item["authority"]})
    for item in report["milestone_earned_breakdown"]:
        emit({**base, "row_type": "CLIENT_REPORTED_MILESTONE",
              "reference": item["id"], "reported_pct": item["client_reported_completion_pct"],
              "gross_amount": item["client_claimed_earned_to_date"],
              "authority": "CLIENT_RECORDED_UNCERTIFIED"})
    for item in report["approved_variation_earned_breakdown"]:
        emit({**base, "row_type": "CLIENT_REPORTED_APPROVED_VARIATION",
              "reference": item["variation_id"],
              "reported_pct": item["client_reported_completion_pct"],
              "gross_amount": item["client_claimed_earned_to_date"],
              "authority": "CLIENT_MANUAL_VARIATION_UNCERTIFIED"})
    for label, key in (
        ("GROSS_EARNED_IN_PERIOD", "gross_earned_in_period"),
        ("RETENTION_WITHHELD_IN_PERIOD", "retention_withheld_in_period"),
        ("RETENTION_RELEASED_IN_PERIOD", "retention_released_in_period"),
        ("DEPOSIT_CREDIT_IN_PERIOD", "deposit_credit_applied_in_period"),
        ("AMOUNT_DUE_THIS_CLAIM", "amount_due_from_this_claim"),
        ("CASH_RECORDED_TO_DATE", "recorded_cash_received_to_date"),
        ("OUTSTANDING_RECEIVABLE", "outstanding_receivable"),
    ):
        emit({**base, "row_type": "PAYMENT_SUMMARY", "reference": label,
              "gross_amount": report["summary"][key],
              "authority": "CLIENT_FINANCIAL_RECORD_NOT_BANK_CERTIFIED"})
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    paths = ("contract", "quote", "variations", "sealed_run",
             "customers", "previous_claims", "current_claim")
    for path in paths:
        p.add_argument("--" + path.replace("_", "-"), type=Path, required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--format", choices=("json", "csv"), default="json")
    options = p.parse_args(argv)
    files = tuple(getattr(options, name) for name in paths)
    values = [_read_json_without_duplicate_keys(path) for path in files]
    result = build_progress_claim(*values)
    text = (progress_csv(result) if options.format == "csv" else
            json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    _write_new(options.output, text, files)
    print(json.dumps({
        "claim_number": result["claim_number"],
        "claim_fingerprint": result["claim_fingerprint"],
        "amount_due_from_this_claim": result["summary"]["amount_due_from_this_claim"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
