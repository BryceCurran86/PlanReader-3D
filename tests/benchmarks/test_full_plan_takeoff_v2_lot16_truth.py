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


def test_lot16_external_opening_truth_is_atomic_and_project_stays_incomplete():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")

    assert manifest.status == "INCOMPLETE"
    assert len(manifest.reference_takeoff_documents) == 1
    assert len(manifest.verified_items) == 13
    assert all(item.denominator_eligible for item in manifest.verified_items)

    by_trade = {}
    for item in manifest.verified_items:
        by_trade[item.trade_category] = by_trade.get(item.trade_category, 0) + 1
        assert item.unit == "m2"
        assert len(item.expected_object_refs) == 1
        assert item.source_document_refs == ("reference_takeoff.json",)
        assert item.source_location_refs
        assert item.verification_status == "VERIFIED"

    assert by_trade == {"windows": 7, "doors": 6}
    assert sum(item.expected_quantity for item in manifest.verified_items) == pytest.approx(37.584)

    universe = _json(project / "object_universe.json")
    openings = universe["external_openings"]
    assert len(openings) == 13
    assert {row["object_ref"] for row in openings} == {
        item.expected_object_refs[0] for item in manifest.verified_items
    }
    assert universe["dimensioned_external_opening_subset_complete"] is True
    assert universe["external_opening_universe_complete"] is False
    unresolved = universe["unresolved_external_openings"]
    assert len(unresolved) == 1
    assert "MEASURE ON SITE" in unresolved[0]["reason"]

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_lot16_opening_truth_keeps_unfinished_families_fail_closed():
    project = ROOT / PROJECT_ID
    unresolved = _json(project / "unresolved_items.json")
    by_family = {row["family"]: row for row in unresolved["items"]}

    assert by_family["external_openings"]["status"] == "PARTIAL"
    assert "MEASURE ON SITE" in by_family["external_openings"]["reason"]
    for family in (
        "internal_wall_faces",
        "external_wall_faces_and_cladding",
        "ceilings",
        "wet_area_wall_tiling",
        "structural_members",
        "roof_surfaces",
    ):
        assert by_family[family]["status"] == "UNRESOLVED"

    report = _json(project / "verification_report.json")
    assert report["project_status"] == "INCOMPLETE"
    assert report["source_hash_verification"]["status"] == "PASS"
    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["PlanReader output not used as benchmark truth"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
    assert report["opening_closure_summary"]["verified_opening_count"] == 13
    assert report["opening_closure_summary"]["verified_area_m2"] == pytest.approx(37.584)
