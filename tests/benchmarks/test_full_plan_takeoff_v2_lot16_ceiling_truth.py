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


def test_lot16_promoted_ceiling_planes_are_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")
    universe = _json(project / "object_universe.json")

    assert manifest.status == "INCOMPLETE"

    planes = universe["source_closed_ceiling_planes"]
    expected_refs = {row["object_ref"] for row in planes}
    items = [
        item
        for item in manifest.verified_items
        if item.expected_object_refs
        and item.expected_object_refs[0] in expected_refs
    ]

    assert len(planes) == 3
    assert len(items) == 3
    assert all(item.trade_category == "ceilings" for item in items)
    assert all(item.unit == "m2" for item in items)
    assert all(item.denominator_eligible for item in items)
    assert all(len(item.expected_object_refs) == 1 for item in items)
    assert all(item.source_document_refs == ("reference_takeoff.json",) for item in items)
    assert sum(item.expected_quantity for item in items) == pytest.approx(49.340066)

    assert universe["promoted_ceiling_plane_subset_source_closed"] is True
    assert universe["project_ceiling_universe_complete"] is False

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_lot16_ceiling_reconciliation_is_exact_and_bed1_stays_out():
    project = ROOT / PROJECT_ID
    ref = _json(project / "reference_takeoff.json")
    closure = ref["source_closed_ceiling_plane_reconciliation"]

    assert closure["closure_check_ids"] == [
        "lot16:closure:garage_flat_ceiling_plane",
        "lot16:closure:ensuite_wir_raked_ceiling_planes",
    ]
    assert closure["object_count"] == 3
    assert closure["component_sum_m2"] == pytest.approx(49.340066)
    assert closure["source_closed_for_promoted_planes"] is True
    assert closure["complete_for_project_ceiling_universe"] is False
    assert "Bed 1" in closure["excluded_bed1_raked_ceiling_reason"]

    assert set(closure["component_object_refs"]) == {
        "lot16:surface:ceiling:garage_flat",
        "lot16:surface:ceiling:ensuite_raked_12deg",
        "lot16:surface:ceiling:wir_raked_12deg",
    }


def test_lot16_ceiling_subset_does_not_complete_project_ceiling_universe():
    project = ROOT / PROJECT_ID
    unresolved = _json(project / "unresolved_items.json")
    by_family = {row["family"]: row for row in unresolved["items"]}
    assert by_family["ceilings"]["status"] == "UNRESOLVED"

    report = _json(project / "verification_report.json")
    summary = report["ceiling_plane_closure_summary"]
    assert summary["verified_ceiling_plane_count"] == 3
    assert summary["verified_area_m2"] == pytest.approx(49.340066)
    assert summary["source_closed_for_promoted_planes"] is True
    assert summary["complete_for_project_ceiling_universe"] is False
    assert summary["bed1_raked_ceiling_promoted"] is False

    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["source-closed Lot16 ceiling-plane subset verified"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
