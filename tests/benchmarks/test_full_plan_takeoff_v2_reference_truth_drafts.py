from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "frozen_holdout" / "full_plan_v2" / "projects"
PROJECTS = ("au_qld_lot16_power", "au_qld_3laurel")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("project_id", PROJECTS)
def test_reference_truth_draft_is_fail_closed_and_source_locked(project_id: str):
    project_root = ROOT / project_id
    manifest = _load(project_root / "source_manifest.json")
    draft = _load(project_root / "reference_truth_draft.json")

    assert draft["schema_version"] == "draft-reference-truth-v1"
    assert draft["project_id"] == project_id == manifest["project_id"]
    assert draft["status"] == "DRAFT_INCOMPLETE"
    assert "never PlanReader output" in draft["truth_source_policy"]
    assert draft["unresolved_surface_families"]
    assert "Do not mark project VERIFIED" in draft["completion_rule"]

    frozen_docs = {doc["name"]: doc["sha256"] for doc in manifest["source_documents"]}
    assert draft["source_documents"]
    for source in draft["source_documents"]:
        assert frozen_docs[source["name"]] == source["sha256"]


@pytest.mark.parametrize("project_id", PROJECTS)
def test_reference_truth_candidates_have_unique_positive_source_lineage(project_id: str):
    draft = _load(ROOT / project_id / "reference_truth_draft.json")
    candidates = draft["verified_physical_candidates"]
    assert candidates

    refs = [row["object_ref"] for row in candidates]
    assert len(refs) == len(set(refs))

    for row in candidates:
        assert row["physical_kind"] in {"surface", "opening_surface", "structural_member"}
        assert row["object_family"]
        assert row["description"]
        quantity = float(row["expected_quantity"])
        assert math.isfinite(quantity) and quantity > 0
        assert row["unit"] in {"m", "m2", "count"}
        assert row["source_location"]
        assert "planreader" not in row["source_location"].lower()


@pytest.mark.parametrize("project_id", PROJECTS)
def test_aggregate_controls_are_explicitly_separate_from_physical_candidates(project_id: str):
    draft = _load(ROOT / project_id / "reference_truth_draft.json")
    candidate_refs = {row["object_ref"] for row in draft["verified_physical_candidates"]}
    controls = draft["aggregate_controls_not_denominator"]
    assert controls

    for control in controls:
        assert control["control_id"] not in candidate_refs
        assert math.isfinite(float(control["expected_quantity"]))
        assert float(control["expected_quantity"]) > 0
        assert control["source_location"]
        assert control["reason"]


def test_lot16_and_3laurel_truth_drafts_do_not_modify_live_v2_denominator():
    for project_id in PROJECTS:
        manifest = _load(ROOT / project_id / "source_manifest.json")
        assert manifest["status"] == "INCOMPLETE"
        assert manifest["reference_takeoff_documents"] == []
        assert manifest["verified_takeoff_items"] == []


@pytest.mark.parametrize(
    ("project_id", "check_id"),
    (
        ("au_qld_lot16_power", "lot16:closure:declared_floor_area"),
        ("au_qld_3laurel", "3laurel:closure:declared_floor_area"),
    ),
)
def test_declared_floor_area_components_close_exactly_to_source_total(project_id: str, check_id: str):
    draft = _load(ROOT / project_id / "reference_truth_draft.json")
    check = next(row for row in draft["closure_checks"] if row["check_id"] == check_id)
    by_ref = {row["object_ref"]: row for row in draft["verified_physical_candidates"]}
    calculated = sum(float(by_ref[ref]["expected_quantity"]) for ref in check["component_object_refs"])
    assert calculated == pytest.approx(float(check["declared_total_m2"]), abs=1e-9)
    assert float(check["difference_m2"]) == pytest.approx(0.0, abs=1e-9)



def test_3laurel_primary_ceiling_planes_close_to_declared_plan_area():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    check = next(row for row in draft["closure_checks"] if row["check_id"] == "3laurel:closure:primary_ceiling_planes")
    by_ref = {row["object_ref"]: row for row in draft["verified_physical_candidates"]}
    calculated = sum(float(by_ref[ref]["expected_quantity"]) for ref in check["component_object_refs"])
    assert calculated == pytest.approx(297.50, abs=1e-9)
    assert calculated == pytest.approx(float(check["declared_reference_plan_area_m2"]), abs=1e-9)


def test_3laurel_gross_shower_tile_faces_stay_out_of_net_denominator_until_deductions_close():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    faces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "wet_area_wall_tile_gross_face"
    ]
    assert len(faces) == 8
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(23.085)
    assert all(
        row["attributes"]["denominator_readiness"]
        == "draft_only_until_niche_and_return_adjustments_are_resolved"
        for row in faces
    )
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:gross_shower_tile_faces"
    )
    assert check["net_denominator_ready"] is False
    assert "niche/recess returns and deductions remain unresolved" in check["reason"]
    assert "wet_area_tile_niche_returns_and_recess_deductions" in draft["unresolved_surface_families"]
