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


def test_3laurel_wet_area_floor_truth_is_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")

    assert manifest.status == "INCOMPLETE"

    expected_refs = {
        "3laurel:surface:floor:bathroom",
        "3laurel:surface:floor:main_wc",
        "3laurel:surface:floor:laundry",
        "3laurel:surface:floor:gf_ensuite_laundry",
    }
    items = [
        item for item in manifest.verified_items
        if item.expected_object_refs
        and item.expected_object_refs[0] in expected_refs
    ]
    assert len(items) == 4
    assert all(item.trade_category == "tiling" for item in items)
    assert all(item.unit == "m2" for item in items)
    assert all(item.denominator_eligible for item in items)
    assert all(len(item.expected_object_refs) == 1 for item in items)
    assert sum(item.expected_quantity for item in items) == pytest.approx(18.5649)

    universe = _json(project / "object_universe.json")
    floors = universe["wet_area_floor_surfaces"]
    assert len(floors) == 4
    assert {row["object_ref"] for row in floors} == expected_refs
    assert universe["wet_area_floor_surface_universe_complete"] is True

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_3laurel_wet_area_floor_reconciliation_preserves_overlap_rule():
    project = ROOT / PROJECT_ID
    ref = _json(project / "reference_takeoff.json")
    closure = ref["wet_area_floor_reconciliation"]

    assert closure["closure_check_id"] == "3laurel:closure:wet_area_atomic_floor_surfaces"
    assert closure["object_count"] == 4
    assert closure["component_sum_m2"] == pytest.approx(18.5649)
    assert closure["source_closed"] is True
    assert closure["aggregate_overlap"]["main_living_refs"] == [
        "3laurel:surface:floor:bathroom",
        "3laurel:surface:floor:main_wc",
        "3laurel:surface:floor:laundry",
    ]
    assert closure["aggregate_overlap"]["gf_living_refs"] == [
        "3laurel:surface:floor:gf_ensuite_laundry"
    ]
    assert "non-denominator" in closure["aggregate_overlap"]["rule"]


def test_3laurel_wet_area_floors_do_not_complete_whole_project():
    project = ROOT / PROJECT_ID
    report = _json(project / "verification_report.json")
    summary = report["wet_area_floor_closure_summary"]

    assert summary["verified_floor_count"] == 4
    assert summary["verified_area_m2"] == pytest.approx(18.5649)
    assert summary["source_closed"] is True
    assert summary["overlapping_living_aggregate_regions_denominator_eligible"] is False

    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["wet-area tiled floor surfaces source-closed"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
