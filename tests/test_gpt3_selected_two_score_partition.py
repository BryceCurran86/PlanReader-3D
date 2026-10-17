"""A selected source project cannot counterfeit its aggregate score counts."""
from copy import deepcopy
import pytest
from tools import report_gpt3_selected_two_project_original_evidence as selected


def row(pid, matched=2, missed=3, extras=1):
    denom = matched + missed
    return {
        "project_id": pid, "sealed_run_id": "run-" + pid,
        "sealed_run_fingerprint": "sha-" + pid,
        "customer_quantity_ids": ["quantity-" + pid],
        "denominator": denom, "matched_within_tolerance": matched,
        "matched_outside_tolerance": 0, "missed": missed, "partial": 0, "unresolved": 0,
        "unsupported_extra": extras, "abstained_outputs": 0, "lineage_conflicts": 0,
        "coverage_accuracy": matched / denom,
        "precision_adjusted_accuracy": matched / (denom + extras),
    }


def run(monkeypatch, changed=None):
    a, b = row("a"), row("b", matched=1, missed=4, extras=0)
    if changed:
        changed(a)
    mapping = {"a": a, "b": b}
    monkeypatch.setattr(selected, "_checked_one", lambda x: mapping[x])
    return selected.build_selected_two_project_development_evidence(["a", "b"])


def test_exact_partitioned_counts_aggregate_only_diagnostic(monkeypatch):
    output = run(monkeypatch)
    assert output["selected_denominator"] == 10
    assert output["publication_status"] == "SELECTED_PROJECT_DEVELOPMENT_ONLY"
    assert output["official_four_project_accuracy"] is None


@pytest.mark.parametrize("change,match", [
    (lambda a: a.update(missed=2), "partition"),
    (lambda a: a.update(matched_within_tolerance=True), "malformed"),
    (lambda a: a.update(unsupported_extra=-1), "malformed"),
    (lambda a: a.update(coverage_accuracy=0.9), "percentage"),
    (lambda a: a.update(precision_adjusted_accuracy=0.9), "percentage"),
    (lambda a: a.update(coverage_accuracy=float("nan")), "percentage"),
])
def test_selected_two_rejects_tampered_counter_or_precision_copy(monkeypatch, change, match):
    with pytest.raises(ValueError, match=match):
        run(monkeypatch, change)
