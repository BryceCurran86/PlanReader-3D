from __future__ import annotations

import hashlib
import inspect

import pytest

import tools.diag_gpt3_maryborough_ft3_source_firstgate as module


def test_source_sha_guard_is_exact_and_fail_closed(tmp_path, monkeypatch):
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"exact-source")
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    monkeypatch.setattr(module, "EXPECTED_SHA256", digest)
    payload, got = module._verify_source(pdf)
    assert payload == b"exact-source"
    assert got == digest
    pdf.write_bytes(b"changed-source")
    with pytest.raises(ValueError, match="original source SHA"):
        module._verify_source(pdf)


def test_status_preserves_enum_owned_value():
    class _Status:
        value = "corroborated"

    assert module._status(_Status()) == "corroborated"
    assert module._status("abstained") == "abstained"


def test_diagnostic_has_no_frozen_truth_or_scoring_inputs():
    source = inspect.getsource(module)
    forbidden = (
        "reference_takeoff",
        "object_universe",
        "expected_quantity",
        "denominator_eligible",
        "run_exact_project_reconciliation",
        "evaluate_project_v2",
        "matched_within_tolerance",
    )
    for token in forbidden:
        assert token not in source


def test_diagnostic_never_publishes_finish_or_benchmark_claims():
    source = inspect.getsource(module.inspect_ft3_firstgate)
    assert '"floor_finish_quantity_published": False' in source
    assert '"customer_quantity_published": False' in source
    assert '"benchmark_identity_assigned": False' in source
    assert '"benchmark_accuracy": None' in source
