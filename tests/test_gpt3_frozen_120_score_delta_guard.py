"""Source-neutral tests for exact 120-item *postscore* change accounting.

These are synthetic, untrusted post-evaluator snapshots, not benchmark
executions or proof of signed extraction, geometry or source closure.
"""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from tools import gpt3_frozen_120_score_delta_guard as delta


@pytest.fixture(autouse=True)
def _synthetic_future_verified_manifests(monkeypatch):
    # These synthetic PUBLISHED snapshots test the delta arithmetic only;
    # the actual frozen 2026-10-17 manifests remain INCOMPLETE and cannot publish.
    monkeypatch.setattr(delta, "_official_source_universe_verified", lambda: True)


def _fake_ledger(*, published: bool = False, fingerprint: str = "a" * 64) -> dict:
    targets, sources, scorer = delta._expected_inputs_and_targets()
    rows = []
    for (project, target), (trade, unit) in sorted(targets.items()):
        rows.append({
            "project_id": project, "item_id": target,
            "trade_category": trade, "unit": unit,
            "evaluation_state": "MISSED" if published else "NOT_EVALUATED",
            "produced_quantity_id": None,
            "first_target_authority_failure": "NOT_DIAGNOSED",
            "project_evidence_status": ("PROJECT_VERIFIED" if published else "PROJECT_BLOCKED"),
            "project_gate_reasons": [] if published else ["not_scored"],
        })
    return {
        "schema_version": "gpt3-120-target-ledger-v1",
        "target_count": 120,
        "evaluated_target_count": 120 if published else 0,
        "not_evaluated_target_count": 0 if published else 120,
        "publication_status": "PUBLISHED" if published else "UNPUBLISHED",
        "producer_head": "b" * 40 if published else None,
        "source_sha256s_by_project": sources,
        "frozen_file_sha256s": scorer,
        "input_fingerprint": fingerprint,
        "official_coverage_accuracy": 0.0 if published else None,
        "official_precision_adjusted_accuracy": 0.0 if published else None,
        "items": rows,
    }


def _set_scored(ledger, idx, state, quantity_id):
    ledger["items"][idx]["evaluation_state"] = state
    ledger["items"][idx]["produced_quantity_id"] = quantity_id
    matched = sum(
        row["evaluation_state"] == "MATCHED_WITHIN_TOLERANCE"
        for row in ledger["items"]
    )
    ledger["official_coverage_accuracy"] = matched / 120
    ledger["official_precision_adjusted_accuracy"] = matched / 120


def test_two_missing_official_scores_must_not_be_called_zero_or_gains():
    old = _fake_ledger()
    fresh = _fake_ledger(fingerprint="c" * 64)
    result = delta.compare_postscore_ledgers(old, fresh)
    assert result["comparison_status"] == "OFFICIAL_BASELINE_OR_REEVALUATION_UNAVAILABLE"
    assert result["score_comparison_available"] is False
    assert result["before_coverage_accuracy"] is None
    assert result["after_coverage_accuracy"] is None
    assert result["net_additional_correct_items"] is None
    assert result["accuracy_percentage_point_change"] is None
    assert result["newly_correct_target_ids"] == []
    assert result["regressed_target_ids"] == []


def test_mixed_published_and_unpublished_rejects_claim_of_40pp():
    old = _fake_ledger()
    fresh = _fake_ledger(published=True, fingerprint="d" * 64)
    _set_scored(fresh, 0, "MATCHED_WITHIN_TOLERANCE", "synthetic-q0")
    result = delta.compare_postscore_ledgers(old, fresh)
    assert result["score_comparison_available"] is False
    assert result["net_additional_correct_items"] is None


def test_synthetic_two_gains_one_regression_net_exact_one_target():
    old = _fake_ledger(published=True, fingerprint="a" * 64)
    fresh = _fake_ledger(published=True, fingerprint="b" * 64)
    _set_scored(old, 1, "MATCHED_WITHIN_TOLERANCE", "synthetic-old-1")
    _set_scored(fresh, 0, "MATCHED_WITHIN_TOLERANCE", "synthetic-new-0")
    _set_scored(fresh, 2, "MATCHED_WITHIN_TOLERANCE", "synthetic-new-2")
    result = delta.compare_postscore_ledgers(old, fresh)
    assert result["score_comparison_available"] is True
    assert result["gross_new_correct_items"] == 2
    assert result["regressed_correct_items"] == 1
    assert result["net_additional_correct_items"] == 1
    assert result["accuracy_percentage_point_change"] == pytest.approx(100/120)
    assert len(result["newly_correct_target_ids"]) == 2
    assert len(result["regressed_target_ids"]) == 1
    assert result["issuer_authentication_proven_by_this_comparator"] is False


