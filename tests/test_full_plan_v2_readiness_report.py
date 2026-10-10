"""GPT3 readiness diagnostics must never turn absent production into a score."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.report_full_plan_v2_readiness import diagnostic_report, _source_sha_proof

ROOT = Path("benchmarks/frozen_holdout/full_plan_v2")


def test_missing_production_is_explicitly_unpublished(tmp_path: Path) -> None:
    report = diagnostic_report(ROOT, tmp_path)
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["score_claim"] is False
    assert len(report["projects"]) == 4
    for project in report["projects"]:
        assert project["produced_file_present"] is False
        assert project["produced_count"] is None
        assert project["coverage_accuracy"] is None
        assert project["precision_adjusted_accuracy"] is None
        assert "production_items_missing" in project["blockers"]
        assert project["source_sha_verified"] is False


def test_duplicate_production_identifiers_cannot_be_hidden(tmp_path: Path) -> None:
    target = tmp_path / "au_qld_maryborough_service_station"
    target.mkdir()
    item = {
        "quantity_id": "duplicate-q",
        "trade_category": "surface",
        "value": 4.0,
        "unit": "m2",
        "object_refs": ["source-object"],
        "lineage_ok": True,
        "abstained": False,
    }
    (target / "produced_items.json").write_text(
        json.dumps([item, item]), encoding="utf-8"
    )
    report = diagnostic_report(ROOT, tmp_path)
    project = next(
        entry for entry in report["projects"]
        if entry["project_id"] == "au_qld_maryborough_service_station"
    )
    assert project["produced_count"] == 2
    assert project["duplicate_quantity_ids"] == ["duplicate-q"]
    assert "duplicate_produced_quantity_ids" in project["blockers"]
    assert project["coverage_accuracy"] is None


def test_empty_production_is_not_a_successful_reconciliation(tmp_path: Path) -> None:
    target = tmp_path / "au_qld_lot16_power"
    target.mkdir()
    (target / "produced_items.json").write_text("[]", encoding="utf-8")
    project = next(
        p for p in diagnostic_report(ROOT, tmp_path)["projects"]
        if p["project_id"] == "au_qld_lot16_power"
    )
    assert project["produced_file_present"] is True
    assert "empty_produced_items_unverified" in project["blockers"]
    assert project["reconciliation_complete"] is False


def test_source_hash_checks_actual_bytes_not_just_filename(tmp_path: Path) -> None:
    folder = tmp_path / "project-x"
    folder.mkdir()
    source = folder / "evidence.pdf"
    source.write_bytes(b"true source")
    manifest = {"source_documents": [{
        "name": "evidence.pdf",
        "size_bytes": len(b"true source"),
        "sha256": hashlib.sha256(b"true source").hexdigest(),
    }]}
    assert _source_sha_proof(manifest, tmp_path, "project-x") == (True, [])
    source.write_bytes(b"fake source")
    verified, reasons = _source_sha_proof(manifest, tmp_path, "project-x")
    assert verified is False
    assert "source_file_sha_mismatch:evidence.pdf" in reasons
    source.unlink()
    verified, reasons = _source_sha_proof(manifest, tmp_path, "project-x")
    assert verified is False
    assert "source_file_missing:evidence.pdf" in reasons


def test_sealed_run_absent_is_explicit_and_unpublished(tmp_path: Path) -> None:
    project = next(p for p in diagnostic_report(ROOT, tmp_path, sealed_root=tmp_path)["projects"]
                   if p["project_id"] == "au_qld_lot16_power")
    assert project["sealed_run_verified"] is False
    assert project["sealed_quantity_count"] is None
    assert "sealed_run_missing" in project["blockers"]
    assert project["coverage_accuracy"] is None


def test_tampered_sealed_run_cannot_claim_verified(tmp_path: Path) -> None:
    from scripts.report_full_plan_v2_readiness import _sealed_run_proof
    folder = tmp_path / "project-x"
    folder.mkdir()
    (folder / "sealed_run.json").write_text('{"project_id":"project-x","quantities":[]}', encoding="utf-8")
    verified, count, blockers = _sealed_run_proof(tmp_path, "project-x", set())
    assert verified is False
    assert count is None
    assert blockers == ["sealed_run_integrity_invalid"]


def test_missing_produced_quantity_id_blocks_readiness_without_crashing(tmp_path: Path) -> None:
    target = tmp_path / "au_qld_lot16_power"
    target.mkdir()
    # A malformed row still belongs in the production audit; it cannot
    # disappear or invent a benchmark identity just because the ID is absent.
    (target / "produced_items.json").write_text(
        json.dumps([{
            "trade_category": "opening", "value": 1.8, "unit": "m2",
            "object_refs": ["physical-opening-1"],
            "lineage_ok": True, "abstained": False,
        }]), encoding="utf-8",
    )
    report = diagnostic_report(ROOT, tmp_path)
    project = next(x for x in report["projects"] if x["project_id"] == "au_qld_lot16_power")
    assert project["produced_file_present"] is True
    assert project["produced_count"] == 1
    assert "produced_quantity_id_missing_or_invalid" in project["blockers"]
    assert project["reconciliation_complete"] is False
    assert project["coverage_accuracy"] is None
    assert project["precision_adjusted_accuracy"] is None
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["score_claim"] is False


def test_invalid_produced_quantity_id_types_do_not_become_fake_id_strings(tmp_path: Path) -> None:
    target = tmp_path / "au_qld_maryborough_service_station"
    target.mkdir()
    def item(quantity_id):
        return {
            "quantity_id": quantity_id, "trade_category": "surface",
            "value": 4.0, "unit": "m2", "object_refs": ["physical-floor-1"],
            "lineage_ok": True, "abstained": False,
        }
    (target / "produced_items.json").write_text(
        json.dumps([item(None), item(1234), item(" "), item("real-quantity-id")]),
        encoding="utf-8",
    )
    project = next(
        p for p in diagnostic_report(ROOT, tmp_path)["projects"]
        if p["project_id"] == "au_qld_maryborough_service_station"
    )
    assert project["produced_count"] == 4
    assert project["duplicate_quantity_ids"] == []
    assert "produced_quantity_id_missing_or_invalid" in project["blockers"]
    assert "None" not in project["duplicate_quantity_ids"]
    assert project["reconciliation_complete"] is False
    assert project["coverage_accuracy"] is None
