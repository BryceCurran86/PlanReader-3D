"""GPT3 120-target inventory regression tests (no publication/quantities minted)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools import report_gpt3_four_project_evidence as evidence
from tools import gpt3_120_target_input_fingerprint_ledger as ledger


def _blocked_report(tmp_path):
    roots = {
        "source_dir": tmp_path / "private-originals-not-supplied",
        "sealed_dir": tmp_path / "seals-not-supplied",
        "identity_map_dir": tmp_path / "maps-not-supplied",
        "customer_dir": tmp_path / "customer-not-supplied",
    }
    return evidence.build_four_project_evidence_ledger(**roots)


def _original_owner_receipt():
    root = Path(__file__).resolve().parents[1]
    path = root / "docs/engineering/four_job_runs/20261016_47c8031a/RUN_RECEIPT.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_blocked_four_project_evidence_enumerates_120_distinct_unevaluated_items(tmp_path):
    report = _blocked_report(tmp_path)
    actual = ledger.build_120_target_ledger(report)
    assert actual["publication_status"] == "UNPUBLISHED"
    assert actual["official_coverage_accuracy"] is None
    assert actual["official_precision_adjusted_accuracy"] is None
    assert actual["target_count"] == 120
    assert actual["evaluated_target_count"] == 0
    assert actual["not_evaluated_target_count"] == 120
    assert {x["evaluation_state"] for x in actual["items"]} == {"NOT_EVALUATED"}
    assert {x["first_target_authority_failure"] for x in actual["items"]} == {"NOT_DIAGNOSED"}
    assert sorted(sum(x["project_id"] == project["project_id"] for x in actual["items"])
                  for project in report["projects"]) == [6, 24, 27, 63]
    assert len({(x["project_id"], x["item_id"]) for x in actual["items"]}) == 120
    assert all("expected_quantity" not in item for item in actual["items"])


def test_original_run_receipt_statuses_are_audit_only_not_target_scores(tmp_path):
    report = _blocked_report(tmp_path)
    owner = _original_owner_receipt()
    actual = ledger.build_120_target_ledger(
        report, owner_receipt=owner, producer_head=owner["repo_head"],
    )
    by_project = {x["project_id"]: x["owner_handoff_status"] for x in actual["items"]}
    assert by_project["au_qld_maryborough_service_station"] == "MEMORY_LIMIT"
    assert by_project["au_qld_3laurel"] == "COMPLETED"
    assert actual["evaluated_target_count"] == 0
    assert actual["repeat_evaluation_advice"] == "CHANGED_INPUTS_OR_UNPROVEN_COMPARISON"


def test_identical_exact_input_fingerprint_suppresses_replay_advice(tmp_path):
    report = _blocked_report(tmp_path)
    owner = _original_owner_receipt()
    head = owner["repo_head"]
    first = ledger.build_120_target_ledger(
        report, owner_receipt=owner, producer_head=head,
    )
    second = ledger.build_120_target_ledger(
        deepcopy(report), owner_receipt=deepcopy(owner), producer_head=head,
        previous_input_fingerprint=first["input_fingerprint"],
    )
    assert second["input_fingerprint"] == first["input_fingerprint"]
    assert second["repeat_evaluation_advice"] == (
        "UNCHANGED_PRODUCER_SOURCE_SCORING_INPUTS_DO_NOT_RERUN"
    )


def test_owner_runtime_paths_memory_and_elapsed_time_do_not_force_rescore(tmp_path):
    report = _blocked_report(tmp_path)
    owner = _original_owner_receipt()
    head = owner["repo_head"]
    first = ledger.build_120_target_ledger(
        report, owner_receipt=owner, producer_head=head,
    )
    same_evidence = deepcopy(owner)
    same_evidence["project_handoffs"][0]["elapsed_s"] += 999.5
    same_evidence["project_handoffs"][1]["peak_private_mb_sampled"] += 1024
    same_evidence["project_handoffs"][2]["output_folder"] = (
        "C:/new/session/id/should-not-change-source-identity"
    )
    second = ledger.build_120_target_ledger(
        report, owner_receipt=same_evidence, producer_head=head,
        previous_input_fingerprint=first["input_fingerprint"],
    )
    assert second["input_fingerprint"] == first["input_fingerprint"]
    assert second["repeat_evaluation_advice"] == (
        "UNCHANGED_PRODUCER_SOURCE_SCORING_INPUTS_DO_NOT_RERUN"
    )


def test_changed_actual_sealed_output_artifact_invalidates_fingerprint(tmp_path):
    report = _blocked_report(tmp_path)
    owner = _original_owner_receipt()
    head = owner["repo_head"]
    first = ledger.build_120_target_ledger(
        report, owner_receipt=owner, producer_head=head,
    )
    changed = deepcopy(owner)
    sealed_row = next(row for row in changed["files"]
                      if row["file"].endswith(".sealed.json"))
    sealed_row["share_safe_sha256"] = "a" * 64
    second = ledger.build_120_target_ledger(
        report, owner_receipt=changed, producer_head=head,
        previous_input_fingerprint=first["input_fingerprint"],
    )
    assert second["input_fingerprint"] != first["input_fingerprint"]
    assert second["repeat_evaluation_advice"] == "CHANGED_INPUTS_OR_UNPROVEN_COMPARISON"


def test_report_change_invalidates_previous_input_fingerprint(tmp_path):
    report = _blocked_report(tmp_path)
    owner = _original_owner_receipt()
    head = owner["repo_head"]
    first = ledger.build_120_target_ledger(
        report, owner_receipt=owner, producer_head=head,
    )
    altered = deepcopy(report)
    altered["projects"][0]["reason_codes"].append("independently-new-stage-evidence")
    second = ledger.build_120_target_ledger(
        altered, owner_receipt=owner, producer_head=head,
        previous_input_fingerprint=first["input_fingerprint"],
    )
    assert second["input_fingerprint"] != first["input_fingerprint"]
    assert second["repeat_evaluation_advice"] == "CHANGED_INPUTS_OR_UNPROVEN_COMPARISON"


def test_frozen_scorer_change_invalidates_digest_without_changing_gold(tmp_path, monkeypatch):
    report = _blocked_report(tmp_path)
    first = ledger.build_120_target_ledger(report)
    original = ledger._frozen_input_digests
    def changed(manifests):
        hashes = original(manifests)
        hashes["evaluator.py"] = "f" * 64
        return hashes
    monkeypatch.setattr(ledger, "_frozen_input_digests", changed)
    second = ledger.build_120_target_ledger(report)
    assert first["input_fingerprint"] != second["input_fingerprint"]


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda r: r.update(benchmark_id="retired-benchmark"),
        lambda r: r.update(frozen_denominator=51),
        lambda r: r.update(required_project_count=2),
        lambda r: r.update(projects=r["projects"][:-1]),
        lambda r: r["projects"].append(deepcopy(r["projects"][0])),
        lambda r: r["projects"][1].update(project_id=r["projects"][0]["project_id"]),
        lambda r: r["projects"][2].update(denominator=120),
        lambda r: r["projects"][0].update(reason_codes=[False]),
    ],
)
def test_bad_report_universe_and_reason_types_fail_closed(tmp_path, corrupt):
    report = _blocked_report(tmp_path)
    corrupt(report)
    with pytest.raises(ValueError):
        ledger.build_120_target_ledger(report)


def test_fake_publication_cannot_bypass_incomplete_frozen_manifests(tmp_path):
    report = _blocked_report(tmp_path)
    report["publication_status"] = "PUBLISHED"
    report["coverage_accuracy"] = 1.0
    report["precision_adjusted_accuracy"] = 1.0
    with pytest.raises(ValueError, match="VERIFIED frozen project manifests"):
        ledger.build_120_target_ledger(report)


def test_original_receipt_cannot_be_attached_to_foreign_producer_head(tmp_path):
    report = _blocked_report(tmp_path)
    owner = _original_owner_receipt()
    with pytest.raises(ValueError, match="producer commit conflicts"):
        ledger.build_120_target_ledger(
            report, owner_receipt=owner, producer_head="0"*40,
        )


def test_missing_producer_commit_never_suppresses_repeat_advice(tmp_path):
    report = _blocked_report(tmp_path)
    first = ledger.build_120_target_ledger(report)
    repeated = ledger.build_120_target_ledger(
        report, previous_input_fingerprint=first["input_fingerprint"],
    )
    assert repeated["repeat_evaluation_advice"] == "CHANGED_INPUTS_OR_UNPROVEN_COMPARISON"


def test_cli_generates_120_unscored_items_without_private_source_files(tmp_path):
    report = _blocked_report(tmp_path)
    report_path = tmp_path / "evidence.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out = tmp_path / "target-ledger.json"
    code = ledger.main([
        "--evidence-report", str(report_path), "--output", str(out),
    ])
    assert code == 2
    obj = json.loads(out.read_text(encoding="utf-8"))
    assert obj["target_count"] == 120
    assert obj["evaluated_target_count"] == 0
    with pytest.raises(ValueError, match="cannot overwrite"):
        ledger.main([
            "--evidence-report", str(report_path), "--output", str(report_path),
        ])
