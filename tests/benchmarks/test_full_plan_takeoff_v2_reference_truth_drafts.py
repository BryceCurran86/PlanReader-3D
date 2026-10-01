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


def test_3laurel_typed_external_opening_census_is_source_closed():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    openings = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "external_opening"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:typed_external_opening_census"
    )
    assert len(openings) == 20
    assert check["typed_opening_count"] == 20
    assert sum(float(row["expected_quantity"]) for row in openings) == pytest.approx(58.59)
    assert check["typed_opening_area_m2"] == pytest.approx(58.59)
    assert check["complete_for_typed_labels"] is True
    assert check["complete_for_all_openings"] is False
    assert "untyped_or_ambiguous_door_openings_and_internal_external_classification" in draft["unresolved_surface_families"]


@pytest.mark.parametrize(
    ("project_id", "check_id", "expected_count", "expected_length"),
    (
        ("au_qld_lot16_power", "lot16:closure:wall_bracing_schedule", 24, 27.9),
        ("au_qld_3laurel", "3laurel:closure:wall_bracing_schedule", 37, 45.75),
    ),
)
def test_wall_bracing_schedule_closure(project_id: str, check_id: str, expected_count: int, expected_length: float):
    draft = _load(ROOT / project_id / "reference_truth_draft.json")
    braces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "wall_bracing"
    ]
    check = next(row for row in draft["closure_checks"] if row["check_id"] == check_id)
    assert len(braces) == expected_count == check["object_count"]
    assert sum(float(row["expected_quantity"]) for row in braces) == pytest.approx(expected_length)
    assert check["total_length_m"] == pytest.approx(expected_length)

def test_lot16_typed_external_opening_census_closes_without_guessing_custom_front_glazing():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    openings = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "external_opening"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:typed_external_opening_census"
    )
    assert len(openings) == check["typed_opening_count"] == 10
    assert sum(float(row["expected_quantity"]) for row in openings) == pytest.approx(31.41)
    assert check["typed_opening_area_m2"] == pytest.approx(31.41)
    assert check["complete_for_typed_dimensioned_labels"] is True
    assert check["complete_for_all_openings"] is False
    assert "custom_front_windows_measure_on_site" in check["residual_unresolved"]
    assert (
        "custom_front_glazing_and_untyped_external_door_elements"
        in draft["unresolved_surface_families"]
    )


def test_3laurel_explicit_external_post_and_pier_census_is_source_closed():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    posts = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "external_structural_post"
    ]
    piers = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "external_structural_pier"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:closure:external_post_pier_census"
    )
    assert len(posts) == check["timber_post_count"] == 2
    assert len(piers) == check["brick_pier_count"] == 4
    assert len(posts) + len(piers) == check["object_count"] == 6
    assert all(row["attributes"]["section_mm"] == "140x140" for row in posts)
    assert all(row["attributes"]["section_mm"] == "470x470" for row in piers)
    assert check["complete_for_explicitly_dimensioned_posts_and_piers"] is True
    assert (
        "structural_members_beyond_closed_wall_bracing_and_explicit_140x140_posts_470x470_piers"
        in draft["unresolved_surface_families"]
    )

def test_lot16_bracing_resistance_control_matches_engineering_schedule():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:wall_bracing_resistance"
    )
    assert check["direction_A"]["required_kN"] == pytest.approx(98.90)
    assert check["direction_A"]["provided_kN"] == pytest.approx(104.96)
    assert check["direction_A"]["margin_kN"] == pytest.approx(6.06)
    assert check["direction_B"]["required_kN"] == pytest.approx(45.70)
    assert check["direction_B"]["provided_kN"] == pytest.approx(51.48)
    assert check["direction_B"]["margin_kN"] == pytest.approx(5.78)
    assert check["direction_A"]["provided_kN"] > check["direction_A"]["required_kN"]
    assert check["direction_B"]["provided_kN"] > check["direction_B"]["required_kN"]


def test_3laurel_bracing_resistance_controls_match_source_schedules():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:wall_bracing_resistance"
    )
    expected = {
        "A": (93.71, 97.84, 4.13),
        "B": (44.66, 49.68, 5.02),
        "A_U2": (25.41, 30.70, 5.29),
        "B_U2": (31.20, 33.60, 2.40),
    }
    for key, (required, provided, margin) in expected.items():
        row = check["schedules"][key]
        assert row["required_kN"] == pytest.approx(required)
        assert row["provided_kN"] == pytest.approx(provided)
        assert row["margin_kN"] == pytest.approx(margin)
        assert row["provided_kN"] > row["required_kN"]

def test_lot16_explicit_architectural_support_census_is_source_closed():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    supports = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "architectural_support_member"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:closure:explicit_architectural_support_census"
    )
    assert len(supports) == check["object_count"] == 3
    assert check["telescopic_pier_count"] == 2
    assert check["hardwood_post_count"] == 1
    assert sum(
        row["attributes"]["member_type"] == "telescopic_pier" for row in supports
    ) == 2
    post = next(
        row for row in supports if row["attributes"]["member_type"] == "timber_post"
    )
    assert post["attributes"]["section_mm"] == "90x90"
    assert post["attributes"]["material"] == "hardwood"
    assert check["complete_for_explicitly_labelled_architectural_supports"] is True
    assert check["structural_engineering_instance_schedule_available"] is False
    assert (
        "structural_members_beyond_closed_wall_bracing_and_explicit_architectural_supports"
        in draft["unresolved_surface_families"]
    )



def test_lot16_known_external_openings_close_except_measure_on_site_glazing():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    openings = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "external_opening"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:known_external_opening_census"
    )
    assert len(openings) == check["known_opening_count"] == 13
    assert sum(float(row["expected_quantity"]) for row in openings) == pytest.approx(37.584)
    assert check["known_opening_area_m2"] == pytest.approx(37.584)
    assert check["complete_for_all_dimensioned_and_plan_width_openings"] is True
    assert check["complete_for_all_external_openings"] is False
    assert check["residual_unresolved"] == ["custom_front_windows_measure_on_site"]
    assert "custom_front_glazing_measure_on_site_only" in draft["unresolved_surface_families"]


def test_3laurel_external_opening_universe_is_source_closed():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    openings = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "external_opening"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:closure:external_opening_census"
    )
    assert len(openings) == check["external_opening_count"] == 23
    assert sum(float(row["expected_quantity"]) for row in openings) == pytest.approx(64.764)
    assert check["external_opening_area_m2"] == pytest.approx(64.764)
    assert check["complete_for_all_external_openings"] is True
    assert (
        "internal_door_opening_universe_for_wall_face_deductions"
        in draft["unresolved_surface_families"]
    )
    assert (
        "untyped_or_ambiguous_door_openings_and_internal_external_classification"
        not in draft["unresolved_surface_families"]
    )
