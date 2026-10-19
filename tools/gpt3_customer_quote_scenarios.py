"""Multi-scenario customer-rate pricing over the same immutable signed takeoff.

This is a real cost-planning consumer of GPT3 V1 commercial rows, never
a benchmark estimator or an original drawing parser.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_verified_customer_quote import (
    _csv_text, _decimal, _money, _write_new, build_verified_customer_quote,
)
from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys


def build_scenario_comparison(
    sealed_run: Mapping[str, Any], customer_rows: list[dict],
    scenario_book: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare independent rate books without altering signed measurements."""
    if type(scenario_book) is not dict or scenario_book.get("schema_version") != "gpt3-client-scenarios-v1":
        raise ValueError("scenario bundle has unsupported client schema")
    raw = scenario_book.get("scenarios")
    baseline = scenario_book.get("baseline")
    if type(raw) is not list or not 2 <= len(raw) <= 20:
        raise ValueError("scenario comparison requires 2-20 priced alternatives")
    if type(baseline) is not str or not baseline:
        raise ValueError("scenario comparison requires an exact baseline")
    budgets = scenario_book.get("budgets", {})
    if type(budgets) is not dict:
        raise ValueError("budget caps must be an optional name-to-exact-decimal mapping")
    names: set[str] = set()
    quotes: dict[str, dict] = {}
    for entry in raw:
        if type(entry) is not dict or set(entry) != {"name", "client_rates"}:
            raise ValueError("scenario entry must name exactly one client rate book")
        name, rates = entry["name"], entry["client_rates"]
        if (type(name) is not str or not name or name != name.strip()
            or name in names or type(rates) is not dict):
            raise ValueError("scenario names and rate books must be canonical and distinct")
        names.add(name)
        quotes[name] = build_verified_customer_quote(sealed_run, customer_rows, rates)
    if baseline not in quotes or any(key not in names for key in budgets):
        raise ValueError("baseline/budget names must match exactly one declared scenario")
    currencies = {quote["currency"] for quote in quotes.values()}
    issuers = {quote["signed_run_fingerprint"] for quote in quotes.values()}
    if len(currencies) != 1 or len(issuers) != 1:
        raise ValueError("rate scenarios must use one currency and one source-signed run")

    original = quotes[baseline]
    if (
        original["signed_quantity_count"] == 0
        or any(q["signed_quantity_count"] == 0 for q in quotes.values())
    ):
        raise ValueError(
            "scenario comparison cannot price an empty signed source universe"
        )
    reference_items = {
        row["quantity_id"]: row for row in original["items"]
    }
    comparisons = []
    impact: dict[tuple[str, str], Decimal] = {}
    outstanding: dict[tuple[str, str], set[str]] = {}
    for name in sorted(quotes):
        q = quotes[name]
        items = {row["quantity_id"]: row for row in q["items"]}
        if set(items) != set(reference_items):
            raise ValueError("scenario has changed physical quantity identities")
        changed_prices = []
        for qid in sorted(reference_items):
            start, end = reference_items[qid], items[qid]
            for key in ("physical_quantity", "unit", "quantity_fingerprint",
                        "source_sha256", "source_page", "revision_id"):
                if start[key] != end[key]:
                    raise ValueError("scenario has altered the original physical evidence")
            if end["pricing_status"] != "PRICED_FROM_CLIENT_RATE":
                outstanding.setdefault((end["family"], end["unit"]), set()).add(qid)
            if start["sell_amount"] is not None and end["sell_amount"] is not None:
                difference = Decimal(end["sell_amount"]) - Decimal(start["sell_amount"])
                if difference:
                    changed_prices.append({
                        "quantity_id": qid,
                        "family": end["family"],
                        "unit": end["unit"],
                        "old_price": start["sell_amount"],
                        "new_price": end["sell_amount"],
                        "rate_only_price_delta": _money(difference),
                    })
                    label = (end["family"], end["unit"])
                    impact[(name, *label)] = impact.get((name, *label), Decimal("0")) + difference
        before = original["summary"].get("grand_total")
        after = q["summary"].get("grand_total")
        cap = _decimal(budgets[name], f"scenario budget {name}") if name in budgets else None
        shortfall = (
            max(Decimal("0"), Decimal(after) - cap)
            if cap is not None and after is not None else None
        )
        budget_status = (
            "NOT_SUPPLIED" if cap is None else
            "UNPRICED_CANNOT_ASSESS_BUDGET" if after is None else
            "EXCEEDS_CLIENT_BUDGET" if shortfall > 0 else
            "WITHIN_CLIENT_BUDGET"
        )
        comparisons.append({
            "client_budget_status": budget_status,
            "client_budget_shortfall": _money(shortfall) if shortfall is not None else None,

            "scenario": name,
            "is_baseline": name == baseline,
            "publication_status": q["publication_status"],
            "quote_fingerprint": q["quote_fingerprint"],
            "signed_run_fingerprint": q["signed_run_fingerprint"],
            "priced_subtotal": q["summary"]["priced_automated_subtotal"],
            "unpriced_count": q["unpriced_quantity_count"],
            "total": after,
            "total_vs_baseline": (
                _money(Decimal(after) - Decimal(before))
                if after is not None and before is not None else None
            ),
            "labour_hours": q["summary"]["priced_labour_hours"],
            "budget_cap": _money(cap) if cap is not None else None,
            "budget_remaining": (
                _money(cap - Decimal(after))
                if cap is not None and after is not None else None
            ),
            "rate_only_changed_items": changed_prices,
        })
    request_lines = [{
        "family": family, "unit": unit,
        "unpriced_quantity_ids": sorted(ids),
        "request": "CLIENT_SUPPLIER_RATE_REQUIRED_NOT_ZERO",
    } for (family, unit), ids in sorted(outstanding.items())]
    payload = {
        "schema_version": "gpt3-client-scenario-comparison-v1",
        "project_id": original["project_id"],
        "currency": original["currency"],
        "baseline": baseline,
        "signed_run_fingerprint": original["signed_run_fingerprint"],
        "publication_status": (
            "SCENARIOS_PRICED" if all(row["total"] is not None for row in comparisons)
            else "SCENARIOS_INCOMPLETE"
        ),
        "comparison": comparisons,
        "family_unit_rate_impact": [
            {"scenario": name, "family": family, "unit": unit, "delta": _money(value)}
            for (name, family, unit), value in sorted(impact.items())
        ],
        "supplier_rate_requests": request_lines,
        "client_budget_approval_granted": False,
        "over_budget_scenarios": [
            row["scenario"] for row in comparisons
            if row["client_budget_status"] == "EXCEEDS_CLIENT_BUDGET"
        ],
        "official_four_project_accuracy": None,
    }
    payload["comparison_fingerprint"] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()
    return payload


