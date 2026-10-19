"""Contract rehashing never substitutes for an original client policy replay."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from test_gpt3_contract_variations_progress import inputs
from tools.gpt3_verify_contract_source_policy_replay import (
    verify_contract_source_policy_replay, build_contract_replay_report, main,
)
from tools.gpt3_verified_contract_delivery import digest


def fixtures(tmp_path):
    sealed, customers, rates, quote, policy, contract = inputs()
    data = {"sealed": sealed, "customers": customers, "rates": rates,
            "quote": quote, "policy": policy, "contract": contract}
    paths = {}
    for name, row in data.items():
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(row, sort_keys=True), encoding="utf-8")
        paths[name] = path
    return data, paths


def _run(data, *, with_rates=True):
    return verify_contract_source_policy_replay(
        sealed_run=data["sealed"], customers=data["customers"],
        quote=data["quote"], policy=data["policy"],
        candidate_contract=data["contract"],
        client_rates=data["rates"] if with_rates else None,
    )


def test_exact_signed_eight_source_replays_accepted_client_contract_and_rate():
    data = dict(zip(
        ("sealed", "customers", "rates", "quote", "policy", "contract"), inputs(),
    ))
    result = _run(data)
    assert result["result"] == "EXACT_SIGNED_V1_QUOTE_CLIENT_POLICY_REPLAY"
    assert result["source_item_count"] == 8
    assert result["client_rate_replay_status"] == "EXACT_CLIENT_RATE_BOOK_REPLAY"
    assert result["official_v2_accuracy"] is None
    assert result["client_signature_independently_authenticated"] is False
    assert result["certified_progress"] is False


def test_forged_and_rehashed_milestone_cannot_reuse_original_client_policy():
    data = dict(zip(
        ("sealed", "customers", "rates", "quote", "policy", "contract"), inputs(),
    ))
    fake = deepcopy(data["contract"])
    fake["milestones"][0]["scheduled_value"] = "999.00"
    fake["contract_fingerprint"] = digest(fake, "contract_fingerprint")
    data["contract"] = fake
    with pytest.raises(ValueError, match="differs from exact"):
        _run(data)


def test_rehashed_client_acceptance_without_matching_policy_fails():
    data = dict(zip(
        ("sealed", "customers", "rates", "quote", "policy", "contract"), inputs(),
    ))
    fake = deepcopy(data["contract"])
    fake["acceptance"]["reference"] = "forged-approval"
    fake["contract_fingerprint"] = digest(fake, "contract_fingerprint")
    data["contract"] = fake
    with pytest.raises(ValueError, match="differs from exact"):
        _run(data)


def test_changed_rate_book_cannot_reuse_old_accepted_contract_quote():
    data = dict(zip(
        ("sealed", "customers", "rates", "quote", "policy", "contract"), inputs(),
    ))
    data["rates"]["rates"][0]["material"] = "999.00"
    with pytest.raises(ValueError, match="does not reproduce"):
        _run(data)


def test_no_explicit_rates_does_not_claim_quote_rate_issuer_proof():
    data = dict(zip(
        ("sealed", "customers", "rates", "quote", "policy", "contract"), inputs(),
    ))
    r = _run(data, with_rates=False)
    assert r["client_rate_replay_status"] == "CLIENT_RATE_BOOK_NOT_PROVIDED"
    assert r["source_authenticated"] is False


def test_contract_audit_cli_create_only_and_immutable_signed_inputs(tmp_path):
    data, paths = fixtures(tmp_path)
    before = {k: hashlib.sha256(p.read_bytes()).hexdigest()
              for k, p in paths.items()}
    argv = [
        "--sealed-run", str(paths["sealed"]),
        "--customers", str(paths["customers"]),
        "--client-quote", str(paths["quote"]),
        "--client-policy", str(paths["policy"]),
        "--client-contract", str(paths["contract"]),
        "--client-rates", str(paths["rates"]),
        "--output", str(tmp_path / "audit.json"),
    ]
    assert main(argv) == 0
    audit = json.loads((tmp_path / "audit.json").read_text())
    assert audit["source_item_count"] == 8
    assert audit["publication_status"] == "UNPUBLISHED"
    assert before == {k: hashlib.sha256(p.read_bytes()).hexdigest()
                      for k, p in paths.items()}
    with pytest.raises(FileExistsError):
        main(argv)
    argv[-1] = str(paths["sealed"])
    with pytest.raises(ValueError, match="protected evidence"):
        main(argv)


def test_corrupt_customer_receipt_never_replays_contract(tmp_path):
    data, paths = fixtures(tmp_path)
    data["customers"][0]["ai_baseline_quantity"] = 999
    with pytest.raises(Exception):
        _run(data)