def test_genuine_repeat_fingerprint_reports_no_new_targets():
    before = _fake_ledger(published=True)
    result = delta.compare_postscore_ledgers(before, deepcopy(before))
    assert result["comparison_status"] == "UNCHANGED_PRODUCER_SOURCE_SCORING_INPUTS"
    assert result["net_additional_correct_items"] == 0
    assert result["accuracy_percentage_point_change"] == 0


def test_changed_target_with_identical_input_fingerprint_is_forbidden():
    before = _fake_ledger(published=True)
    after = deepcopy(before)
    _set_scored(after, 0, "MATCHED_WITHIN_TOLERANCE", "synthetic-q")
    with pytest.raises(ValueError, match="same scoring fingerprint"):
        delta.compare_postscore_ledgers(before, after)


def test_modified_unpublished_targets_are_never_accepted_as_evaluation():
    before = _fake_ledger()
    after = _fake_ledger(fingerprint="c" * 64)
    after["items"][0]["evaluation_state"] = "MISSED"
    with pytest.raises(ValueError, match="unpublished run"):
        delta.compare_postscore_ledgers(before, after)


@pytest.mark.parametrize(
    "damage",
    [
        lambda x: x.update(target_count=119),
        lambda x: x.update(schema_version="wrong"),
        lambda x: x.update(evaluated_target_count=3),
        lambda x: x.update(not_evaluated_target_count=1),
        lambda x: x.update(official_coverage_accuracy=0),
        lambda x: x["items"].pop(),
        lambda x: x["items"].append(deepcopy(x["items"][0])),
        lambda x: x["items"][0].update(item_id="synthetic-nonexistent-id"),
        lambda x: x["items"][0].update(trade_category="wrong-trade"),
        lambda x: x["items"][0].update(unit="wrong-unit"),
        lambda x: x["source_sha256s_by_project"].update(
            {next(iter(x["source_sha256s_by_project"])): ["0"*64]}),
        lambda x: x["frozen_file_sha256s"].update({"evaluator.py": "0" * 64}),
        lambda x: x.update(input_fingerprint="NOT_SHA256"),
        lambda x: x.update(producer_head=True),
    ],
)
def test_14_independent_unpublished_scope_integrity_negatives(damage):
    before = _fake_ledger()
    after = deepcopy(before)
    damage(after)
    with pytest.raises(ValueError):
        delta.compare_postscore_ledgers(before, after)


@pytest.mark.parametrize(
    "damage",
    [
        lambda x: x.update(evaluated_target_count=119),
        lambda x: x.update(not_evaluated_target_count=1),
        lambda x: x["items"][0].update(evaluation_state="NOT_EVALUATED"),
        lambda x: x["items"][0].update(
            evaluation_state="MATCHED_WITHIN_TOLERANCE",
            produced_quantity_id=None),
        lambda x: x.update(official_coverage_accuracy=0.9),
        lambda x: x.update(official_precision_adjusted_accuracy=0.8),
        lambda x: x.update(producer_head=None),
    ],
)
def test_published_target_source_and_numerator_invariants_fail_closed(damage):
    old = _fake_ledger(published=True)
    new = _fake_ledger(published=True, fingerprint="b" * 64)
    damage(new)
    with pytest.raises(ValueError):
        delta.compare_postscore_ledgers(old, new)


def test_nonwinning_status_change_and_rekey_are_not_extra_correct_targets():
    old = _fake_ledger(published=True, fingerprint="1" * 64)
    new = _fake_ledger(published=True, fingerprint="2" * 64)
    new["items"][0]["evaluation_state"] = "UNRESOLVED"
    old["items"][1]["evaluation_state"] = "UNRESOLVED"
    new["items"][1]["evaluation_state"] = "UNRESOLVED"
    old["items"][1]["produced_quantity_id"] = "synthetic-old-id"
    new["items"][1]["produced_quantity_id"] = "synthetic-new-id"
    out = delta.compare_postscore_ledgers(old, new)
    assert out["net_additional_correct_items"] == 0
    assert len(out["other_changed_target_states"]) == 1
    assert len(out["changed_produced_quantity_ids"]) == 1


def test_actual_unverified_frozen_manifest_blocks_any_published_comparison(monkeypatch):
    monkeypatch.setattr(delta, "_official_source_universe_verified", lambda: False)
    with pytest.raises(ValueError, match="INCOMPLETE"):
        delta.compare_postscore_ledgers(_fake_ledger(published=True),
                                        _fake_ledger(published=True, fingerprint="c"*64))


def test_identical_input_fingerprint_cannot_hide_new_producer_head():
    old = _fake_ledger(published=True)
    new = deepcopy(old)
    new["producer_head"] = "f"*40
    with pytest.raises(ValueError, match="same scoring fingerprint"):
        delta.compare_postscore_ledgers(old, new)


