from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCOREBOARD_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "frozen_holdout"
    / "full_plan_v2"
    / "development_scoreboard.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "full_plan_v2_development_scoreboard",
    _SCOREBOARD_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

build_development_failure_ledger_v2 = _MODULE.build_development_failure_ledger_v2
evaluate_development_suite_v2 = _MODULE.evaluate_development_suite_v2
ProducedTakeoffItemV2 = _MODULE.ProducedTakeoffItemV2
ProjectBenchmarkManifestV2 = _MODULE.ProjectBenchmarkManifestV2
SourceDocumentV2 = _MODULE._module.SourceDocumentV2
VerifiedTakeoffItemV2 = _MODULE._module.VerifiedTakeoffItemV2


SHA = "b" * 64


def _doc(name: str, role: str) -> SourceDocumentV2:
    return SourceDocumentV2(
        name=name,
        role=role,
        sha256=SHA,
        size_bytes=100,
        page_count=1,
    )


def _manifest(project_id: str) -> ProjectBenchmarkManifestV2:
    reference_name = f"{project_id}-reference.json"
    item = VerifiedTakeoffItemV2(
        item_id=f"{project_id}-floor",
        project_id=project_id,
        description="Verified floor area",
        trade_category="tiling",
        unit="m2",
        expected_quantity=10.0,
        tolerance_policy_id="relative-tolerance-v1",
        tolerance_fraction=0.05,
        expected_object_refs=(f"{project_id}:floor",),
        source_document_refs=(reference_name,),
        source_location_refs=("sheet:A100:room",),
        denominator_eligible=True,
    )
    return ProjectBenchmarkManifestV2(
        project_id=project_id,
        status="INCOMPLETE",
        source_package_complete=True,
        source_documents=(_doc(f"{project_id}.pdf", "architectural_drawings"),),
        reference_takeoff_documents=(
            _doc(reference_name, "independent_verified_reference_takeoff"),
        ),
        verified_items=(item,),
        reason_codes=("truth_expansion_in_progress",),
    )


def _produced(
    project_id: str,
    *,
    quantity_id: str | None = None,
    refs: tuple[str, ...] | None = None,
    value: float = 10.0,
    lineage_ok: bool = True,
) -> ProducedTakeoffItemV2:
    return ProducedTakeoffItemV2(
        quantity_id=quantity_id or f"{project_id}-q",
        trade_category="tiling",
        value=value,
        unit="m2",
        object_refs=refs or (f"{project_id}:floor",),
        lineage_ok=lineage_ok,
    )


def test_incomplete_project_verified_truth_is_development_scorable():
    manifest = _manifest("p1")
    result = evaluate_development_suite_v2(
        (manifest,),
        {"p1": (_produced("p1"),)},
    )
    assert result.status == "COMPLETE_CURRENT_TRUTH_SET"
    assert result.source_closed_truth_items == 1
    assert result.development_accuracy == pytest.approx(1.0)
    assert result.precision_adjusted_accuracy == pytest.approx(1.0)


def test_partial_execution_never_becomes_headline_accuracy():
    manifests = tuple(_manifest(f"p{i}") for i in range(1, 5))
    result = evaluate_development_suite_v2(
        manifests,
        {
            "p1": (_produced("p1"),),
            "p2": (_produced("p2"),),
        },
    )
    assert result.status == "PARTIAL_OR_BLOCKED"
    assert result.executed_projects == 2
    assert result.source_closed_truth_items == 4
    assert result.executed_denominator == 2
    assert result.execution_coverage == pytest.approx(0.5)
    assert result.observed_accuracy == pytest.approx(1.0)
    assert result.development_accuracy is None
    assert result.precision_adjusted_accuracy is None
    assert "p3:production_output_missing" in result.reason_codes
    assert "p4:production_output_missing" in result.reason_codes


def test_complete_current_truth_set_produces_development_headline():
    manifests = tuple(_manifest(f"p{i}") for i in range(1, 5))
    produced = {
        f"p{i}": (_produced(f"p{i}"),)
        for i in range(1, 5)
    }
    result = evaluate_development_suite_v2(manifests, produced)
    assert result.execution_coverage == pytest.approx(1.0)
    assert result.development_accuracy == pytest.approx(1.0)


def test_unsupported_extra_counts_as_hallucination_and_penalizes_precision():
    manifests = tuple(_manifest(f"p{i}") for i in range(1, 5))
    produced = {
        f"p{i}": (_produced(f"p{i}"),)
        for i in range(1, 5)
    }
    produced["p1"] = produced["p1"] + (
        _produced(
            "p1",
            quantity_id="unsupported-extra",
            refs=("p1:invented-floor",),
            value=5.0,
        ),
    )
    result = evaluate_development_suite_v2(manifests, produced)
    assert result.development_accuracy == pytest.approx(1.0)
    assert result.hallucinations == 1
    assert result.precision_adjusted_accuracy == pytest.approx(4 / 5)


def test_lineage_conflict_blocks_headline():
    manifests = tuple(_manifest(f"p{i}") for i in range(1, 5))
    produced = {
        f"p{i}": (_produced(f"p{i}", lineage_ok=(i != 3)),)
        for i in range(1, 5)
    }
    result = evaluate_development_suite_v2(manifests, produced)
    assert result.lineage_conflicts == 1
    assert result.development_accuracy is None
    assert "lineage_conflict" in result.reason_codes


def test_failure_ledger_reports_exact_item_failures_without_faking_missing_execution():
    manifests = (_manifest("p1"), _manifest("p2"))
    produced = {
        "p1": (
            _produced("p1", value=12.0),
            _produced(
                "p1",
                quantity_id="unsupported-extra",
                refs=("p1:invented-floor",),
                value=5.0,
            ),
        ),
    }

    ledger = build_development_failure_ledger_v2(manifests, produced)

    assert ledger.missing_execution_project_ids == ("p2",)
    assert len(ledger.failure_items) == 1
    failure = ledger.failure_items[0]
    assert failure.project_id == "p1"
    assert failure.item_id == "p1-floor"
    assert failure.state == "MATCHED_OUTSIDE_TOLERANCE"
    assert failure.produced_quantity_id == "p1-q"
    assert failure.error_fraction == pytest.approx(0.2)
    assert failure.expected_object_refs == ("p1:floor",)
    assert failure.matched_object_refs == ("p1:floor",)

    assert len(ledger.unsupported_outputs) == 1
    unsupported = ledger.unsupported_outputs[0]
    assert unsupported.project_id == "p1"
    assert unsupported.quantity_id == "unsupported-extra"
    assert unsupported.object_refs == ("p1:invented-floor",)

    # A project that was not executed is not falsely classified as a MISSED item.
    assert all(item.project_id != "p2" for item in ledger.failure_items)


def test_failure_ledger_omits_items_already_within_tolerance():
    manifest = _manifest("p1")
    ledger = build_development_failure_ledger_v2(
        (manifest,),
        {"p1": (_produced("p1"),)},
    )
    assert ledger.failure_items == ()
    assert ledger.unsupported_outputs == ()
    assert ledger.missing_execution_project_ids == ()


def test_active_v2_truth_inventory_has_at_least_120_source_closed_items():
    root = _SCOREBOARD_PATH.parent
    suite = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    denominator = 0
    for project_id in suite["projects"]:
        manifest = json.loads(
            (root / "projects" / project_id / "source_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        denominator += sum(
            bool(item.get("denominator_eligible", True))
            for item in manifest["verified_takeoff_items"]
        )
    assert len(suite["projects"]) == 4
    assert denominator >= 120
