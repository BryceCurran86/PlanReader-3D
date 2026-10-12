"""Adversarial original-source stage delta; never proxy for V2 accuracy."""
from copy import deepcopy
import json
import sys

import pytest

from test_gpt3_maryborough_source_stage_ledger import _inputs
from tools.diag_gpt3_maryborough_source_stage_ledger import build_maryborough_source_stage_ledger
from tools.diag_gpt3_maryborough_source_stage_delta import (
    compare_maryborough_source_stages, main,
)


def _baseline():
    return build_maryborough_source_stage_ledger(*_inputs())


def _advance_host(ledger):
    row = next(x for x in ledger["opening_first_stage_rows"]
               if x["opening_identity_id"] == "opening-A")
    row["stage"] = "COMPLETE_HOST_FRAME_UNPROVEN"
    row["host_binding_record_id"] = "original-new-host-binding-A"
    row["first_stage_reason_codes"] = ["complete_whole_wall_unproven"]
    ledger["host_bindings_source_resolved"] = 3
    ledger["first_unproved_stage_counts"] = {
        "COMPLETE_HOST_FRAME_UNPROVEN": 2,
        "HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED": 1,
    }


def test_same_source_same_universe_identity_stage_advance_is_unscored():
    before, after = _baseline(), _baseline()
    _advance_host(after)
    result = compare_maryborough_source_stages(before, after)
    assert result["physical_candidate_universe_comparable"] is True
    assert result["source_stage_improvement_comparable"] is True
    assert result["advanced_count"] == 1
    assert result["regressed_count"] == 0
    assert result["stage_advanced"][0]["opening_identity_id"] == "opening-A"
    assert result["changed_positive_receipt_ids"] == ["opening-A"]
    assert result["benchmark_score_granted"] is False
    assert result["benchmark_accuracy"] is None
    assert result["source_authenticated_independently"] is False


def test_changed_candidate_universe_must_not_be_presented_as_accuracy_improvement():
    before, after = _baseline(), _baseline()
    _advance_host(after)
    row = {
        "opening_identity_id": "opening-added", "stage": "HOST_BINDING_UNPROVEN",
        "first_stage_reason_codes": ["no_authenticated_host_wall_band"],
        "host_binding_record_id": None, "frame_record_id": None,
    }
    after["opening_first_stage_rows"].append(row)
    after["opening_universe_size"] = 4
    after["first_unproved_stage_counts"]["HOST_BINDING_UNPROVEN"] = 1
    result = compare_maryborough_source_stages(before, after)
    assert result["added_physical_ids"] == ["opening-added"]
    assert result["advanced_count"] == 1
    assert result["physical_candidate_universe_comparable"] is False
    assert result["source_stage_improvement_comparable"] is False
    assert "candidate universe changed" in result["note"]


def test_regression_is_reported_and_cancels_comparable_improvement_flag():
    before, after = _baseline(), _baseline()
    _advance_host(after)
    row = next(x for x in after["opening_first_stage_rows"]
               if x["opening_identity_id"] == "opening-C")
    row["stage"] = "COMPLETE_HOST_FRAME_UNPROVEN"
    row["frame_record_id"] = None
    row["first_stage_reason_codes"] = ["complete_whole_wall_unproven"]
    after["frames_source_resolved"] = 0
    after["first_unproved_stage_counts"] = {
        "COMPLETE_HOST_FRAME_UNPROVEN": 3,
    }
    result = compare_maryborough_source_stages(before, after)
    assert result["advanced_count"] == 1
    assert result["regressed_count"] == 1
    assert result["source_stage_improvement_comparable"] is False
    assert result["stage_regressed"][0]["opening_identity_id"] == "opening-C"


def test_changed_positive_receipt_without_stage_gain_is_not_hidden():
    before, after = _baseline(), _baseline()
    row = next(x for x in after["opening_first_stage_rows"]
               if x["opening_identity_id"] == "opening-B")
    row["host_binding_record_id"] = "new-unverified-rekey"
    result = compare_maryborough_source_stages(before, after)
    assert result["changed_positive_receipt_ids"] == ["opening-B"]
    assert not result["source_stage_improvement_comparable"]
    assert result["advanced_count"] == 0


