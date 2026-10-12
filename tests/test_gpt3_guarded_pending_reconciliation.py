from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.run_gpt3_guarded_pending_reconciliation as module


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "docs/engineering/lot16_original_identity_reconciliation_20261012"
)
MANIFEST = (
    ROOT
    / "benchmarks/frozen_holdout/full_plan_v2/projects"
    / "au_qld_lot16_power/source_manifest.json"
)
SOURCE_SHA = (
    "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
)
ITEM = "lot16-1218-sgw-01-area"
OBJECT_REF = "lot16:opening:p3:1218_sgw:01"
PHYSICAL = "physical_opening_existence_c4d87543028146e1cff0b5e2ca480c55"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _pending():
    return {
        "project_id": "au_qld_lot16_power",
        "source_sha256": SOURCE_SHA,
        "status": "IDENTITY_READY_QUANTITY_UNSEALED",
        "physical_opening_id": PHYSICAL,
        "benchmark_item_id": ITEM,
        "benchmark_object_ref": OBJECT_REF,
    }


def _partial_map():
    active = _json(EVIDENCE / "identity_map.json")
    active["bindings"] = [
        row
        for row in active["bindings"]
        if row["benchmark_item_id"] != ITEM
    ]
    assert len(active["bindings"]) == 6
    return active


def _run(*, pending=None, active=None):
    return module.build_guarded_exact_report(
        pending_ledger=_pending() if pending is None else pending,
        sealed_run_payload=_json(EVIDENCE / "source_sealed_run.json"),
        customer_rows=_json(EVIDENCE / "verified_customer_rows.json"),
        active_identity_map_payload=(
            _partial_map() if active is None else active
        ),
        source_manifest=_json(MANIFEST),
        manifest_path=MANIFEST,
    )


def test_real_seven_row_evidence_scores_only_after_guarded_activation():
    candidate, activation, report = _run()

    assert activation["activated_count"] == 1
    assert activation["benchmark_score_granted"] is False
    assert activation["benchmark_accuracy"] is None
    assert activation["evaluator_invoked"] is False

    assert len(candidate["bindings"]) == 7
    activated = next(
        row for row in candidate["bindings"]
        if row["benchmark_item_id"] == ITEM
    )
    assert activated["production_object_identity_refs"] == [PHYSICAL]
    assert activated["production_family"] == "opening_area"

    assert report["source_sha_verified"] is True
    assert report["reconciliation_complete"] is True
    assert report["denominator"] == 27
    assert report["matched_within_tolerance"] == 7
    assert report["matched_outside_tolerance"] == 0
    assert report["missed"] == 20
    assert report["partial"] == 0
    assert report["unresolved"] == 0
    assert report["unsupported_extra"] == 0
    assert report["lineage_conflicts"] == 0
    assert report["coverage_accuracy"] == 7 / 27
    assert report["precision_adjusted_accuracy"] == 7 / 27
    assert len(report["produced_items"]) == 7


def test_unsealed_pending_identity_never_reaches_exact_evaluator(monkeypatch):
    called = False

    class _Exact:
        @staticmethod
        def build_exact_project_report(**kwargs):
            nonlocal called
            called = True
            raise AssertionError("evaluator must not run")

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Exact)
    pending = {
        **_pending(),
        "physical_opening_id": "physical_opening_existence_not_sealed",
    }
    with pytest.raises(
        ValueError,
        match="no pre-certified identity is newly sealed",
    ):
        _run(pending=pending)
    assert called is False


def test_duplicate_active_identity_never_reaches_exact_evaluator(monkeypatch):
    called = False

    class _Exact:
        @staticmethod
        def build_exact_project_report(**kwargs):
            nonlocal called
            called = True
            raise AssertionError("evaluator must not run")

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Exact)
    with pytest.raises(ValueError, match="already active"):
        _run(active=_json(EVIDENCE / "identity_map.json"))
    assert called is False


def test_guarded_report_rejects_activation_and_report_run_mismatch(monkeypatch):
    real = module._exact_report_module()

    class _Changed:
        @staticmethod
        def build_exact_project_report(**kwargs):
            report = real.build_exact_project_report(**kwargs)
            return {**report, "sealed_run_id": "different-run"}

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Changed)
    with pytest.raises(ValueError, match="sealed run mismatch"):
        _run()


def test_guarded_report_rejects_activation_and_report_fingerprint_mismatch(
    monkeypatch,
):
    real = module._exact_report_module()

    class _Changed:
        @staticmethod
        def build_exact_project_report(**kwargs):
            report = real.build_exact_project_report(**kwargs)
            return {
                **report,
                "sealed_run_fingerprint": "0" * 64,
            }

    monkeypatch.setattr(module, "_exact_report_module", lambda: _Changed)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        _run()
