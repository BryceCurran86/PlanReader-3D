from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

_REPORT_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "frozen_holdout"
    / "full_plan_v2"
    / "run_exact_project_reconciliation.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "full_plan_v2_exact_project_reconciliation",
    _REPORT_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
build_exact_project_report = _MODULE.build_exact_project_report

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


SHA = "a" * 64


def _write_manifest(path: Path) -> None:
    payload = {
        "schema_version": "2.0",
        "project_id": "p1",
        "status": "INCOMPLETE",
        "source_package_complete": True,
        "source_documents": [{
            "name": "p1.pdf",
            "role": "architectural_drawings",
            "sha256": SHA,
            "size_bytes": 100,
            "page_count": 1,
        }],
        "reference_takeoff_documents": [{
            "name": "p1-reference.json",
            "role": "independent_verified_reference_takeoff",
            "sha256": SHA,
            "size_bytes": 100,
            "page_count": 1,
        }],
        "verified_takeoff_items": [{
            "item_id": "p1-floor",
            "description": "Verified floor area",
            "trade_category": "tiling",
            "unit": "m2",
            "expected_quantity": 10.0,
            "tolerance_policy_id": "relative-tolerance-v1",
            "tolerance_fraction": 0.05,
            "expected_object_refs": ["p1:floor"],
            "source_document_refs": ["p1-reference.json"],
            "source_location_refs": ["sheet:A100:room"],
            "denominator_eligible": True,
            "verification_status": "VERIFIED",
        }],
        "reason_codes": ["truth_expansion_in_progress"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sealed_run(path: Path) -> None:
    quantity = QuantityEvidence(
        quantity_id="qty-1",
        family="room_area",
        semantic_key="room_area:floor-1",
        value=10.0,
        unit="m2",
        input_entity_ids=("canonical-floor-1",),
        formula="figured",
        formula_version="1",
        evidence_ids=("ev-1",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        metadata={
            "project_id": "p1",
            "document_id": "doc-1",
            "source_sha256": SHA,
            "revision_id": "rev-1",
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id="p1",
        document_id="doc-1",
        source_sha256=SHA,
        source_page="p1",
        viewport_id="vp-1",
        revision_id="rev-1",
        current_revision_id="rev-1",
        evidence_ids=("ev-1",),
        canonical_entity_ids=("canonical-floor-1",),
    )
    run = seal_source_closed_run(
        [quantity],
        project_id="p1",
        traces_by_quantity_id={"qty-1": trace},
    )
    path.write_text(run.to_json(), encoding="utf-8")


def _identity_map(path: Path) -> None:
    payload = {
        "schema_version": "1.0.0",
        "project_id": "p1",
        "source_sha256s": [SHA],
        "bindings": [{
            "benchmark_item_id": "p1-floor",
            "production_object_identity_refs": ["canonical-floor-1"],
            "production_family": "room_area",
        }],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_exact_project_report_emits_required_reconciliation_fields(tmp_path) -> None:
    manifest = tmp_path / "source_manifest.json"
    sealed = tmp_path / "sealed.json"
    identity = tmp_path / "identity.json"
    _write_manifest(manifest)
    _sealed_run(sealed)
    _identity_map(identity)

    report = build_exact_project_report(
        manifest_path=manifest,
        sealed_run_path=sealed,
        identity_map_path=identity,
    )

    assert report["project_id"] == "p1"
    assert report["source_sha_verified"] is True
    assert report["reconciliation_complete"] is True
    assert report["denominator"] == 1
    assert report["matched_within_tolerance"] == 1
    assert report["matched_outside_tolerance"] == 0
    assert report["missed"] == 0
    assert report["partial"] == 0
    assert report["unresolved"] == 0
    assert report["unsupported_extra"] == 0
    assert report["coverage_accuracy"] == pytest.approx(1.0)
    assert report["precision_adjusted_accuracy"] == pytest.approx(1.0)
    assert report["lineage_conflicts"] == 0
    assert len(report["produced_items"]) == 1
    assert report["produced_items"][0]["quantity_id"] == "qty-1"


def test_exact_project_report_rejects_tampered_sealed_handoff(tmp_path) -> None:
    manifest = tmp_path / "source_manifest.json"
    sealed = tmp_path / "sealed.json"
    identity = tmp_path / "identity.json"
    _write_manifest(manifest)
    _sealed_run(sealed)
    _identity_map(identity)

    payload = json.loads(sealed.read_text(encoding="utf-8"))
    payload["quantities"][0]["value"] = 999.0
    sealed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SourceClosedRunConflictError, match="fingerprint mismatch"):
        build_exact_project_report(
            manifest_path=manifest,
            sealed_run_path=sealed,
            identity_map_path=identity,
        )



def test_exact_project_report_cli_writes_requested_json(tmp_path) -> None:
    manifest = tmp_path / "source_manifest.json"
    sealed = tmp_path / "sealed.json"
    identity = tmp_path / "identity.json"
    output = tmp_path / "report.json"
    _write_manifest(manifest)
    _sealed_run(sealed)
    _identity_map(identity)

    assert _MODULE.main([
        "--manifest", str(manifest),
        "--sealed-run", str(sealed),
        "--identity-map", str(identity),
        "--output", str(output),
    ]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source_sha_verified"] is True
    assert payload["reconciliation_complete"] is True
    assert payload["denominator"] == 1
    assert payload["matched_within_tolerance"] == 1
    assert payload["coverage_accuracy"] == pytest.approx(1.0)
    assert payload["precision_adjusted_accuracy"] == pytest.approx(1.0)
    assert payload["produced_items"][0]["quantity_id"] == "qty-1"
