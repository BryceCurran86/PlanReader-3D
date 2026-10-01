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
    assert "wet_area_tile_bathroom_niche_face_and_all_niche_return_depths" in draft["unresolved_surface_families"]


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


def test_lot16_roof_sheathing_geometry_is_closed_but_engineering_crosscheck_blocks_finality():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    roof = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "roof_sheathing"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:roof_sheathing_geometry"
    )
    assert len(roof) == check["roof_plane_count"] == 4
    assert sum(float(row["attributes"]["projected_area_m2"]) for row in roof) == pytest.approx(252.04696)
    assert sum(float(row["expected_quantity"]) for row in roof) == pytest.approx(255.250323)
    assert check["total_projected_plan_area_m2"] == pytest.approx(252.04696)
    assert check["total_sloped_sheathing_area_m2"] == pytest.approx(255.250323)
    assert check["pitch_groups_degrees"] == [5, 12]
    assert check["complete_for_architectural_guide_geometry"] is True
    assert check["final_engineering_crosscheck_complete"] is False
    assert "roof_planes_final_crosscheck_against_engineering_stormwater_note" in draft["unresolved_surface_families"]

def test_3laurel_partial_internal_wall_gross_faces_are_dimension_closed_but_not_net_ready():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:partial_internal_wall_gross_faces"
    )
    refs = set(check["component_object_refs"])
    faces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"] in refs
    ]
    assert len(faces) == check["object_count"] == 8
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(53.838)
    assert check["bathroom_gross_area_m2"] == pytest.approx(25.002)
    assert check["gf_ensuite_laundry_gross_area_m2"] == pytest.approx(28.836)
    assert check["complete_for_these_two_finished_room_perimeters"] is True
    assert check["complete_for_project_internal_wall_universe"] is False
    assert check["openings_and_finish_deductions_resolved"] is False
    assert all(
        row["attributes"]["denominator_readiness"]
        == "draft_only_until_openings_and_finish_scope_are_resolved"
        for row in faces
    )
    assert (
        "internal_wall_faces_beyond_closed_bathroom_and_gf_ensuite_laundry_gross_faces"
        in draft["unresolved_surface_families"]
    )



def test_source_limitations_block_unverifiable_geometry_from_truth():
    lot16 = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    lot_blocker = next(
        row
        for row in lot16["closure_checks"]
        if row["check_id"] == "lot16:blocker:custom_front_glazing_measure_on_site"
    )
    assert lot_blocker["status"] == "UNRESOLVED_SOURCE_LIMITATION"
    assert lot_blocker["exact_dimensions_available"] is False
    assert lot_blocker["scaling_substitute_allowed"] is False
    assert "custom_front_glazing_measure_on_site_only" in lot16["unresolved_surface_families"]

    laurel = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    roof_blocker = next(
        row
        for row in laurel["closure_checks"]
        if row["check_id"] == "3laurel:blocker:roof_plane_geometry"
    )
    assert roof_blocker["status"] == "UNRESOLVED_SOURCE_LIMITATION"
    assert roof_blocker["roof_plan_sheet_present"] is False
    assert roof_blocker["figured_roof_plane_dimensions_available"] is False
    assert roof_blocker["scaling_substitute_allowed"] is False
    assert roof_blocker["pitch_evidence_degrees"] == [25]
    assert "roof_planes" in laurel["unresolved_surface_families"]


def test_3laurel_main_laundry_gross_wall_faces_are_dimension_closed_but_not_net_ready():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:main_laundry_internal_wall_gross_faces"
    )
    refs = set(check["component_object_refs"])
    faces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"] in refs
    ]
    assert len(faces) == check["object_count"] == 4
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(25.704)
    assert check["room_finished_dimensions_m"] == [3.08, 1.68]
    assert check["finished_ceiling_height_m"] == pytest.approx(2.7)
    assert check["complete_for_main_laundry_finished_room_perimeter"] is True
    assert check["openings_and_finish_deductions_resolved"] is False
    assert all(
        row["attributes"]["denominator_readiness"]
        == "draft_only_until_openings_and_finish_scope_are_resolved"
        for row in faces
    )
    assert (
        "internal_wall_faces_beyond_closed_bathroom_main_laundry_and_gf_ensuite_laundry_gross_faces"
        in draft["unresolved_surface_families"]
    )


