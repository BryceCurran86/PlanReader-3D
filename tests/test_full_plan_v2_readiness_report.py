"""GPT3 readiness diagnostics must never turn absent production into a score."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.report_full_plan_v2_readiness import diagnostic_report

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
