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


def test_lot16_internal_access_truth_is_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")
    universe = _json(project / "object_universe.json")

    assert manifest.status == "INCOMPLETE"

    openings = universe["internal_room_access_openings"]
    expected_refs = {row["object_ref"] for row in openings}
    items = [
        item
        for item in manifest.verified_items
        if item.expected_object_refs
        and item.expected_object_refs[0] in expected_refs
    ]

    assert len(openings) == 9
    assert len(items) == 9
    assert all(item.trade_category == "doors" for item in items)
    assert all(item.unit == "m2" for item in items)
    assert all(item.denominator_eligible for item in items)
    assert all(len(item.expected_object_refs) == 1 for item in items)
    assert all(item.source_document_refs == ("reference_takeoff.json",) for item in items)
    assert sum(item.expected_quantity for item in items) == pytest.approx(16.443)

    assert universe["internal_room_access_labelled_subset_complete"] is True
    assert universe["project_internal_opening_universe_complete"] is False

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_lot16_internal_access_reconciliation_is_exact_and_excludes_external_870s():
    project = ROOT / PROJECT_ID
    ref = _json(project / "reference_takeoff.json")
    closure = ref["internal_room_access_reconciliation"]

    assert closure["closure_check_id"] == "lot16:closure:internal_room_access_opening_census"
    assert closure["internal_opening_count"] == 9
    assert closure["internal_opening_area_m2"] == pytest.approx(16.443)
    assert closure["width_distribution_m"] == {"0.87": 9}
    assert closure["joinery_height_m"] == pytest.approx(2.1)
    assert closure["complete_for_explicit_internal_870_room_access_openings"] is True
    assert closure["complete_for_all_internal_wall_openings"] is False
    assert closure["excluded_external_870_labels"] == [
        "laundry_external_service_door",
        "garage_external_service_door",
    ]
    assert closure["residual_unresolved"] == [
        "robe_sliding_joinery_openings",
        "bifold_or_other_internal_joinery_openings",
        "unlabelled_open_archways",
    ]


def test_lot16_internal_access_subset_keeps_remaining_wall_opening_scope_fail_closed():
    project = ROOT / PROJECT_ID
    unresolved = _json(project / "unresolved_items.json")
    by_family = {row["family"]: row for row in unresolved["items"]}
    assert by_family["internal_wall_faces"]["status"] == "UNRESOLVED"

    report = _json(project / "verification_report.json")
    summary = report["internal_room_access_closure_summary"]
    assert summary["verified_opening_count"] == 9
    assert summary["verified_area_m2"] == pytest.approx(16.443)
    assert summary["width_distribution_m"] == {"0.87": 9}
    assert summary["joinery_height_m"] == pytest.approx(2.1)
    assert summary["complete_for_explicit_internal_870_room_access_openings"] is True
    assert summary["complete_for_all_internal_wall_openings"] is False

    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["labelled internal room-access opening subset source-closed"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
