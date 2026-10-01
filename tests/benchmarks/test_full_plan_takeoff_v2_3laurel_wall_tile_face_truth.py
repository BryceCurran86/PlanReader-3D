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


def test_3laurel_wall_tile_face_truth_is_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")

    assert manifest.status == "INCOMPLETE"

    expected_refs = {
        "3laurel:surface:wall_tile:laundry_D_skirting",
        "3laurel:surface:wall_tile:bathroom_C_shower_net",
        "3laurel:surface:wall_tile:ensuite_B_shower_return_net",
        "3laurel:surface:wall_tile:ensuite_D_shower_return_net",
        "3laurel:surface:wall_tile:gf_ensuite_B_shower_return_net",
        "3laurel:surface:wall_tile:gf_ensuite_D_shower_return_net",
        "3laurel:surface:wall_tile:ensuite_rear_flat_after_niche",
        "3laurel:surface:wall_tile:gf_ensuite_rear_flat_after_niche",
    }
    items = [
        item
        for item in manifest.verified_items
        if item.expected_object_refs
        and item.expected_object_refs[0] in expected_refs
    ]

    assert len(items) == 8
    assert all(item.trade_category == "tiling" for item in items)
    assert all(item.unit == "m2" for item in items)
    assert all(item.denominator_eligible for item in items)
    assert all(len(item.expected_object_refs) == 1 for item in items)
    assert all(item.source_document_refs == ("reference_takeoff.json",) for item in items)
    assert sum(item.expected_quantity for item in items) == pytest.approx(21.3002)

    universe = _json(project / "object_universe.json")
    faces = universe["wall_tile_finish_surfaces"]
    assert len(faces) == 8
    assert {row["object_ref"] for row in faces} == expected_refs
    assert universe["wall_tile_face_subset_source_closed"] is True
    assert universe["project_wet_area_tile_universe_complete"] is False

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_3laurel_wall_tile_reconciliation_keeps_niche_returns_unresolved():
    project = ROOT / PROJECT_ID
    ref = _json(project / "reference_takeoff.json")
    closure = ref["wall_tile_face_subset_reconciliation"]

    assert closure["object_count"] == 8
    assert closure["component_sum_m2"] == pytest.approx(21.3002)
    assert closure["source_closed_for_promoted_faces"] is True
    assert closure["complete_for_project_wet_area_tile_universe"] is False
    assert closure["niche_return_depths_resolved"] is False

    assert closure["closure_check_ids"] == [
        "3laurel:closure:laundry_D_tile_skirting",
        "3laurel:closure:bathroom_C_shower_tile_face",
        "3laurel:closure:niche_free_ensuite_shower_returns",
        "3laurel:closure:ensuite_rear_flat_faces_after_niche_deductions",
    ]

    unresolved = _json(project / "unresolved_items.json")
    by_family = {row["family"]: row for row in unresolved["items"]}
    assert by_family["wet_area_tile_niches_and_returns"]["status"] == "UNRESOLVED"
    assert by_family["remaining_wet_area_tile_scope"]["status"] == "UNRESOLVED"


def test_3laurel_wall_tile_faces_do_not_complete_whole_project():
    project = ROOT / PROJECT_ID
    report = _json(project / "verification_report.json")
    summary = report["wall_tile_face_closure_summary"]

    assert summary["verified_face_count"] == 8
    assert summary["verified_area_m2"] == pytest.approx(21.3002)
    assert summary["source_closed_for_promoted_faces"] is True
    assert summary["complete_for_project_wet_area_tile_universe"] is False
    assert summary["niche_returns_resolved"] is False

    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["explicit wet-area wall-tile face subset source-closed"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
