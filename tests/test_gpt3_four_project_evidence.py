"""The four-project reporting path must never convert missing source into zero."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import report_gpt3_four_project_evidence as module


def _dirs(tmp_path: Path) -> dict:
    return {
        "source_dir": tmp_path / "source",
        "sealed_dir": tmp_path / "sealed",
        "identity_map_dir": tmp_path / "identity",
        "customer_dir": tmp_path / "customer",
    }


def test_missing_original_sources_keep_all_120_items_unpublished(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unavailable source may not invoke frozen evaluator")
    monkeypatch.setattr(module, "evaluate_suite_v2", forbidden)
    result = module.build_four_project_evidence_ledger(**_dirs(tmp_path))
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["official_suite_result"] is None
    assert result["coverage_accuracy"] is None
    assert result["precision_adjusted_accuracy"] is None
    assert result["required_project_count"] == 4
    assert result["frozen_denominator"] == 120
    assert len(result["projects"]) == 4
    assert sorted(x["denominator"] for x in result["projects"]) == [6, 24, 27, 63]
    for project in result["projects"]:
        assert project["publication_status"] == "UNAVAILABLE"
        assert project["source_sha_verified"] is False
        assert project["customer_bijection_verified"] is False
        assert project["reconciliation_complete"] is False
        assert project["exact_project_report"] is None


def test_present_but_corrupt_original_bytes_report_conflict_not_zero(tmp_path):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    project_root = dirs["source_dir"] / manifest.project_id
    project_root.mkdir(parents=True)
    for doc in manifest.source_documents:
        (project_root / doc.name).write_bytes(b"%PDF-fake-not-original")
    result = module.build_four_project_evidence_ledger(**dirs)
    observed = next(x for x in result["projects"] if x["project_id"] == manifest.project_id)
    assert observed["publication_status"] == "CONFLICT"
    assert observed["source_sha_verified"] is False
    assert observed["reconciliation_complete"] is False
    assert observed["exact_project_report"] is None
    assert any(
        reason.startswith("original_source_size_mismatch:")
        or reason.startswith("original_source_sha_mismatch:")
        for reason in observed["reason_codes"]
    )
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["coverage_accuracy"] is None


def test_verified_source_without_signed_run_stays_unavailable(tmp_path, monkeypatch):
    dirs = _dirs(tmp_path)
    manifest = module.load_suite_manifests(module.FROZEN_ROOT)[0]
    project_root = dirs["source_dir"] / manifest.project_id
    project_root.mkdir(parents=True)
    for doc in manifest.source_documents:
        (project_root / doc.name).write_bytes(b"%PDF-test-fixture")
    # The source gate is simulated ONLY to exercise the downstream absence.
    # No real SHA proof or quantity is created from these test-only bytes.
    monkeypatch.setattr(
        module, "_original_sha_gate",
        lambda raw, paths: (True, [], [d.sha256 for d in manifest.source_documents]),
    )
    result = module.build_four_project_evidence_ledger(**dirs)
    observed = next(x for x in result["projects"] if x["project_id"] == manifest.project_id)
    assert observed["source_sha_verified"] is True
    assert observed["publication_status"] == "UNAVAILABLE"
    assert "signed_production_evidence_unavailable" in observed["reason_codes"]
    assert observed["customer_bijection_verified"] is False
    assert observed["exact_project_report"] is None
    assert result["official_suite_result"] is None


def test_malformed_customer_rows_fail_closed(tmp_path):
    path = tmp_path / "customer.json"
    path.write_text('[{"quantity_id": "q1"}, {"quantity_id": ""}]', encoding="utf-8")
    with pytest.raises(ValueError, match="canonical quantity identity"):
        module._json_customer_rows(path)
    path.write_text('{"quantity_id": "q1"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        module._json_customer_rows(path)


def test_malformed_signed_evidence_fails_closed(tmp_path):
    path = tmp_path / "signed.json"
    path.write_text('[]', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        module._json_object(path)
