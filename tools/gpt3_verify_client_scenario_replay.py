"""Exact, create-only client rate scenario replay from existing signed V1 output.

A scenario's self-consistent JSON digest is not source or client pricing proof.
Independently rebuild each scenario from the original sealed quantities,
verified customer rows and each explicitly provided client rate book.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_customer_quote_scenarios import build_scenario_comparison
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_object, _json_customer_rows,
)


def verify_scenario_source_rate_replay(
    sealed_v1: Mapping[str, Any], customers: list[dict],
    scenario_book: Mapping[str, Any], candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if type(candidate) is not dict:
        raise ValueError("scenario candidate must be a strict JSON object")
    verified = build_scenario_comparison(sealed_v1, customers, scenario_book)
    if candidate != verified:
        raise ValueError(
            "client scenarios do not reproduce from signed V1/customer/rate inputs"
        )
    return {
        "schema_version": "gpt3_client_scenario_rate_replay.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "original_pdf_reverified": False,
        "official_v2_accuracy": None,
        "project_id": verified["project_id"],
        "source_run_fingerprint": verified["signed_run_fingerprint"],
        "scenario_comparison_fingerprint": verified["comparison_fingerprint"],
        "scenario_count": len(verified["comparison"]),
        "budget_approval_granted": False,
        "verified_status": "EXACT_CLIENT_SCENARIO_RATE_SOURCE_REPLAY",
    }


def build_scenario_replay_report(
    *, sealed_path: Path, customer_path: Path,
    book_path: Path, candidate_path: Path,
) -> dict:
    paths = (sealed_path, customer_path, book_path, candidate_path)
    before = tuple(sha256(p.read_bytes()).hexdigest() for p in paths)
    report = verify_scenario_source_rate_replay(
        _json_object(sealed_path),
        _json_customer_rows(customer_path, allow_manual=True),
        _json_object(book_path),
        _json_object(candidate_path),
    )
    after = tuple(sha256(p.read_bytes()).hexdigest() for p in paths)
    if after != before:
        raise ValueError("signed source/customer/rate scenario bytes changed")
    report["source_input_sha256s"] = {
        "signed_v1": before[0],
        "customers": before[1],
        "client_scenario_book": before[2],
        "candidate_report": before[3],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--customers", type=Path, required=True)
    parser.add_argument("--client-scenarios", type=Path, required=True)
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (
        FROZEN_ROOT, args.sealed_run, args.customers,
        args.client_scenarios, args.candidate_report,
    )
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report = build_scenario_replay_report(
        sealed_path=args.sealed_run, customer_path=args.customers,
        book_path=args.client_scenarios, candidate_path=args.candidate_report,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
