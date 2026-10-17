"""Distinct projects cannot duplicate one issuer's signed customer evidence."""
import pytest
from tools import report_gpt3_selected_two_project_original_evidence as selected


def project(pid, sealed_id, fp, quantity):
    return {
        "project_id": pid, "sealed_run_id": sealed_id, "sealed_run_fingerprint": fp,
        "customer_quantity_ids": [quantity], "denominator": 1,
        "matched_within_tolerance": 0, "matched_outside_tolerance": 0,
        "missed": 1, "partial": 0, "unresolved": 0, "unsupported_extra": 0,
        "abstained_outputs": 0, "lineage_conflicts": 0,
    }


def compare(monkeypatch, first, second):
    rows = {"a": first, "b": second}
    monkeypatch.setattr(selected, "_checked_one", lambda row: rows[row])
    return selected.build_selected_two_project_development_evidence(["a", "b"])


@pytest.mark.parametrize("run_id,fp", [("same", "fp-two"), ("run-two", "same")])
def test_duplicate_independent_signed_run_fingerprint_or_issuer_rejected(monkeypatch, run_id, fp):
    a = project("a", "same", "same", "quantity-a")
    b = project("b", run_id, fp, "quantity-b")
    with pytest.raises(ValueError, match="independently sealed"):
        compare(monkeypatch, a, b)


def test_distinct_original_signed_run_ids_and_fingerprints_remain_diagnostic(monkeypatch):
    result = compare(monkeypatch, project("a", "run-a", "fingerprint-a", "qa"),
                     project("b", "run-b", "fingerprint-b", "qb"))
    assert result["selected_denominator"] == 2
    assert result["publication_status"] == "SELECTED_PROJECT_DEVELOPMENT_ONLY"
    assert result["official_four_project_accuracy"] is None