def scenario_csv(report: Mapping[str, Any]) -> str:
    """Provide safe scenario summary rows for client cost-planning import."""
    columns = ("scenario", "is_baseline", "publication_status",
               "priced_subtotal", "unpriced_count", "total",
               "total_vs_baseline", "labour_hours", "budget_cap", "budget_remaining")
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    for row in report["comparison"]:
        writer.writerow({key: _csv_text(row.get(key)) if key == "scenario"
                         else row.get(key) for key in columns})
    return handle.getvalue()


def supplier_rfq_csv(report: Mapping[str, Any]) -> str:
    """Supplier price requests for missing signed families, never zero prices."""
    columns = ("project_id", "family", "unit",
               "source_quantity_ids", "requested_input", "currency")
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    for row in report["supplier_rate_requests"]:
        writer.writerow({
            "project_id": _csv_text(report["project_id"]),
            "family": _csv_text(row["family"]),
            "unit": _csv_text(row["unit"]),
            "source_quantity_ids": _csv_text(";".join(row["unpriced_quantity_ids"])),
            "requested_input": row["request"],
            "currency": report["currency"],
        })
    return handle.getvalue()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sealed-run", type=Path, required=True)
    p.add_argument("--customers", type=Path, required=True)
    p.add_argument("--scenario-books", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--format", choices=("json", "csv", "rfq-csv"), default="json")
    args = p.parse_args(argv)
    inputs = (args.sealed_run, args.customers, args.scenario_books)
    report = build_scenario_comparison(
        _read_json_without_duplicate_keys(args.sealed_run),
        _read_json_without_duplicate_keys(args.customers),
        _read_json_without_duplicate_keys(args.scenario_books),
    )
    body = (scenario_csv(report) if args.format == "csv" else
            supplier_rfq_csv(report) if args.format == "rfq-csv" else
            json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
    _write_new(args.output, body, inputs)
    print(json.dumps({
        "publication_status": report["publication_status"],
        "comparison_fingerprint": report["comparison_fingerprint"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0 if report["publication_status"] == "SCENARIOS_PRICED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
