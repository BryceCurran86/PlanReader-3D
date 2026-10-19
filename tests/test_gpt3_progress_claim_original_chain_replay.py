"""No rehashed progress amount may become a signed or client-approved quantity."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from test_gpt3_contract_variations_progress import (
    inputs, variation_book, claim_input,
)
from tools.gpt3_client_progress_claims import build_progress_claim
from tools.gpt3_customer_change_orders import build_change_register
from tools.gpt3_verified_contract_delivery import digest
from tools.gpt3_verify_progress_claim_source_chain import (
    verify_progress_claim_source_chain, build_progress_claim_source_chain_report,
    main,
)


def _inputs():
    signed, rows, rates, quote, policy, contract = inputs()
    changes = variation_book(contract, approved=True)
    register = build_change_register(contract, quote, changes)
    claim = claim_input(
        contract, register, number=1,
        stage1="20", stage2="0", v_pct="10",
        source_pct="20", day="2026-10-22",
    )
    candidate = build_progress_claim(
        contract, quote, register, signed, rows, [], claim,
    )
    return {
        "sealed_run": signed, "customers": rows, "quote": quote,
        "client_contract_policy": policy, "client_contract": contract,
        "client_variation_book": changes,
        "client_variation_register": register,
        "previous_claims": [], "current_claim_input": claim,
        "candidate_claim": candidate, "client_rates": rates,
    }


def test_archived_signed_eight_replay_client_progress_chain_without_certification():
    payload = _inputs()
    result = verify_progress_claim_source_chain(**payload)
    assert result["result"] == "EXACT_SIGNED_V1_CLIENT_PROGRESS_CHAIN_REPLAY"
    assert result["claim_number"] == 1
    assert result["client_rates_replayed"] is True
    assert result["installed_work_independently_certified"] is False
    assert result["bank_receipts_verified"] is False
    assert result["official_v2_accuracy"] is None


def test_forged_and_rehashed_client_claim_amount_cannot_bypass_source_replay():
    payload = _inputs()
    forged = deepcopy(payload["candidate_claim"])
    forged["summary"]["gross_earned_to_date"] = "9999.00"
    forged["claim_fingerprint"] = digest(forged, "claim_fingerprint")
    payload["candidate_claim"] = forged
    with pytest.raises(ValueError, match="differs from exact"):
        verify_progress_claim_source_chain(**payload)


def test_rehashed_contract_acceptance_without_client_policy_fails_earlier_gate():
    payload = _inputs()
    forged = deepcopy(payload["client_contract"])
    forged["acceptance"]["reference"] = "fake-acceptance"
    forged["contract_fingerprint"] = digest(forged, "contract_fingerprint")
    payload["client_contract"] = forged
    with pytest.raises(ValueError, match="contract cannot be reconstructed"):
        verify_progress_claim_source_chain(**payload)


def test_reissued_variation_state_requires_exact_client_original_event_book():
    payload = _inputs()
    bad = deepcopy(payload["client_variation_register"])
    bad["variations"][0]["description"] = "injected added work"
    bad["variation_register_fingerprint"] = digest(bad, "variation_register_fingerprint")
    payload["client_variation_register"] = bad
    with pytest.raises(ValueError, match="variation register cannot"):
        verify_progress_claim_source_chain(**payload)


def test_changed_client_rate_book_never_reuses_old_signed_quote_for_progress():
    payload = _inputs()
    payload["client_rates"]["rates"][0]["labour"] = "900.00"
    with pytest.raises(ValueError, match="does not reproduce"):
        verify_progress_claim_source_chain(**payload)


def test_readonly_progress_cli_avoids_overwrite_and_records_exact_evidence_hashes(tmp_path):
    data = _inputs()
    paths = {}
    original = {}
    translation = {
        "sealed_run": "sealed", "customers": "customers",
        "quote": "quote", "client_contract_policy": "contract_policy",
        "client_contract": "contract", "client_variation_book": "variations_book",
        "client_variation_register": "variations",
        "previous_claims": "previous_claims",
        "current_claim_input": "new_claim",
        "candidate_claim": "candidate",
        "client_rates": "rates",
    }
    for key, value in data.items():
        path = tmp_path / (translation[key] + ".json")
        path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        paths[translation[key]] = path
        original[translation[key]] = hashlib.sha256(path.read_bytes()).hexdigest()
    argv = []
    for name, path in paths.items():
        argv.extend(["--" + name.replace("_", "-"), str(path)])
    output = tmp_path / "progress-audit.json"
    argv.extend(["--output", str(output)])
    assert main(argv) == 0
    report = json.loads(output.read_text())
    assert report["publication_status"] == "UNPUBLISHED"
    assert original == {
        key: hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in paths.items()
    }
    with pytest.raises(FileExistsError):
        main(argv)

def test_prior_self_hashed_claim_without_original_event_epochs_cannot_be_authenticated():
    payload = _inputs()
    payload["previous_claims"] = [deepcopy(payload["candidate_claim"])]
    with pytest.raises(ValueError, match="first-claim-only authority gate"):
        verify_progress_claim_source_chain(**payload)
