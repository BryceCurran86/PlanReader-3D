import pb_opening_deductions_v134 as legacy


def test_each_opening_can_be_included_or_excluded_from_deduction():
    # Under the production safety fence, an opening is subtracted only when it is
    # a confirmed estimator/manual override (with an assigned wall) or a completed
    # B5 decision. A plain legacy ``deduct=True`` default is not sufficient
    # authority. Functions are resolved via the module at call time so the test is
    # valid whether or not the production fence has been installed.
    window = {"kind": "Window", "width_m": 1.2, "height_m": 1.5, "quantity": 2, "deduct": True, "wall_ref": "W01", "manual_override_confirmed": True}
    door = {"kind": "Door", "width_m": 0.9, "height_m": 2.1, "quantity": 1, "deduct": False, "wall_ref": "W01"}
    assert legacy.opening_area_m2(window) == 3.6
    assert legacy.opening_area_m2(door) == 1.89
    assert legacy.deducted_area_m2([window, door]) == 3.6
    assert legacy.net_wall_area_m2(20.0, [window, door]) == 16.4


def test_toggle_changes_net_wall_area_without_removing_opening():
    opening = legacy.normalise_opening(
        {"kind": "Door", "width_m": 1.0, "height_m": 2.0, "deduct": True, "wall_ref": "W01", "manual_override_confirmed": True}
    )
    assert legacy.net_wall_area_m2(10.0, [opening]) == 8.0
    opening["deduct"] = False
    assert legacy.net_wall_area_m2(10.0, [opening]) == 10.0


def test_deduction_never_drives_wall_negative():
    opening = {"kind": "Window", "width_m": 5.0, "height_m": 5.0, "deduct": True, "wall_ref": "W01", "manual_override_confirmed": True}
    assert legacy.net_wall_area_m2(10.0, [opening]) == 0.0


def test_ag12_unauthenticated_opening_default_abstains_without_fence():
    # AG-12: Unauthenticated opening defaults must not reduce wall m²
    raw_unvetted = {
        "kind": "Window",
        "width_m": 1.5,
        "height_m": 2.0,
        "quantity": 1,
        "deduct": True,
        # Missing assigned wall, missing manual confirmation, missing B5 proof
    }
    assert legacy.deducted_area_m2([raw_unvetted]) == 0.0
    assert legacy.net_wall_area_m2(20.0, [raw_unvetted]) == 20.0


def test_ag12_duplicate_opening_references_deducted_at_most_once():
    # AG-12: Duplicate references to the same physical opening must be deducted at most once
    opening = {
        "id": "OP-DUPLICATE-01",
        "opening_instance_id": "INST-01",
        "kind": "Window",
        "width_m": 1.5,
        "height_m": 2.0,
        "quantity": 1,
        "deduct": True,
        "wall_ref": "W01",
        "manual_override_confirmed": True,
    }
    # Pass same opening twice
    assert legacy.deducted_area_m2([opening, opening]) == 3.0
    assert legacy.net_wall_area_m2(20.0, [opening, opening]) == 17.0
