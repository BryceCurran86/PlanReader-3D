"""Source candidate membership may change despite unchanged opening/host totals."""
from copy import deepcopy
import json
import sys

import pytest

from tools.diag_gpt3_original_source_membership import compare_source_membership, main
from tests.symlink_test_support import symlink_or_skip


def _report():
    return {
        "source_sha256": "a" * 64,
        "revision_id": "revision-a",
        "snapshot_id": "snapshot-a",
        "selected_geometry_page_ids": ["3"],
        "all_source_pages_requested": True,
        "primitive_safety_cap": 20_000,
        "native_candidate_closures": [{
            "page_id": "3", "unresolved_candidate_ids": ["candidate-1", "candidate-2"],
            "unresolved_observation_ids": ["obs-1", "obs-2"],
            "raw_candidate_count": 2, "resolved_candidate_count": 0,
            "candidate_universe_complete": False, "status": "corroborated",
            "reason_codes": ["physical_opening_candidate_closure_unresolved"],
        }],
        "semantic_inventory": {"record": {
            "visible_observation_ids": ["obs-1", "obs-2", "obs-3"],
            "conflict_observation_ids": ["obs-1", "obs-2"],
            "residual_visible_observation_ids": ["obs-3"],
            "opening_support_observation_ids": ["obs-1"],
            "physical_opening_record_ids": ["opening-1"],
            "representative_observation_ids": ["obs-1"],
            "record_id": "semantic-record-1", "decision_scope_id": "scope-a",
            "source_sha256": "a" * 64,
            "snapshot_id": "snapshot-a", "revision_id": "revision-a",
            "physical_opening_universe_complete": False,
            "structural_enumeration_complete": False, "reason_codes": [],
        }},
        "canonical_openings": [{"id": "opening-1"}],
        "opening_bindings": [{"opening_identity_id": "opening-1", "host_wall_id": "wall-a"}],
        "host_frame_traces": [{"opening_identity_id": "opening-1", "record_id": "frame-1"}],
        "resolved_host_frame_evidence": [{"frame": "frame-1"}],
        "opening_label_semantic_traces": [],
        "opening_figured_label_traces": [],
        "opening_measurement_traces": [{
            "opening_identity_id": "opening-1", "page_id": "3",
            "width_status": "abstained", "width_record_id": None,
            "void_reason_codes": ["source_universe_incomplete", "physical_opening_undecided"],
        }],
        "opening_void_reason_codes": ["physical_opening_undecided", "source_universe_incomplete"],
        "source_owned_wall_scopes": [],
    }


def test_identical_reports_are_unpublished_and_have_no_claimed_accuracy():
    before = _report()
    audit = compare_source_membership(before, deepcopy(before))
    assert audit["parity_pass"] is True
    assert audit["benchmark_score_granted"] is False
    assert audit["source_authenticated_independently"] is False
    assert audit["benchmark_accuracy"] is None


def test_unresolved_and_conflict_membership_drift_is_not_hidden_by_same_host_totals():
    before, after = _report(), _report()
    after["native_candidate_closures"][0]["unresolved_candidate_ids"] = [
        "candidate-2", "candidate-3",
    ]
    after["native_candidate_closures"][0]["unresolved_observation_ids"].append("obs-3")
    after["semantic_inventory"]["record"]["conflict_observation_ids"] = ["obs-2"]
    after["semantic_inventory"]["record"]["residual_visible_observation_ids"] = [
        "obs-1", "obs-3",
    ]
    after["semantic_inventory"]["record"]["record_id"] = "semantic-record-2"
    report = compare_source_membership(before, after)
    assert report["parity_pass"] is False
    assert report["status"] == "SOURCE_MEMBERSHIP_DRIFT_UNPUBLISHED"
    changes = {row["path"]: row for row in report["changes"]}
    native = changes["native_candidate_closures[3].unresolved_candidate_ids"]
    assert native["added_count"] == native["removed_count"] == 1
    assert native["added_ids_sample"] == ["candidate-3"]
    assert native["removed_ids_sample"] == ["candidate-1"]
    assert native["added_ids"] == ["candidate-3"]
    assert native["removed_ids"] == ["candidate-1"]
    assert changes["semantic_inventory.record.conflict_observation_ids"]["removed_ids_sample"] == ["obs-1"]
    assert not any(row["path"] == "opening_bindings" for row in report["changes"])


def test_host_proof_change_is_not_masked_by_same_membership():
    before, after = _report(), _report()
    after["opening_bindings"][0]["host_wall_id"] = "wall-b"
    result = compare_source_membership(before, after)
    assert not result["parity_pass"]
    assert any(row["path"] == "opening_bindings" for row in result["changes"])


