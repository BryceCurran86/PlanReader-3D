"""Replay customer-priced quote from exact signed source and explicit client rates.

Content-equal report hashes are not source PDF issuer certificates; this audit
requires the untouched V1 seal, independently verified customer rows and the
EXACT client rate inputs to reproduce every quote byte deterministically.
No source quantity, client rate, existing quote, customer output or frozen
benchmark truth is modified.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.gpt3_verified_customer_quote import build_verified_customer_quote
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_object, _json_customer_rows,
)


def verify_client_quote_source_replay(
    sealed_v1: Mapping[str, Any], customers: list[dict],
    rate_book: Mapping[str, Any], candidate: Mapping[str, Any],
    *, scope_preview: Mapping[str, Any] | None = None,
) -> dict:
    """Reprice from independently audited V1 and rate cards, never from quote."""
    if type(candidate) is not dict:
        raise ValueError("replay quote must be a strict JSON object")
    source_repriced = build_verified_customer_quote(
        sealed_v1, customers, rate_book, scope_preview=scope_preview,
    )
    if dict(candidate) != source_repriced:
        raise ValueError(
            "client quote does not reproduce from exact V1 source/customer/rate inputs"
        )
    return {
        "schema_version": "gpt3_client_quote_exact_replay.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "original_pdf_reverified": False,
        "official_v2_accuracy": None,
        "customer_quote_replay_status": "EXACT_SIGNED_V1_CUSTOMER_RATE_REPLAY",
        "project_id": source_repriced["project_id"],
        "sealed_run_fingerprint": source_repriced["signed_run_fingerprint"],
        "quote_fingerprint": source_repriced["quote_fingerprint"],
        "signed_quantity_count": source_repriced["signed_quantity_count"],
        "unpriced_quantity_count": source_repriced["unpriced_quantity_count"],
        "quote_publication_status": source_repriced["publication_status"],
    }


def build_quote_replay_report(
    *, sealed_path: Path, customer_path: Path, rate_path: Path,
    quote_path: Path, scope_path: Path | None = None,
) -> dict:
    paths = (sealed_path, customer_path, rate_path, quote_path)
    if scope_path is not None:
        paths += (scope_path,)
    initial_sha = tuple(sha256(p.read_bytes()).hexdigest() for p in paths)
    signed = _json_object(sealed_path)
    customers = _json_customer_rows(customer_path, allow_manual=True)
    rates = _json_object(rate_path)
    candidate = _json_object(quote_path)
    scope = _json_object(scope_path) if scope_path is not None else None
    report = verify_client_quote_source_replay(
        signed, customers, rates, candidate, scope_preview=scope,
    )
    final_sha = tuple(sha256(p.read_bytes()).hexdigest() for p in paths)
    if initial_sha != final_sha:
        raise ValueError("signed/customer/rate/quote artifact changed during audit")
    report["input_artifact_sha256s"] = {
        "sealed_v1": initial_sha[0],
        "customers": initial_sha[1],
        "client_rates": initial_sha[2],
        "client_quote": initial_sha[3],
    }
    if scope_path is not None:
        report["input_artifact_sha256s"]["scope_preview"] = initial_sha[4]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--customers", type=Path, required=True)
    parser.add_argument("--client-rates", type=Path, required=True)
    parser.add_argument("--client-quote", type=Path, required=True)
    parser.add_argument("--scope-preview", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (
        FROZEN_ROOT, args.sealed_run, args.customers, args.client_rates,
        args.client_quote, args.scope_preview,
    )
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report = build_quote_replay_report(
        sealed_path=args.sealed_run, customer_path=args.customers,
        rate_path=args.client_rates, quote_path=args.client_quote,
        scope_path=args.scope_preview,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
