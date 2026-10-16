"""Regression tests: a named drawing type outranks cross-sheet references."""
from pb_sheet_classification_v172 import classify_sheet_role


def test_floor_plan_title_not_overridden_by_rcp_reference():
    role, confidence, _, target = classify_sheet_role(
        "GROUND FLOOR PLAN", "Refer to reflected ceiling plan for ceiling levels."
    )
    assert (role, target) == ("FLOOR_PLAN", "WALL_FLOOR")
    assert confidence >= 0.90


def test_ceiling_title_not_overridden_by_door_schedule_reference():
    role, _, _, target = classify_sheet_role(
        "REFLECTED CEILING PLAN", "Refer to door schedule and elevations."
    )
    assert (role, target) == ("REFLECTED_CEILING_PLAN", "CEILING")


def test_elevation_title_not_overridden_by_finish_schedule_reference():
    role, _, _, target = classify_sheet_role(
        "INTERNAL ELEVATION", "See room finish schedule for FT3."
    )
    assert (role, target) == ("ELEVATION", "ELEVATION_SURFACE")


def test_generic_plan_title_abstains_even_with_schedule_reference():
    role, confidence, _, target = classify_sheet_role(
        "PROPOSED PLAN", "Refer to door schedule and ceiling plan."
    )
    assert (role, target) == ("OTHER_GENERAL", "NONE")
    assert confidence < 0.90


def test_unheaded_text_only_cannot_prove_authoritative_view():
    role, confidence, _, _ = classify_sheet_role("", "Refer to ground floor plan.")
    assert role == "FLOOR_PLAN"
    assert confidence < 0.90


def test_explicit_schedule_title_remains_supported():
    assert classify_sheet_role("DOOR SCHEDULE")[0] == "DOOR_WINDOW_SCHEDULE"
    assert classify_sheet_role("FINISH SCHEDULE")[0] == "FINISH_SCHEDULE"
