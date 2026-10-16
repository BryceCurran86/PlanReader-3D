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


def test_workspace_registry_uses_page_label_before_page_type():
    import sqlite3
    from pb_sheet_classification_v172 import SheetClassificationRegistry

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE pages (id INTEGER, workspace_id INTEGER, page_label TEXT, page_type TEXT)")
    db.execute(
        "INSERT INTO pages VALUES (?, ?, ?, ?)",
        (1, 42, "GROUND FLOOR PLAN", "See reflected ceiling plan"),
    )
    try:
        records = SheetClassificationRegistry.derive_for_workspace(db, 42).records
        assert len(records) == 1
        assert records[0].canonical_role == "FLOOR_PLAN"
        assert records[0].primary_takeoff_target == "WALL_FLOOR"
    finally:
        db.close()