def test_3laurel_two_source_dimensioned_niche_face_deductions_are_closed_but_returns_are_not():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:source_dimensioned_niche_face_deductions"
    )
    refs = set(check["component_object_refs"])
    openings = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"] in refs
    ]
    assert len(openings) == check["niche_opening_count"] == 2
    assert all(row["object_family"] == "wet_area_wall_tile_deduction_opening" for row in openings)
    assert sum(float(row["expected_quantity"]) for row in openings) == pytest.approx(0.48)
    assert check["flat_face_deduction_area_m2"] == pytest.approx(0.48)
    assert check["main_ensuite_rear_flat_tile_area_after_niche_m2"] == pytest.approx(4.296)
    assert check["gf_ensuite_rear_flat_tile_area_after_niche_m2"] == pytest.approx(4.809)
    assert check["niche_return_depths_resolved"] is False
    assert check["bathroom_niche_deduction_resolved"] is False
    assert all(
        row["attributes"]["niche_return_depth_resolved"] is False
        for row in openings
    )
    assert (
        "wet_area_tile_bathroom_niche_face_and_all_niche_return_depths"
        in draft["unresolved_surface_families"]
    )


def test_3laurel_main_ensuite_gross_wall_faces_close_from_finished_dimensions():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    faces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"].startswith(
            "3laurel:surface:internal_wall_gross:main_ensuite:"
        )
    ]
    assert len(faces) == 5
    assert {row["object_ref"].rsplit(":", 1)[1] for row in faces} == {
        "A", "B", "C", "D", "E"
    }
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(
        29.916
    )
    assert all(
        row["attributes"]["finished_ceiling_height_m"] == pytest.approx(2.7)
        for row in faces
    )
    assert all(
        row["attributes"]["denominator_readiness"]
        == "draft_only_until_openings_and_finish_scope_are_resolved"
        for row in faces
    )
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"]
        == "3laurel:control:main_ensuite_internal_wall_gross_faces"
    )
    assert check["object_count"] == 5
    assert check["component_sum_m2"] == pytest.approx(29.916)
    assert check["net_denominator_ready"] is False


def test_3laurel_main_wc_gross_wall_faces_close_from_finished_dimensions():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    faces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"].startswith(
            "3laurel:surface:internal_wall_gross:main_wc:"
        )
    ]
    assert len(faces) == 4
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(
        14.418
    )
    widths = sorted(row["attributes"]["finished_face_width_m"] for row in faces)
    assert widths == pytest.approx([1.11, 1.11, 1.56, 1.56])
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:main_wc_internal_wall_gross_faces"
    )
    assert check["object_count"] == 4
    assert check["component_sum_m2"] == pytest.approx(14.418)
    assert check["net_denominator_ready"] is False


def test_lot16_bed2_bed3_gross_wall_faces_are_dimension_closed_but_not_net_ready():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:bed2_bed3_gross_wall_faces"
    )
    refs = set(check["component_object_refs"])
    faces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"] in refs
    ]
    assert len(faces) == check["object_count"] == 8
    assert check["bed2_floor_dimension_closure"]["calculated_floor_area_m2"] == pytest.approx(11.88)
    assert check["bed2_floor_dimension_closure"]["source_declared_floor_area_m2"] == pytest.approx(11.88)
    assert check["bed3_floor_dimension_closure"]["calculated_floor_area_m2"] == pytest.approx(11.70)
    assert check["bed3_floor_dimension_closure"]["source_declared_floor_area_m2"] == pytest.approx(11.70)
    assert check["wall_height_to_top_plate_m"] == pytest.approx(2.59)
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(71.225)
    assert check["gross_wall_area_m2"] == pytest.approx(71.225)
    assert check["complete_for_bed2_bed3_top_plate_rectangular_wall_faces"] is True
    assert check["openings_and_ceiling_intersections_resolved"] is False
    assert all(
        row["attributes"]["denominator_readiness"]
        == "draft_only_until_openings_and_ceiling_intersection_are_resolved"
        for row in faces
    )
    assert (
        "internal_wall_faces_beyond_closed_bed2_bed3_top_plate_gross_faces"
        in draft["unresolved_surface_families"]
    )