@pytest.mark.parametrize("tamper", [
    "sha", "revision", "snapshot", "page", "safety_cap",
    "duplicate_native", "duplicate_semantic", "missing_semantic",
    "missing_protected", "foreign_native_page", "foreign_semantic_source",
    "foreign_semantic_snapshot", "one_sided_source_scope",
])
def test_incompatible_or_malformed_source_evidence_fails_closed(tamper):
    old, new = _report(), _report()
    if tamper == "sha":
        new["source_sha256"] = "b" * 64
    elif tamper == "revision":
        new["revision_id"] = "other-revision"
    elif tamper == "snapshot":
        new["snapshot_id"] = "other-snapshot"
    elif tamper == "page":
        new["selected_geometry_page_ids"] = ["4"]
    elif tamper == "safety_cap":
        new["primitive_safety_cap"] = 21_000
    elif tamper == "duplicate_native":
        new["native_candidate_closures"][0]["unresolved_candidate_ids"].append("candidate-1")
    elif tamper == "duplicate_semantic":
        new["semantic_inventory"]["record"]["conflict_observation_ids"].append("obs-1")
    elif tamper == "missing_semantic":
        new.pop("semantic_inventory")
    elif tamper == "missing_protected":
        new.pop("canonical_openings")
    elif tamper == "foreign_semantic_source":
        new["semantic_inventory"]["record"]["source_sha256"] = "b" * 64
    elif tamper == "foreign_semantic_snapshot":
        new["semantic_inventory"]["record"]["snapshot_id"] = "other-snapshot"
    elif tamper == "one_sided_source_scope":
        new["source_room_face_scopes"] = [{"foreign": "scope"}]
    else:
        new["native_candidate_closures"].append(deepcopy(new["native_candidate_closures"][0]))
    with pytest.raises(ValueError):
        compare_source_membership(old, new)


def test_source_record_id_reissue_is_detected_even_with_same_member_sets():
    old, new = _report(), _report()
    new["semantic_inventory"]["record"]["record_id"] = "other-record"
    audit = compare_source_membership(old, new)
    assert not audit["parity_pass"]
    assert audit["changes"][0]["path"] == "semantic_inventory.record.record_id"


@pytest.mark.parametrize("target", ["baseline", "candidate", "baseline_symlink"])
def test_cli_never_overwrites_source_evidence_even_through_symlink(tmp_path, monkeypatch, target):
    baseline = tmp_path / "before.json"
    candidate = tmp_path / "after.json"
    payload = json.dumps(_report(), sort_keys=True)
    baseline.write_text(payload, encoding="utf-8")
    candidate.write_text(payload, encoding="utf-8")
    alias = tmp_path / "alias.json"
    symlink_or_skip(alias, baseline)
    output = {"baseline": baseline, "candidate": candidate, "baseline_symlink": alias}[target]
    monkeypatch.setattr(sys, "argv", [
        "source-diff", "--baseline", str(baseline),
        "--candidate", str(candidate), "--output", str(output),
    ])
    with pytest.raises(ValueError, match="readiness output may not overwrite"):
        main()
    assert baseline.read_text(encoding="utf-8") == payload
    assert candidate.read_text(encoding="utf-8") == payload


def test_cli_unpublished_result_written_only_to_independent_output(tmp_path, monkeypatch):
    baseline = tmp_path / "before.json"
    candidate = tmp_path / "after.json"
    output = tmp_path / "diagnostic.json"
    payload = json.dumps(_report())
    baseline.write_text(payload, encoding="utf-8")
    candidate.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "source-diff", "--baseline", str(baseline),
        "--candidate", str(candidate), "--output", str(output),
    ])
    assert main() == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["parity_pass"] is True
    assert result["benchmark_score_granted"] is False
    assert result["benchmark_accuracy"] is None


def test_opening_measurement_receipt_cannot_change_when_host_totals_match():
    old, new = _report(), _report()
    new["opening_measurement_traces"][0].update(
        width_status="corroborated", width_record_id="forged-original-width",
    )
    audit = compare_source_membership(old, new)
    assert not audit["parity_pass"]
    assert any(row["path"] == "opening_measurement_traces" for row in audit["changes"])


def test_unordered_void_reason_witness_order_does_not_fake_source_drift():
    old, new = _report(), _report()
    new["opening_measurement_traces"][0]["void_reason_codes"].reverse()
    new["opening_void_reason_codes"].reverse()
    assert compare_source_membership(old, new)["parity_pass"] is True


@pytest.mark.parametrize("mutation", ["duplicate_measurement", "invalid_void_reason", "missing_measurement"])
def test_invalid_original_measurement_universe_fails_closed(mutation):
    old, new = _report(), _report()
    if mutation == "duplicate_measurement":
        new["opening_measurement_traces"].append(
            deepcopy(new["opening_measurement_traces"][0])
        )
    elif mutation == "invalid_void_reason":
        new["opening_measurement_traces"][0]["void_reason_codes"] = ["valid", "valid"]
    else:
        del new["opening_measurement_traces"]
    with pytest.raises(ValueError):
        compare_source_membership(old, new)


@pytest.mark.parametrize("field,new_value", [
    ("document_id", "foreign-document"),
    ("decision_scope_kind", "untrusted-other-scope"),
    ("schema_version", "unsupported-next-schema"),
    ("page_ids", ["4"]),
])
def test_original_semantic_document_scope_and_schema_changes_never_silent(field, new_value):
    old, new = _report(), _report()
    new["semantic_inventory"]["record"][field] = new_value
    audit = compare_source_membership(old, new)
    assert not audit["parity_pass"]
    assert any(
        row["path"] == "semantic_inventory.record." + field
        for row in audit["changes"]
    )


def test_full_change_ledger_is_not_truncated_after_eight_source_identities():
    old, new = _report(), _report()
    new_ids = [f"candidate-extra-{index:02d}" for index in range(12)]
    new["native_candidate_closures"][0]["unresolved_candidate_ids"].extend(new_ids)
    result = compare_source_membership(old, new)
    delta = next(row for row in result["changes"]
                 if row["path"] == "native_candidate_closures[3].unresolved_candidate_ids")
    assert delta["added_ids"] == new_ids
    assert len(delta["added_ids_sample"]) == 8
    assert result["parity_pass"] is False
