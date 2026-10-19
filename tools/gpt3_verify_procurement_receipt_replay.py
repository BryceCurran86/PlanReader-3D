"""Exact supplier receipt ledger replay against signed V1 and client events.

All payments, supplier invoices, client-recorded deliveries and orders remain
CLIENT DECLARATIONS, not externally authenticated fulfillment or bank activity.
A self-consistent fulfillment fingerprint is insufficient to prove the ledger
was derived from the original procurement plan and source-linked quote.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_client_procurement_awards import build_procurement_plan
from tools.gpt3_client_procurement_receipts import build_procurement_receipts
from tools.gpt3_safe_original_report_output import preflight_new_diagnostic, write_new_diagnostic
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object, _json_customer_rows


def verify_procurement_receipt_source_replay(
    *, sealed_run: Mapping[str, Any], customers: list[dict],
    client_quote: Mapping[str, Any], procurement_book: Mapping[str, Any],
    procurement_plan: Mapping[str, Any], client_events: Mapping[str, Any],
    candidate_receipts: Mapping[str, Any],
    client_rates: Mapping[str, Any] | None = None,
) -> dict:
    """Independently rerun both original quote procurement and event ledger."""
    if type(candidate_receipts) is not dict:
        raise ValueError("original supplier receipt report must be an object")
    recreated_plan = build_procurement_plan(
        dict(client_quote), dict(sealed_run), customers, dict(procurement_book),
        client_rate_book=(dict(client_rates) if client_rates is not None else None),
    )
    if recreated_plan != procurement_plan:
        raise ValueError(
            "procurement plan differs from exact original signed-source client book"
        )
    expected = build_procurement_receipts(
        recreated_plan, dict(client_events),
    )
    if expected != candidate_receipts:
        raise ValueError(
            "supplier receipt report differs from exact source-linked client event replay"
        )
    return {
        "schema_version": "gpt3_procurement_receipt_source_replay.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "original_pdf_reverified": False,
        "supplier_delivery_independently_verified": False,
        "bank_payments_independently_verified": False,
        "external_order_sent_by_this_audit": False,
        "official_v2_accuracy": None,
        "project_id": expected["project_id"],
        "signed_run_fingerprint": expected["signed_run_fingerprint"],
        "client_quote_fingerprint": expected["quote_fingerprint"],
        "procurement_fingerprint": expected["procurement_fingerprint"],
        "fulfillment_fingerprint": expected["fulfillment_fingerprint"],
        "client_event_count": len(client_events["events"]),
        "original_client_rate_replay": (
            "REPLAYED" if client_rates is not None else "NOT_PROVIDED"
        ),
        "result": "EXACT_SIGNED_V1_CLIENT_PROCUREMENT_EVENT_REPLAY",
    }


def build_procurement_receipt_replay_report(
    *, sealed_path: Path, customer_path: Path, quote_path: Path,
    procurement_book_path: Path, procurement_plan_path: Path,
    client_events_path: Path, candidate_receipts_path: Path,
    client_rates_path: Path | None = None,
) -> dict:
    paths = (
        sealed_path, customer_path, quote_path, procurement_book_path,
        procurement_plan_path, client_events_path, candidate_receipts_path,
    )
    if client_rates_path is not None:
        paths += (client_rates_path,)
    before = tuple(sha256(p.read_bytes()).hexdigest() for p in paths)
    report = verify_procurement_receipt_source_replay(
        sealed_run=_json_object(sealed_path),
        customers=_json_customer_rows(customer_path, allow_manual=True),
        client_quote=_json_object(quote_path),
        procurement_book=_json_object(procurement_book_path),
        procurement_plan=_json_object(procurement_plan_path),
        client_events=_json_object(client_events_path),
        candidate_receipts=_json_object(candidate_receipts_path),
        client_rates=(
            _json_object(client_rates_path) if client_rates_path is not None
            else None
        ),
    )
    if before != tuple(sha256(p.read_bytes()).hexdigest() for p in paths):
        raise ValueError("supplier ledger source bytes changed during original replay")
    report["input_sha256s"] = {
        name: original_hash for name, original_hash in zip(
            ("sealed_v1", "customers", "quote", "procurement_book",
             "procurement_plan", "client_events", "candidate_receipts",
             "client_rates"),
            before,
        )
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("sealed_run", "customers", "quote", "procurement_book",
                 "procurement_plan", "client_events", "candidate_receipts"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--client-rates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = (
        args.sealed_run, args.customers, args.quote, args.procurement_book,
        args.procurement_plan, args.client_events, args.candidate_receipts,
    )
    preflight_new_diagnostic(
        args.output, protected_roots=(FROZEN_ROOT, *evidence, args.client_rates),
    )
    report = build_procurement_receipt_replay_report(
        sealed_path=args.sealed_run, customer_path=args.customers,
        quote_path=args.quote, procurement_book_path=args.procurement_book,
        procurement_plan_path=args.procurement_plan,
        client_events_path=args.client_events,
        candidate_receipts_path=args.candidate_receipts,
        client_rates_path=args.client_rates,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=(FROZEN_ROOT, *evidence, args.client_rates),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