def test_3laurel_internal_room_access_door_census_is_source_closed_but_joinery_stays_open():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    openings = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "internal_room_access_opening"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:closure:internal_room_access_door_census"
    )
    assert len(openings) == check["room_access_opening_count"] == 14
    assert sum(float(row["expected_quantity"]) for row in openings) == pytest.approx(25.011)
    assert check["hinged_count"] == 8
    assert check["cavity_slider_count"] == 6
    assert check["width_distribution_m"] == {"0.72": 4, "0.87": 9, "1.20": 1}
    assert check["joinery_height_m"] == pytest.approx(2.1)
    assert check["complete_for_labelled_room_access_doors"] is True
    assert check["complete_for_all_internal_wall_openings"] is False
    assert "robe_and_linen_sliding_joinery_openings" in check["residual_unresolved"]
    assert all(
        row["attributes"]["wall_deduction_scope"] == "room_access_opening_only"
        for row in openings
    )
    assert (
        "internal_wall_openings_beyond_closed_room_access_doors_including_robe_linen_joinery"
        in draft["unresolved_surface_families"]
    )

def test_3laurel_labelled_internal_joinery_openings_are_closed_but_unlabelled_breaks_stay_open():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    openings = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_family"] == "internal_sliding_joinery_opening"
    ]
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:closure:internal_sliding_joinery_opening_census"
    )
    assert len(openings) == check["labelled_vsd_opening_count"] == 4
    assert sum(float(row["expected_quantity"]) for row in openings) == pytest.approx(13.86)
    assert check["width_distribution_m"] == {"1.20": 1, "1.80": 3}
    assert check["joinery_height_m"] == pytest.approx(2.1)
    assert check["complete_for_explicit_vsd_labels"] is True
    assert check["complete_for_all_internal_wall_openings"] is False
    assert check["residual_unresolved"] == [
        "unlabelled_internal_wall_breaks_or_open_archways"
    ]
    assert (
        "unlabelled_internal_wall_breaks_or_open_archways_for_wall_face_deductions"
        in draft["unresolved_surface_families"]
    )



def test_3laurel_bathroom_wc_room_access_deductions_are_mapped_but_not_full_net_walls():
    draft = _load(ROOT / "au_qld_3laurel" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "3laurel:control:bathroom_wc_room_access_deductions"
    )
    assert check["mapped_room_access_opening_count"] == 2
    assert check["mapped_room_access_opening_area_m2"] == pytest.approx(3.024)
    by_room = {row["room"]: row for row in check["room_controls"]}
    assert by_room["main_bathroom"]["gross_wall_area_m2"] == pytest.approx(25.002)
    assert by_room["main_bathroom"]["access_opening_area_m2"] == pytest.approx(1.512)
    assert by_room["main_bathroom"]["gross_less_room_access_opening_m2"] == pytest.approx(23.49)
    assert by_room["main_wc"]["gross_wall_area_m2"] == pytest.approx(14.418)
    assert by_room["main_wc"]["access_opening_area_m2"] == pytest.approx(1.512)
    assert by_room["main_wc"]["gross_less_room_access_opening_m2"] == pytest.approx(12.906)
    assert check["complete_for_these_room_access_openings"] is True
    assert check["complete_for_all_wall_openings"] is False
    assert check["finish_scope_resolved"] is False


def test_lot16_explicit_internal_elevation_wall_faces_close_to_top_plate():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    refs = {
        "lot16:surface:internal_wall_gross:bath:elev1",
        "lot16:surface:internal_wall_gross:bath:shower",
        "lot16:surface:internal_wall_gross:bath:elev4",
        "lot16:surface:internal_wall_gross:ensuite:elev1",
        "lot16:surface:internal_wall_gross:ensuite:elev2",
        "lot16:surface:internal_wall_gross:wc:elev1",
        "lot16:surface:internal_wall_gross:laundry:elev1",
        "lot16:surface:internal_wall_gross:laundry:elev2",
    }
    faces = [
        row for row in draft["verified_physical_candidates"]
        if row["object_ref"] in refs
    ]
    assert len(faces) == 8
    assert {row["object_ref"] for row in faces} == refs
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(
        35.3794
    )
    assert all(
        row["attributes"]["wall_height_to_top_plate_m"] == pytest.approx(2.59)
        for row in faces
    )
    assert all(
        row["attributes"]["raked_ceiling_extension_included"] is False
        for row in faces
    )
    check = next(
        row for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:explicit_internal_elevation_wall_faces"
    )
    assert check["object_count"] == 8
    assert check["component_sum_m2"] == pytest.approx(35.3794)
    assert check["net_denominator_ready"] is False

