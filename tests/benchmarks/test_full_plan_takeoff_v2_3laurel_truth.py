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


def test_3laurel_external_opening_truth_is_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")

    assert manifest.status == "INCOMPLETE"
    assert len(manifest.reference_takeoff_documents) == 1
    assert len(manifest.verified_items) == 23
    assert all(item.denominator_eligible for item in manifest.verified_items)

    by_trade = {}
    for item in manifest.verified_items:
        by_trade[item.trade_category] = by_trade.get(item.trade_category, 0) + 1
        assert item.unit == "m2"
        assert len(item.expected_object_refs) == 1
        assert item.source_document_refs == ("reference_takeoff.json",)
        assert item.source_location_refs
        assert item.verification_status == "VERIFIED"

    assert by_trade == {"windows": 16, "doors": 7}
    assert sum(item.expected_quantity for item in manifest.verified_items) == pytest.approx(
        64.764
    )

    universe = _json(project / "object_universe.json")
    openings = universe["external_openings"]
    assert len(openings) == 23
    assert {row["object_ref"] for row in openings} == {
        item.expected_object_refs[0] for item in manifest.verified_items
    }
    assert universe["external_opening_universe_complete"] is True

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_3laurel_opening_truth_reconciles_window_and_door_subtotals():
    report = _json(ROOT / PROJECT_ID / "verification_report.json")
    summary = report["opening_closure_summary"]

    assert summary["verified_opening_count"] == 23
    assert summary["verified_area_m2"] == pytest.approx(64.764)
    assert summary["window_glazing_count"] == 16
    assert summary["window_glazing_area_m2"] == pytest.approx(35.28)
    assert summary["door_count"] == 7
    assert summary["door_area_m2"] == pytest.approx(29.484)
    assert summary["external_opening_universe_complete"] is True


def test_3laurel_remaining_project_families_stay_fail_closed():
    project = ROOT / PROJECT_ID
    unresolved = _json(project / "unresolved_items.json")
    expected = {
        "internal_wall_faces",
        "external_wall_faces_and_cladding",
        "roof_surfaces",
        "structural_members",
        "secondary_fc_soffit_and_beam_faces",
        "wet_area_tile_niches_and_returns",
        "remaining_wet_area_tile_scope",
        "internal_opening_universe",
    }
    by_family = {row["family"]: row for row in unresolved["items"]}
    assert set(by_family) == expected
    assert all(row["status"] == "UNRESOLVED" for row in by_family.values())

    report = _json(project / "verification_report.json")
    assert report["project_status"] == "INCOMPLETE"
    assert report["source_hash_verification"]["status"] == "PASS"
    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["external opening universe source-closed"]["status"] == "PASS"
    assert proofs["PlanReader output not used as benchmark truth"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
