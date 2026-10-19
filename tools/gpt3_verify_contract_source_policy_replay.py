"""Replay client contract schedule from original signed V1 and exact policy.

The claimed contract digest is checked, then every schedule field is rebuilt
from the immutable signed source, verified customer rows, priced quote and
client-supplied contract acceptance/policy. This is NOT original PDF proof,
independent confirmation of a client's signature, progress certification, or
a Full Plan V2 benchmark score.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_safe_original_report_output import preflight_new_diagnostic, write_new_diagnostic
from tools.gpt3_replay_client_quote_from_signed_source import verify_client_quote_source_replay
from tools.gpt3_verified_contract_delivery import build_contract_schedule, verify_contract
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object, _json_customer_rows


def verify_contract_source_policy_replay(
    *, sealed_run: Mapping[str, Any], customers: list[dict],
    quote: Mapping[str, Any], policy: Mapping[str, Any],
    candidate_contract: Mapping[str, Any],
    client_rates: Mapping[str, Any] | None = None,
) -> dict:
    """Independent signed V1/quote/policy replay without trusting a new hash."""
    if type(candidate_contract) is not dict:
        raise ValueError("contract candidate must be a strict JSON object")
    if client_rates is not None:
        verify_client_quote_source_replay(sealed_run, customers, client_rates, quote)
    rebuilt = build_contract_schedule(quote, sealed_run, customers, policy)
    verify_contract(candidate_contract, quote)
    if candidate_contract != rebuilt:
        raise ValueError(
            "client contract differs from exact V1 customer quote and client policy replay"
        )
    return {
        "schema_version": "gpt3_contract_source_policy_replay.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "original_pdf_reverified": False,
        "client_signature_independently_authenticated": False,
        "certified_progress": False,
        "official_v2_accuracy": None,
        "project_id": rebuilt["project_id"],
        "signed_run_fingerprint": rebuilt["signed_run_fingerprint"],
        "quote_fingerprint": rebuilt["quote_fingerprint"],
        "contract_fingerprint": rebuilt["contract_fingerprint"],
        "source_item_count": rebuilt["source_item_count"],
        "client_rate_replay_status": (
            "EXACT_CLIENT_RATE_BOOK_REPLAY" if client_rates is not None
            else "CLIENT_RATE_BOOK_NOT_PROVIDED"
        ),
        "result": "EXACT_SIGNED_V1_QUOTE_CLIENT_POLICY_REPLAY",
    }


def build_contract_replay_report(
    *, sealed_path: Path, customer_path: Path, quote_path: Path,
    policy_path: Path, contract_path: Path,
    client_rates_path: Path | None = None,
) -> dict:
    paths = (sealed_path, customer_path, quote_path, policy_path, contract_path)
    if client_rates_path is not None:
        paths += (client_rates_path,)
    before = tuple(sha256(p.read_bytes()).hexdigest() for p in paths)
    report = verify_contract_source_policy_replay(
        sealed_run=_json_object(sealed_path),
        customers=_json_customer_rows(customer_path, allow_manual=True),
        quote=_json_object(quote_path),
        policy=_json_object(policy_path),
        candidate_contract=_json_object(contract_path),
        client_rates=(
            _json_object(client_rates_path)
            if client_rates_path is not None else None
        ),
    )
    if before != tuple(sha256(p.read_bytes()).hexdigest() for p in paths):
        raise ValueError("original source/customer/contract policy changed during audit")
    report["input_sha256s"] = {
        "sealed_v1": before[0], "customers": before[1],
        "client_quote": before[2], "client_policy": before[3],
        "client_contract": before[4],
    }
    if client_rates_path is not None:
        report["input_sha256s"]["client_rates"] = before[5]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("sealed_run", "customers", "client_quote", "client_policy", "client_contract"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--client-rates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (
        FROZEN_ROOT, args.sealed_run, args.customers, args.client_quote,
        args.client_policy, args.client_contract, args.client_rates,
    )
    preflight_new_diagnostic(args.output, protected_roots=protected)
    result = build_contract_replay_report(
        sealed_path=args.sealed_run, customer_path=args.customers,
        quote_path=args.client_quote, policy_path=args.client_policy,
        contract_path=args.client_contract, client_rates_path=args.client_rates,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