def test_cli_cannot_overwrite_either_ledger(tmp_path):
    old = tmp_path / "before.json"
    new = tmp_path / "after.json"
    old.write_text(json.dumps(_fake_ledger()), encoding="utf-8")
    new.write_text(json.dumps(_fake_ledger(fingerprint="d"*64)), encoding="utf-8")
    out = tmp_path / "comparison.json"
    assert delta.main([
        "--before-ledger", str(old), "--after-ledger", str(new),
        "--output", str(out),
    ]) == 2
    with pytest.raises(ValueError, match="cannot overwrite"):
        delta.main([
            "--before-ledger", str(old), "--after-ledger", str(new),
            "--output", str(old),
        ])


def test_precision_adjusted_must_have_integer_unsupported_extra_denominator():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    _set_scored(new, 0, "MATCHED_WITHIN_TOLERANCE", "synthetic-q")
    # One winner, official precision 1/(120+integer extras). 0.0051 is
    # misleading but bounded by coverage; no integer extras can yield it.
    new["official_precision_adjusted_accuracy"] = 0.0051
    with pytest.raises(ValueError, match="integer unsupported-extra"):
        delta.compare_postscore_ledgers(old, new)


def test_precision_adjusted_can_legitimately_include_extra_produced_items():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    _set_scored(new, 0, "MATCHED_WITHIN_TOLERANCE", "synthetic-q")
    new["official_precision_adjusted_accuracy"] = 1/124
    result = delta.compare_postscore_ledgers(old, new)
    assert result["net_additional_correct_items"] == 1
    assert result["after_precision_adjusted_accuracy"] == pytest.approx(1/124)
    assert result["issuer_authentication_proven_by_this_comparator"] is False


def test_precision_adjusted_zero_winners_has_no_arbitrary_positive_value():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    new["official_precision_adjusted_accuracy"] = 0.01
    with pytest.raises(ValueError, match="consistent with item states"):
        delta.compare_postscore_ledgers(old, new)


def test_published_two_targets_must_not_consume_same_signed_quantity_twice():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    _set_scored(new, 0, "MATCHED_WITHIN_TOLERANCE", "q-duplicate")
    _set_scored(new, 1, "MATCHED_WITHIN_TOLERANCE", "q-duplicate")
    with pytest.raises(ValueError, match="matched multiple frozen targets"):
        delta.compare_postscore_ledgers(old, new)


def test_published_target_cannot_hide_unverified_project_customer():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    new["items"][0]["project_evidence_status"] = "PROJECT_BLOCKED"
    with pytest.raises(ValueError, match="source/customer-verified project"):
        delta.compare_postscore_ledgers(old, new)


def test_published_target_cannot_hide_project_level_source_failure():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    new["items"][0]["project_gate_reasons"] = ["source_sha_unverified"]
    with pytest.raises(ValueError, match="unresolved project-level gates"):
        delta.compare_postscore_ledgers(old, new)


def test_frozen_postscore_delta_records_integer_extra_precision_separately():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    _set_scored(old, 0, "MATCHED_WITHIN_TOLERANCE", "old-original-q")
    _set_scored(new, 0, "MATCHED_WITHIN_TOLERANCE", "old-original-q")
    _set_scored(new, 1, "MATCHED_WITHIN_TOLERANCE", "new-source-q")
    old["official_precision_adjusted_accuracy"] = 1/125
    new["official_precision_adjusted_accuracy"] = 2/124
    result = delta.compare_postscore_ledgers(old, new)
    assert result["before_unsupported_extra_count_from_evaluator"] == 5
    assert result["after_unsupported_extra_count_from_evaluator"] == 4
    assert result["net_additional_correct_items"] == 1
    assert result["precision_adjusted_percentage_point_change"] == pytest.approx(
        100*(2/124-1/125)
    )


def test_unpublished_delta_never_reports_unsupported_extra_or_precision_gain():
    old = _fake_ledger()
    new = _fake_ledger(fingerprint="f"*64)
    result = delta.compare_postscore_ledgers(old, new)
    assert result["before_unsupported_extra_count_from_evaluator"] is None
    assert result["after_unsupported_extra_count_from_evaluator"] is None
    assert result["precision_adjusted_percentage_point_change"] is None


