"""Independently verify signed customer rows for an unpublished V2 report."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from scripts.report_full_plan_v2_readiness import (
    _customer_output_bijection_proof, _first_failing_authority_stage,
)
from test_customer_output_verification import sealed_and_rows


def _fixtures(tmp_path):
    sealed, customer_rows = sealed_and_rows()
    project_id = sealed.project_id
    sealed_root = tmp_path / "sealed"
    customer_root = tmp_path / "customer"
    signed_file = sealed_root / project_id / "sealed_run.json"
    customer_file = customer_root / project_id / "customer_rows.json"
    signed_file.parent.mkdir(parents=True)
    customer_file.parent.mkdir(parents=True)
    signed_file.write_text(sealed.to_json(), encoding="utf-8")
    customer_file.write_text(json.dumps(customer_rows), encoding="utf-8")
    return sealed, customer_rows, sealed_root, customer_root, signed_file, customer_file


def _proof(tmp_path):
    sealed, rows, sealed_root, customer_root, signed_file, customer_file = _fixtures(tmp_path)
    args = (sealed_root, customer_root, sealed.project_id, True)
    return sealed, rows, args, signed_file, customer_file


def test_original_signed_customer_bijection_is_separately_proven(tmp_path):
    sealed, rows, args, signed_file, customer_file = _proof(tmp_path)
    before = (signed_file.read_bytes(), customer_file.read_bytes())
    assert _customer_output_bijection_proof(
        *args, expected_seal_fingerprint=sealed.fingerprint,
    ) == (True, [])
    assert (signed_file.read_bytes(), customer_file.read_bytes()) == before


def test_no_customer_files_never_count_as_verified_customer_publication(tmp_path):
    sealed, rows, args, signed_file, customer_file = _proof(tmp_path)
    assert _customer_output_bijection_proof(
        args[0], None, args[2], True,
        expected_seal_fingerprint=sealed.fingerprint,
    ) == (False, ["customer_rows_not_supplied"])
    customer_file.unlink()
    assert _customer_output_bijection_proof(
        *args, expected_seal_fingerprint=sealed.fingerprint,
    ) == (False, ["customer_rows_missing"])


@pytest.mark.parametrize("fault", ["missing", "duplicated", "forged", "wrong-source"])
def test_invalid_or_missing_customer_row_cannot_claim_bijection(tmp_path, fault):
    sealed, rows, args, signed_file, customer_file = _proof(tmp_path)
    corrupted = deepcopy(rows)
    if fault == "missing":
        corrupted.pop()
    elif fault == "duplicated":
        corrupted.append(deepcopy(corrupted[0]))
    elif fault == "forged":
        corrupted[0]["quantity_id"] = "unsealed-forged-quantity"
    else:
        corrupted[0]["revision_id"] = "wrong-original-revision"
    customer_file.write_text(json.dumps(corrupted), encoding="utf-8")
    assert _customer_output_bijection_proof(
        *args, expected_seal_fingerprint=sealed.fingerprint,
    ) == (False, ["customer_bijection_integrity_invalid"])


@pytest.mark.parametrize("invalid", [
    '{"quantity_id":"forged"}',
    '[{"quantity_id":"x", "quantity_id":"y"}]',
    "[null]",
])
def test_customer_shape_and_duplicate_key_are_not_proven(tmp_path, invalid):
    sealed, rows, args, signed_file, customer_file = _proof(tmp_path)
    customer_file.write_text(invalid, encoding="utf-8")
    verified, reasons = _customer_output_bijection_proof(
        *args, expected_seal_fingerprint=sealed.fingerprint,
    )
    assert verified is False
    assert reasons in (
        ["customer_rows_invalid_shape"],
        ["customer_bijection_integrity_invalid"],
    )


def test_customer_proof_cannot_inherit_different_signed_run_fingerprint(tmp_path):
    sealed, rows, args, signed_file, customer_file = _proof(tmp_path)
    assert _customer_output_bijection_proof(
        *args, expected_seal_fingerprint="f" * 64,
    ) == (False, ["customer_sealed_run_changed"])


def test_claimed_parity_without_seal_ownership_remains_unverified(tmp_path):
    sealed, rows, args, signed_file, customer_file = _proof(tmp_path)
    assert _customer_output_bijection_proof(
        *args, expected_seal_fingerprint=None,
    ) == (False, ["customer_sealed_run_not_verified"])
    assert _customer_output_bijection_proof(
        args[0], args[1], args[2], False,
        expected_seal_fingerprint=sealed.fingerprint,
    ) == (False, ["customer_sealed_run_not_verified"])


def test_first_failure_exposes_customer_gap_separately_from_sealed_quantities():
    stage, reason = _first_failing_authority_stage(
        source_verified=True, source_reasons=[],
        manifest_status="VERIFIED", manifest_reasons=[],
        sealed_verified=True, seal_reasons=[],
        produced_present=True, produced_valid=True, produced_count=2,
        produced_reasons=[], parity_verified=True, parity_reasons=[],
        customer_verified=False, customer_reasons=["customer_rows_not_supplied"],
    )
    assert (stage, reason) == ("CUSTOMER_OUTPUT_BIJECTION", "customer_rows_not_supplied")


def test_customer_file_rotated_during_verification_is_not_a_valid_receipt(tmp_path, monkeypatch):
    import scripts.report_full_plan_v2_readiness as readiness

    sealed, rows, args, signed_file, customer_file = _proof(tmp_path)
    from pb_customer_output_verification import verify_sealed_customer_output as real

    def check_then_rotate(*call_args):
        verified = real(*call_args)
        customer_file.write_text("[]", encoding="utf-8")
        return verified

    monkeypatch.setattr(
        __import__("pb_customer_output_verification"),
        "verify_sealed_customer_output", check_then_rotate,
    )
    assert readiness._customer_output_bijection_proof(
        *args, expected_seal_fingerprint=sealed.fingerprint,
    ) == (False, ["customer_rows_changed_during_readiness"])
