from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_FROZEN_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "frozen_holdout"
sys.path.insert(0, str(_FROZEN_ROOT))

from full_plan_v2.manifest_io import load_project_manifest

ROOT = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "frozen_holdout"
    / "full_plan_v2"
    / "projects"
)
PROJECT_ID = "au_qld_lot16_power"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_lot16_ensuite_wir_floor_truth_is_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")
    universe = _json(project / "object_universe.json")

    assert manifest.status == "INCOMPLETE"

    floors = universe["ensuite_wir_floor_surfaces"]
    expected_refs = {row["object_ref"] for row in floors}
    items = [
        item
        for item in manifest.verified_items
        if item.expected_object_refs
        and item.expected_object_refs[0] in expected_refs
    ]

    assert len(floors) == 2
    assert len(items) == 2
    by_ref = {item.expected_object_refs[0]: item for item in items}
    assert by_ref["lot16:surface:floor:ensuite"].trade_category == "tiling"
    assert by_ref["lot16:surface:floor:wir"].trade_category == "flooring"
    assert all(item.unit == "m2" for item in items)
    assert all(item.denominator_eligible for item in items)
    assert all(len(item.expected_object_refs) == 1 for item in items)
    assert sum(item.expected_quantity for item in items) == pytest.approx(10.1728)

    assert universe["promoted_atomic_floor_subset_source_closed"] is True
    assert universe["project_floor_universe_complete"] is False

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_lot16_ensuite_wir_floor_reconciliation_preserves_overlap_rule():
    project = ROOT / PROJECT_ID
    ref = _json(project / "reference_takeoff.json")
    closure = ref["ensuite_wir_floor_reconciliation"]

    assert closure["closure_check_id"] == "lot16:closure:ensuite_wir_floor_surfaces"
    assert closure["object_count"] == 2
    assert closure["component_sum_m2"] == pytest.approx(10.1728)
    assert closure["source_closed"] is True
    assert closure["aggregate_overlap"]["aggregate_ref"] == (
        "lot16:surface:floor:residence_composite_region"
    )
    assert "non-denominator" in closure["aggregate_overlap"]["rule"]

    aggregate_ref = closure["aggregate_overlap"]["aggregate_ref"]
    manifest = load_project_manifest(project / "source_manifest.json")
    assert all(aggregate_ref not in item.expected_object_refs for item in manifest.verified_items)


def test_lot16_ensuite_wir_floor_subset_does_not_complete_project():
    project = ROOT / PROJECT_ID
    report = _json(project / "verification_report.json")
    summary = report["ensuite_wir_floor_closure_summary"]

    assert summary["verified_floor_count"] == 2
    assert summary["verified_area_m2"] == pytest.approx(10.1728)
    assert summary["source_closed"] is True
    assert summary["overlapping_residence_composite_denominator_eligible"] is False
    assert summary["project_floor_universe_complete"] is False

    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["Lot16 ensuite and WIR atomic floor subset source-closed"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