def test_lot16_bed1_gross_wall_faces_are_dimension_closed_but_raked_extension_stays_open():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:bed1_gross_wall_faces"
    )
    refs = set(check["component_object_refs"])
    faces = [
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"] in refs
    ]
    assert len(faces) == check["object_count"] == 4
    floor = check["bed1_floor_dimension_closure"]
    assert floor["figured_dimensions_m"] == pytest.approx([3.51, 3.60])
    assert floor["calculated_floor_area_m2"] == pytest.approx(12.636)
    assert floor["source_declared_floor_area_m2"] == pytest.approx(12.64)
    assert floor["rounding_difference_m2"] == pytest.approx(0.004)
    assert check["wall_height_to_top_plate_m"] == pytest.approx(2.59)
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(36.8298)
    assert check["gross_wall_area_m2"] == pytest.approx(36.8298)
    assert check["complete_for_bed1_top_plate_rectangular_wall_faces"] is True
    assert check["openings_and_raked_ceiling_intersection_resolved"] is False
    assert all(row["attributes"]["raked_ceiling_extension_included"] is False for row in faces)
    assert (
        "internal_wall_faces_beyond_closed_bed1_bed2_bed3_top_plate_gross_faces"
        in draft["unresolved_surface_families"]
    )



def test_lot16_unscheduled_structural_members_stay_out_of_truth():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    blocker = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:blocker:unscheduled_structural_members"
    )
    assert blocker["status"] == "UNRESOLVED_SOURCE_LIMITATION"
    assert blocker["instance_specific_bracing_schedule_available"] is True
    assert blocker["remaining_instance_specific_beam_lintel_truss_schedule_available"] is False
    assert blocker["typical_detail_scaling_allowed"] is False
    assert (
        "structural_members_beyond_closed_wall_bracing_and_explicit_architectural_supports"
        in draft["unresolved_surface_families"]
    )


def test_lot16_source_closed_bath_tile_faces_stay_gross_until_deductions_close():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    refs = {
        "lot16:surface:wall_tile_gross:bath:elev1",
        "lot16:surface:wall_tile_gross:bath:shower",
        "lot16:surface:wall_tile_gross:bath:elev4",
    }
    faces = [
        row for row in draft["verified_physical_candidates"]
        if row["object_ref"] in refs
    ]
    assert len(faces) == 3
    assert {row["object_ref"] for row in faces} == refs
    assert sum(float(row["expected_quantity"]) for row in faces) == pytest.approx(
        9.324
    )
    assert all(
        row["attributes"]["tile_height_to_top_plate_m"] == pytest.approx(2.59)
        for row in faces
    )
    assert all(
        "draft_only_until_remaining_bath_face_niche_opening_and_return_deductions_are_closed"
        == row["attributes"]["denominator_readiness"]
        for row in faces
    )
    check = next(
        row for row in draft["closure_checks"]
        if row["check_id"] == "lot16:control:explicit_bath_tile_gross_faces"
    )
    assert check["object_count"] == 3
    assert check["component_sum_m2"] == pytest.approx(9.324)
    assert check["net_denominator_ready"] is False

def test_lot16_explicit_bath_shower_tile_face_is_net_closed_but_wet_area_universe_stays_open():
    draft = _load(ROOT / "au_qld_lot16_power" / "reference_truth_draft.json")
    tile = next(
        row
        for row in draft["verified_physical_candidates"]
        if row["object_ref"] == "lot16:surface:wall_tile:bath_shower_full_height:01"
    )
    check = next(
        row
        for row in draft["closure_checks"]
        if row["check_id"] == "lot16:closure:bath_shower_full_height_tile_face"
    )
    assert tile["expected_quantity"] == pytest.approx(3.108)
    assert tile["attributes"]["finished_face_width_m"] == pytest.approx(1.2)
    assert tile["attributes"]["tile_height_m"] == pytest.approx(2.59)
    assert tile["attributes"]["openings_in_host_face"] is False
    assert tile["attributes"]["net_finish_area_ready"] is True
    assert check["tile_area_m2"] == pytest.approx(3.108)
    assert check["complete_for_this_explicit_face"] is True
    assert check["complete_for_project_wet_area_tile_universe"] is False
    assert (
        "wet_area_wall_tiling_beyond_explicit_bath_shower_full_height_face"
        in draft["unresolved_surface_families"]
    )

