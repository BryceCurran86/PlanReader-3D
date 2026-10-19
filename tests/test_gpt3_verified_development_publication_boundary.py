"""GPT3 must never confuse an incomplete frozen project with missing execution.

These synthetic sources exercise report decisions only. They are NOT plan PDFs
and cannot confer quantity, customer or benchmark publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import report_gpt3_four_project_evidence as report


@dataclass(frozen=True)
class _SyntheticDevelopment:
    status: str = "COMPLETE_CURRENT_TRUTH_SET"
    configured_projects: int = 4
    executed_projects: int = 4
    development_accuracy: float = 0.0


def _four_source_verified_projects(tmp_path: Path, monkeypatch):
    roots = {
        "source_dir": tmp_path / "source",
        "sealed_dir": tmp_path / "sealed",
        "identity_map_dir": tmp_path / "mapping",
        "customer_dir": tmp_path / "customer",
    }
    frozen = tmp_path / "fake-manifests"
    manifests = []
    for i in range(4):
        project_id = f"synthetic-project-{i}"
        name = f"original-{i}.pdf"
        original = roots["source_dir"] / name
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(f"%PDF-synthetic-not-real-{i}".encode("ascii"))
        digest = sha256(original.read_bytes()).hexdigest()
        document = SimpleNamespace(
            name=name, sha256=digest, role="architectural",
        )
        manifests.append(SimpleNamespace(
            project_id=project_id,
            source_documents=(document,),
            verified_items=tuple(
                SimpleNamespace(
                    item_id=f"synthetic-{i}-{j}",
                    denominator_eligible=True,
                    trade_category="flooring",
                )
                for j in range(30)
            ),
            status="INCOMPLETE",
            source_package_complete=True,
            reason_codes=("source_quantity_universe_not_closed",),
        ))
        canonical = frozen / "projects" / project_id / "source_manifest.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_text(json.dumps({
            "project_id": project_id,
            "source_documents": [{
                "name": name, "size_bytes": original.stat().st_size,
                "sha256": digest,
            }],
        }), encoding="utf-8")
        for root, suffix in (
            ("sealed_dir", ".json"),
            ("identity_map_dir", ".identity_map.json"),
            ("customer_dir", ".customer_rows.json"),
        ):
            target = roots[root] / (project_id + suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                "[]" if root == "customer_dir"
                else json.dumps({"project_id": project_id, "source_sha256s": [digest]}),
                encoding="utf-8",
            )

    monkeypatch.setattr(report, "FROZEN_ROOT", frozen)
    monkeypatch.setattr(report, "load_suite_manifests", lambda _: manifests)
    monkeypatch.setattr(
        report, "sealed_source_closed_run_from_dict",
        lambda value: SimpleNamespace(
            project_id=value["project_id"],
            source_sha256s=value["source_sha256s"],
            # Synthetic original-source attempt with an explicit ABSTAIN;
            # unlike a completely empty V1 producer this is an execution.
            quantities=(SimpleNamespace(
                quantity_id=f"attempt-{value['project_id']}",
                abstained=True,
                object_identity_refs=(),
            ),),
            to_dict=lambda: value,
        ),
    )
    monkeypatch.setattr(
        report, "identity_map_from_dict",
        lambda value: SimpleNamespace(
            project_id=value["project_id"],
            source_sha256s=value["source_sha256s"],
            bindings=(),
        ),
    )
    monkeypatch.setattr(
        report, "verify_sealed_customer_output",
        lambda sealed, _: SimpleNamespace(
            project_id=sealed.project_id,
            sealed_quantity_count=1,
            valid_quantity_count=0,
            abstained_quantity_count=1,
            customer_row_count=0,
            verified_quantity_ids=(),
        ),
    )
    monkeypatch.setattr(report, "reconcile_sealed_run_v2", lambda *_: ())
    monkeypatch.setattr(
        report, "_unchanged_frozen_exact_report",
        lambda manifest_path, *_: {
            "project_id": manifest_path.parent.name,
            "source_sha_verified": True,
            "reconciliation_complete": True,
            "denominator": 30,
        },
    )
    return roots, manifests


def test_all_four_verified_executions_remain_officially_unpublished(
    tmp_path, monkeypatch,
):
    roots, manifests = _four_source_verified_projects(tmp_path, monkeypatch)
    calls = []
    def development_evaluator(items, produced):
        calls.append((items, produced))
        return _SyntheticDevelopment()
    def forbidden_official(*_args, **_kwargs):
        raise AssertionError("incomplete project must not enter official evaluator")
    monkeypatch.setattr(report, "evaluate_development_suite_v2", development_evaluator)
    monkeypatch.setattr(report, "evaluate_suite_v2", forbidden_official)

    original_hashes = {
        path: sha256(path.read_bytes()).hexdigest()
        for root in roots.values() for path in root.rglob("*") if path.is_file()
    }
    result = report.build_four_project_evidence_ledger(**roots)

    assert result["publication_status"] == "UNPUBLISHED"
    assert result["official_suite_result"] is None
    assert result["coverage_accuracy"] is None
    assert result["precision_adjusted_accuracy"] is None
    assert result["frozen_denominator"] == 120
    assert result["independently_verified_execution_count"] == 4
    assert result["reason_codes"] == ["frozen_project_manifests_incomplete"]
    assert result["development_suite_result"] == {
        "status": "COMPLETE_CURRENT_TRUTH_SET",
        "configured_projects": 4,
        "executed_projects": 4,
        "development_accuracy": 0.0,
    }
    assert len(calls) == 1
    assert calls[0][0] is manifests
    assert set(calls[0][1]) == {m.project_id for m in manifests}
    assert all(not rows for rows in calls[0][1].values())
    assert all(
        row["publication_status"] == "DIAGNOSTIC_UNPUBLISHED"
        and row["customer_bijection_verified"]
        and row["reconciliation_complete"]
        and row["first_failing_authority_stage"]
            == "frozen_project_source_universe_incomplete"
        for row in result["projects"]
    )
    assert original_hashes == {
        path: sha256(path.read_bytes()).hexdigest()
        for root in roots.values() for path in root.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize(("lost", "expected_stage"), [
    ("source_dir", "original_source_file_absent"),
    ("customer_dir", "sealed_reconciliation_artifact_absent"),
    ("sealed_dir", "sealed_reconciliation_artifact_absent"),
])
def test_missing_original_or_customer_receipt_prevents_development_suite(
    tmp_path, monkeypatch, lost, expected_stage,
):
    roots, manifests = _four_source_verified_projects(tmp_path, monkeypatch)
    target = manifests[2]
    suffix = {
        "source_dir": ".pdf",
        "customer_dir": ".customer_rows.json",
        "sealed_dir": ".json",
    }[lost]
    file = (
        roots[lost] / target.source_documents[0].name
        if lost == "source_dir"
        else roots[lost] / (target.project_id + suffix)
    )
    file.unlink()
    monkeypatch.setattr(
        report, "evaluate_development_suite_v2",
        lambda *_: pytest.fail("incomplete executions cannot be scored as a suite"),
    )
    ledger = report.build_four_project_evidence_ledger(**roots)
    target_row = next(
        row for row in ledger["projects"] if row["project_id"] == target.project_id
    )
    assert target_row["first_failing_authority_stage"] == expected_stage
    assert ledger["independently_verified_execution_count"] == 3
    assert ledger["development_suite_result"] is None
    assert ledger["coverage_accuracy"] is None
    assert ledger["official_suite_result"] is None
    assert ledger["reason_codes"][0] == "four_project_signed_source_universe_not_complete"
    assert f"{target.project_id}:{expected_stage}" in ledger["reason_codes"]


def test_bad_signed_receipt_does_not_gain_complete_development_score(
    tmp_path, monkeypatch,
):
    roots, manifests = _four_source_verified_projects(tmp_path, monkeypatch)
    target = manifests[1]
    (roots["sealed_dir"] / (target.project_id + ".json")).write_text(
        '{"project_id":"bad","project_id":"tampered"}', encoding="utf-8",
    )
    monkeypatch.setattr(
        report, "evaluate_development_suite_v2",
        lambda *_: pytest.fail("invalid signed JSON cannot enter development scorer"),
    )
    ledger = report.build_four_project_evidence_ledger(**roots)
    failed = next(
        row for row in ledger["projects"] if row["project_id"] == target.project_id
    )
    assert failed["first_failing_authority_stage"] == "sealed_source_run_parse_or_signature"
    assert failed["publication_status"] == "CONFLICT"
    assert ledger["independently_verified_execution_count"] == 3
    assert ledger["development_suite_result"] is None
    assert ledger["official_suite_result"] is None


def test_four_original_pdfs_with_one_empty_v1_handoff_never_score_missing_production(
    tmp_path, monkeypatch,
):
    roots, manifests = _four_source_verified_projects(tmp_path, monkeypatch)
    invalid_project = manifests[2].project_id
    real_source_decoder = report.sealed_source_closed_run_from_dict

    def with_empty_source(value):
        if value["project_id"] == invalid_project:
            return SimpleNamespace(
                project_id=invalid_project,
                source_sha256s=value["source_sha256s"],
                quantities=(),
                to_dict=lambda: value,
            )
        return real_source_decoder(value)

    monkeypatch.setattr(
        report, "sealed_source_closed_run_from_dict", with_empty_source,
    )
    monkeypatch.setattr(
        report, "evaluate_development_suite_v2",
        lambda *_: pytest.fail("an empty signed V1 handoff is not a genuine source execution"),
    )
    monkeypatch.setattr(
        report, "evaluate_suite_v2",
        lambda *_a, **_k: pytest.fail("incomplete source may not publish official V2"),
    )

    result = report.build_four_project_evidence_ledger(**roots)
    entry = next(x for x in result["projects"] if x["project_id"] == invalid_project)
    assert entry["publication_status"] == "CONFLICT"
    assert entry["first_failing_authority_stage"] == "signed_source_quantity_universe_empty"
    assert result["independently_verified_execution_count"] == 3
    assert result["development_suite_result"] is None
    assert result["official_suite_result"] is None
    assert result["coverage_accuracy"] is None
    assert f"{invalid_project}:signed_source_quantity_universe_empty" in result["reason_codes"]


def test_duplicate_frozen_project_ids_cannot_reuse_one_signed_source_across_slots(
    tmp_path, monkeypatch,
):
    roots, manifests = _four_source_verified_projects(tmp_path, monkeypatch)
    manifests[-1].project_id = manifests[0].project_id
    with pytest.raises(ValueError, match="four distinct projects"):
        report.build_four_project_evidence_ledger(**roots)
