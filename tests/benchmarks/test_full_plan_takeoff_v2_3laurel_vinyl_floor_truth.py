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
PROJECT_ID = "au_qld_3laurel"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_3laurel_vinyl_floor_truth_is_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")

    assert manifest.status == "INCOMPLETE"

    expected_refs = {
        "3laurel:surface:floor:media",
        "3laurel:surface:floor:bed2",
        "3laurel:surface:floor:bed3",
    }
    items = [
        item for item in manifest.verified_items
        if item.expected_object_refs
        and item.expected_object_refs[0] in expected_refs
    ]
    assert len(items) == 3
    assert all(item.trade_category == "flooring" for item in items)
    assert all(item.unit == "m2" for item in items)
    assert all(item.denominator_eligible for item in items)
    assert all(len(item.expected_object_refs) == 1 for item in items)
    assert sum(item.expected_quantity for item in items) == pytest.approx(38.346)

    universe = _json(project / "object_universe.json")
    floors = universe["vinyl_floor_surfaces"]
    assert len(floors) == 3
    assert {row["object_ref"] for row in floors} == expected_refs
    assert universe["vinyl_floor_surface_universe_complete"] is True

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_3laurel_vinyl_floor_reconciliation_preserves_overlap_rule():
    project = ROOT / PROJECT_ID
    ref = _json(project / "reference_takeoff.json")
    closure = ref["vinyl_floor_reconciliation"]

    assert closure["closure_check_ids"] == [
        "3laurel:closure:media_floor_and_gross_wall_faces",
        "3laurel:closure:bed2_bed3_floor_surfaces",
    ]
    assert closure["object_count"] == 3
    assert closure["component_sum_m2"] == pytest.approx(38.346)
    assert closure["source_closed"] is True
    assert closure["finish"] == "vinyl"
    assert closure["aggregate_overlap"]["aggregate_ref"] == (
        "3laurel:surface:floor:main_living_composite_region"
    )
    assert "non-denominator" in closure["aggregate_overlap"]["rule"]


def test_3laurel_vinyl_floors_do_not_complete_whole_project():
    project = ROOT / PROJECT_ID
    report = _json(project / "verification_report.json")
    summary = report["vinyl_floor_closure_summary"]

    assert summary["verified_floor_count"] == 3
    assert summary["verified_area_m2"] == pytest.approx(38.346)
    assert summary["source_closed"] is True
    assert summary["overlapping_main_living_aggregate_denominator_eligible"] is False

    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["source-dimensioned vinyl floor surfaces source-closed"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
