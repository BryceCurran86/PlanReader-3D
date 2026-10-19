"""Reproduce client progress claims from unchanged V1, policy and variation events.

Client-reported percentages, signatures and cash receipts are NOT certified
installed construction, bank transactions or original PDF-source authority.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_client_progress_claims import build_progress_claim
from tools.gpt3_customer_change_orders import build_change_register
from tools.gpt3_verified_contract_delivery import build_contract_schedule
from tools.gpt3_replay_client_quote_from_signed_source import verify_client_quote_source_replay
from tools.gpt3_safe_original_report_output import preflight_new_diagnostic, write_new_diagnostic
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object, _json_customer_rows


def verify_progress_claim_source_chain(
    *, sealed_run: dict, customers: list[dict], quote: dict,
    client_contract_policy: dict, client_contract: dict,
    client_variation_book: dict, client_variation_register: dict,
    previous_claims: list[dict], current_claim_input: dict,
    candidate_claim: dict, client_rates: dict | None = None,
) -> dict:
    """Validate source → quote → contract → variations → progress deterministically."""
    if client_rates is not None:
        verify_client_quote_source_replay(
            sealed_run, customers, client_rates, quote,
        )
    canonical_contract = build_contract_schedule(
        quote, sealed_run, customers, client_contract_policy,
    )
    if canonical_contract != client_contract:
        raise ValueError(
            "client contract cannot be reconstructed from signed quote and policy"
        )
    canonical_variations = build_change_register(
        canonical_contract, quote, client_variation_book,
    )
    if canonical_variations != client_variation_register:
        raise ValueError(
            "variation register cannot be reconstructed from original client events"
        )
    expected = build_progress_claim(
        canonical_contract, quote, canonical_variations,
        sealed_run, customers, previous_claims, current_claim_input,
    )
    if expected != candidate_claim:
        raise ValueError(
            "client claim differs from exact signed V1 contract and variation source replay"
        )
    return {
        "schema_version": "gpt3_progress_claim_source_chain_replay.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "original_pdf_reverified": False,
        "installed_work_independently_certified": False,
        "bank_receipts_verified": False,
        "client_signatures_verified": False,
        "official_v2_accuracy": None,
        "contract_id": canonical_contract["contract_id"],
        "signed_run_fingerprint": canonical_contract["signed_run_fingerprint"],
        "quote_fingerprint": canonical_contract["quote_fingerprint"],
        "contract_fingerprint": canonical_contract["contract_fingerprint"],
        "variation_fingerprint": canonical_variations["variation_register_fingerprint"],
        "claim_fingerprint": expected["claim_fingerprint"],
        "claim_number": expected["claim_number"],
        "client_rates_replayed": client_rates is not None,
        "result": "EXACT_SIGNED_V1_CLIENT_PROGRESS_CHAIN_REPLAY",
    }


def build_progress_claim_source_chain_report(
    *, sealed_path: Path, customers_path: Path, quote_path: Path,
    contract_policy_path: Path, contract_path: Path,
    variations_book_path: Path, variations_path: Path,
    previous_claims_path: Path, new_claim_path: Path,
    candidate_path: Path, rates_path: Path | None = None,
) -> dict:
    paths = (
        sealed_path, customers_path, quote_path, contract_policy_path,
        contract_path, variations_book_path, variations_path,
        previous_claims_path, new_claim_path, candidate_path,
    )
    if rates_path is not None:
        paths += (rates_path,)
    before = tuple(sha256(p.read_bytes()).hexdigest() for p in paths)
    previous = _json_array(previous_claims_path)
    result = verify_progress_claim_source_chain(
        sealed_run=_json_object(sealed_path),
        customers=_json_customer_rows(customers_path, allow_manual=True),
        quote=_json_object(quote_path),
        client_contract_policy=_json_object(contract_policy_path),
        client_contract=_json_object(contract_path),
        client_variation_book=_json_object(variations_book_path),
        client_variation_register=_json_object(variations_path),
        previous_claims=previous,
        current_claim_input=_json_object(new_claim_path),
        candidate_claim=_json_object(candidate_path),
        client_rates=_json_object(rates_path) if rates_path is not None else None,
    )
    if before != tuple(sha256(p.read_bytes()).hexdigest() for p in paths):
        raise ValueError("signed client progress evidence changed during audit")
    result["input_artifact_sha256s"] = list(before)
    return result


def _json_array(path: Path) -> list[dict]:
    from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys
    raw = _read_json_without_duplicate_keys(path)
    if type(raw) is not list or any(type(row) is not dict for row in raw):
        raise ValueError("previous signed claims must be an array of objects")
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    names = (
        "sealed", "customers", "quote", "contract_policy", "contract",
        "variations_book", "variations", "previous_claims",
        "new_claim", "candidate",
    )
    for name in names:
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--rates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = tuple(getattr(args, name) for name in names)
    protected = (FROZEN_ROOT, *inputs, args.rates)
    preflight_new_diagnostic(args.output, protected_roots=protected)
    result = build_progress_claim_source_chain_report(
        sealed_path=args.sealed, customers_path=args.customers,
        quote_path=args.quote, contract_policy_path=args.contract_policy,
        contract_path=args.contract, variations_book_path=args.variations_book,
        variations_path=args.variations,
        previous_claims_path=args.previous_claims,
        new_claim_path=args.new_claim, candidate_path=args.candidate,
        rates_path=args.rates,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