@pytest.mark.parametrize("alter", [
    "wrong_source_sha", "wrong_project", "forged_benchmark", "forged_source",
    "duplicate_physical_id", "invalid_stage_type", "unproven_has_host_receipt",
    "false_host_count", "contradictory_frame_count", "duplicate_reasons",
    "missing_rows", "unverified_publication",
])
def test_invalid_or_forged_source_ledgers_cannot_compare(alter):
    before, after = _baseline(), _baseline()
    if alter == "wrong_source_sha":
        after["source_sha256"] = "b" * 64
    elif alter == "wrong_project":
        after["project_id"] = "foreign-project"
    elif alter == "forged_benchmark":
        after["benchmark_score_granted"] = True
    elif alter == "forged_source":
        after["original_source_independently_verified"] = True
    elif alter == "duplicate_physical_id":
        after["opening_first_stage_rows"].append(
            deepcopy(after["opening_first_stage_rows"][0])
        )
        after["opening_universe_size"] += 1
    elif alter == "invalid_stage_type":
        after["opening_first_stage_rows"][0]["stage"] = ["not-a-stage"]
    elif alter == "unproven_has_host_receipt":
        after["opening_first_stage_rows"][0]["host_binding_record_id"] = "forged"
    elif alter == "false_host_count":
        after["host_bindings_source_resolved"] = 99
    elif alter == "contradictory_frame_count":
        after["frames_source_resolved"] = 99
    elif alter == "duplicate_reasons":
        after["opening_first_stage_rows"][0]["first_stage_reason_codes"].append(
            "no_authenticated_host_wall_band"
        )
    elif alter == "missing_rows":
        after.pop("opening_first_stage_rows")
    else:
        after["publication_status"] = "BENCHMARK_SCORE_PUBLISHED"
    with pytest.raises(ValueError):
        compare_maryborough_source_stages(before, after)


def test_cli_cannot_replace_source_ledgers_with_own_diagnostic(tmp_path, monkeypatch):
    old = tmp_path / "before.json"
    later = tmp_path / "after.json"
    payload = json.dumps(_baseline())
    old.write_text(payload, encoding="utf-8")
    later.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "source-delta", "--before", str(old), "--after", str(later),
        "--output", str(old),
    ])
    with pytest.raises(ValueError, match="readiness output may not overwrite"):
        main()
    assert old.read_text(encoding="utf-8") == payload
    assert later.read_text(encoding="utf-8") == payload


def test_cli_writes_independent_unpublished_stage_diagnostic(tmp_path, monkeypatch):
    old = tmp_path / "before.json"
    later = tmp_path / "after.json"
    out = tmp_path / "stage_delta.json"
    payload = json.dumps(_baseline())
    old.write_text(payload, encoding="utf-8")
    later.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "source-delta", "--before", str(old), "--after", str(later),
        "--output", str(out),
    ])
    assert main() == 0
    actual = json.loads(out.read_text(encoding="utf-8"))
    assert actual["benchmark_score_granted"] is False
    assert actual["physical_candidate_universe_comparable"] is True
    assert actual["advanced_count"] == 0


def test_source_negative_reason_changes_are_visible_without_stage_promotion():
    before, after = _baseline(), _baseline()
    row = next(x for x in after["opening_first_stage_rows"]
               if x["opening_identity_id"] == "opening-A")
    row["first_stage_reason_codes"] = ["different_original_wall_opposition"]
    report = compare_maryborough_source_stages(before, after)
    assert report["advanced_count"] == 0
    assert report["regressed_count"] == 0
    assert report["changed_negative_reason_ids"] == ["opening-A"]
    assert report["negative_source_evidence_drift_observed"] is True
    assert report["physical_candidate_universe_comparable"] is True
    assert report["source_stage_improvement_comparable"] is False
    assert report["benchmark_score_granted"] is False


def test_unchanged_source_receipts_do_not_mint_improvement():
    report = compare_maryborough_source_stages(_baseline(), _baseline())
    assert report["changed_negative_reason_ids"] == []
    assert report["negative_source_evidence_drift_observed"] is False
    assert report["changed_positive_receipt_ids"] == []
    assert report["advanced_count"] == 0
    assert report["benchmark_accuracy"] is None