@pytest.mark.parametrize(
    "damage",
    [
        lambda x: x["items"][0].update(first_target_authority_failure="MISSED"),
        lambda x: x["items"][0].update(first_target_authority_failure=None),
        lambda x: x["items"][0].update(project_gate_reasons="gate-string"),
        lambda x: x["items"][0].update(project_gate_reasons=[False]),
        lambda x: x["items"][0].update(project_evidence_status=None),
    ],
)
def test_target_inventory_cannot_invent_unpublished_source_authority(damage):
    before = _fake_ledger()
    new = _fake_ledger(fingerprint="f"*64)
    damage(new)
    with pytest.raises(ValueError, match="target row invents"):
        delta.compare_postscore_ledgers(before, new)


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x["items"][0].update(project_evidence_status="UNAVAILABLE"),
        lambda x: x["items"][0].update(project_gate_reasons=["fake-new-source-blocker"]),
        lambda x: x["items"][0].update(owner_handoff_status="MEMORY_LIMIT"),
    ],
)
def test_same_input_fingerprint_must_include_identical_source_gate_metadata(change):
    old = _fake_ledger()
    new = deepcopy(old)
    change(new)
    with pytest.raises(ValueError, match="same scoring fingerprint"):
        delta.compare_postscore_ledgers(old, new)


def test_score_report_cannot_replace_unrelated_existing_customer_data(tmp_path):
    old, new = tmp_path/"old.json", tmp_path/"new.json"
    old.write_text(json.dumps(_fake_ledger()), encoding="utf-8")
    new.write_text(json.dumps(_fake_ledger(fingerprint="f"*64)), encoding="utf-8")
    customer = tmp_path / "signed-customer.json"
    data = '{"source_customer_row": "immutable"}'
    customer.write_text(data, encoding="utf-8")
    with pytest.raises(ValueError, match="may not overwrite other evidence"):
        delta.main([
            "--before-ledger", str(old), "--after-ledger", str(new),
            "--output", str(customer),
        ])
    assert customer.read_text(encoding="utf-8") == data


def test_score_report_can_repeat_to_own_prior_diagnostic(tmp_path):
    old, new = tmp_path/"old.json", tmp_path/"new.json"
    out = tmp_path/"comparison.json"
    old.write_text(json.dumps(_fake_ledger()), encoding="utf-8")
    new.write_text(json.dumps(_fake_ledger(fingerprint="f"*64)), encoding="utf-8")
    args = [
        "--before-ledger", str(old), "--after-ledger", str(new),
        "--output", str(out),
    ]
    assert delta.main(args) == 2
    first = out.read_bytes()
    assert delta.main(args) == 2
    assert out.read_bytes() == first
    assert json.loads(first)["schema_version"] == "gpt3-postscore-delta-v1"


def test_score_report_rejects_existing_binary_artifact_and_symlink(tmp_path):
    old, new = tmp_path/"old.json", tmp_path/"new.json"
    old.write_text(json.dumps(_fake_ledger()), encoding="utf-8")
    new.write_text(json.dumps(_fake_ledger(fingerprint="f"*64)), encoding="utf-8")
    binary = tmp_path/"signed-v1.bin"
    binary.write_bytes(b"immutable-binary-data")
    args = ["--before-ledger", str(old), "--after-ledger", str(new)]
    with pytest.raises(ValueError, match="may not overwrite other evidence"):
        delta.main([*args, "--output", str(binary)])
    assert binary.read_bytes() == b"immutable-binary-data"
    alias = tmp_path/"alias.json"
    alias.symlink_to(binary)
    with pytest.raises(ValueError, match="cannot follow an output symlink"):
        delta.main([*args, "--output", str(alias)])
    assert binary.read_bytes() == b"immutable-binary-data"


@pytest.mark.parametrize("blocked_status", ["MEMORY_LIMIT", "TIMEOUT", "PROCESS_FAILED", "SYSTEM_MEMORY_GUARD"])
def test_published_target_cannot_claim_score_from_failed_owner_process(blocked_status):
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    new["items"][0]["owner_handoff_status"] = blocked_status
    with pytest.raises(ValueError, match="stopped owner source process"):
        delta.compare_postscore_ledgers(old, new)


@pytest.mark.parametrize("quantity_id", ["", "   ", " q-id", "q-id ", "\tq-id"])
def test_published_exact_target_rejects_malformed_machine_quantity_identity(quantity_id):
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    _set_scored(new, 0, "MATCHED_WITHIN_TOLERANCE", quantity_id)
    with pytest.raises(ValueError, match="matched target requires exact"):
        delta.compare_postscore_ledgers(old, new)


def test_published_target_may_legitimately_lack_owner_machine_receipt():
    old = _fake_ledger(published=True, fingerprint="a"*64)
    new = _fake_ledger(published=True, fingerprint="b"*64)
    _set_scored(new, 0, "MATCHED_WITHIN_TOLERANCE", "source-owned-q")
    new["items"][0]["owner_handoff_status"] = None
    result = delta.compare_postscore_ledgers(old, new)
    assert result["net_additional_correct_items"] == 1
