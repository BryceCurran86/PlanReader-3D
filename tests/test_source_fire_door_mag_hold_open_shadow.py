"""Unit tests for Source Fire Door Electro-Magnetic Hold-Open Release & Door Selector Shadow Authority."""

import pytest
from pb_source_fire_door_mag_hold_open_shadow import (
    FireDoorMagHoldCandidate,
    snap_point,
    parse_fire_door_mag_hold_callout,
    evaluate_fire_door_mag_hold_open_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((12.4, 14.9)) == (12.5, 15.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_fire_door_mag_hold_callout_rebated_pair():
    text = "DOUBLE FIRE DOOR WITH REBATED DOOR SELECTOR AND 24V DC MAGNETIC HOLD OPEN WALL MOUNT 2-HR"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["door_leaf_configuration"] == "DOUBLE_LEAF_REBATED"
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["mount_type"] == "WALL_MOUNT"
    assert parsed["voltage"] == "24V_DC"
    assert parsed["smoke_release_interface"] == True
    assert parsed["sequential_selector_required"] == True


def test_parse_fire_door_mag_hold_callout_floor_mount_1hr():
    text = "SINGLE LEAF FIRE DOOR -/60/30 WITH FLOOR MOUNT MAG HOLD OPEN"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["door_leaf_configuration"] == "SINGLE_LEAF"
    assert parsed["fire_rating_hours"] == 1.0
    assert parsed["mount_type"] == "FLOOR_MOUNT"
    assert parsed["sequential_selector_required"] == False


def test_parse_fire_door_mag_hold_callout_overhead_240v():
    text = "OVERHEAD ELECTRO-MAGNETIC HOLDER 240VAC 3-HR"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["mount_type"] == "OVERHEAD_SURFACE"
    assert parsed["voltage"] == "240V_AC"
    assert parsed["fire_rating_hours"] == 3.0


def test_parse_fire_door_mag_hold_callout_frl_120():
    text = "MAGNETIC DOOR HOLDER FRL -/120/30"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["fire_rating_hours"] == 2.0


def test_parse_fire_door_mag_hold_callout_unrelated():
    assert parse_fire_door_mag_hold_callout("STANDARD TIMBER FLUSH DOOR D01") is None


def test_evaluate_fire_door_mag_hold_open_shadow_single():
    callouts = ["MAG HOLD OPEN 24V DC 2-HR WALL MOUNT"]
    positions = [(100.2, 200.4)]
    res = evaluate_fire_door_mag_hold_open_shadow("A-801", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "A-801_mho_001"
    assert c.sheet_id == "A-801"
    assert c.position == (100.0, 200.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_fire_door_mag_hold_open_shadow_dict():
    c = FireDoorMagHoldCandidate(
        candidate_id="A-802_mho_001",
        sheet_id="A-802",
        door_leaf_configuration="DOUBLE_LEAF_REBATED",
        fire_rating_hours=2.0,
        mount_type="WALL_MOUNT",
        voltage="24V_DC",
        smoke_release_interface=True,
        sequential_selector_required=True,
        position=(50.0, 50.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "A-802_mho_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["door_leaf_configuration"] == "DOUBLE_LEAF_REBATED"


def test_evaluate_fire_door_mag_hold_open_shadow_no_positions():
    callouts = ["MAG HOLD OPEN"]
    res = evaluate_fire_door_mag_hold_open_shadow("A-803", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_fire_door_mag_hold_open_shadow_safety_cap():
    callouts = ["MAG HOLD OPEN"] * 10
    res = evaluate_fire_door_mag_hold_open_shadow("A-804", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_fire_door_mag_hold_open_shadow("A-805", []) == []


def test_unrelated_callout_filtering():
    callouts = ["ALUMINIUM SLIDING WINDOW", "MAG HOLD OPEN 24V"]
    res = evaluate_fire_door_mag_hold_open_shadow("A-806", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "A-806_mho_002"


def test_door_coordinator_keyword():
    text = "PAIR OF FIRE DOORS WITH DOOR COORDINATOR"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["sequential_selector_required"] is True
    assert parsed["door_leaf_configuration"] == "DOUBLE_LEAF_REBATED"


def test_manual_only_no_smoke():
    text = "MAG HOLD OPEN MANUAL ONLY"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["smoke_release_interface"] is False


def test_default_values():
    text = "FIRE DOOR HOLD OPEN"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["door_leaf_configuration"] == "SINGLE_LEAF"
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["mount_type"] == "WALL_MOUNT"
    assert parsed["voltage"] == "24V_DC"
    assert parsed["smoke_release_interface"] is True
    assert parsed["sequential_selector_required"] is False


def test_snapping_precision():
    callouts = ["MAG HOLD OPEN"]
    positions = [(4.9, 9.9)]
    res = evaluate_fire_door_mag_hold_open_shadow("A-807", callouts, positions)
    assert res[0].position == (5.0, 10.0)


def test_transom_mount_keyword():
    text = "TRANSOM MOUNT MAGNETIC DOOR HOLDER"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["mount_type"] == "OVERHEAD_SURFACE"


def test_electromagnetic_full_spelling():
    text = "ELECTROMAGNETIC HOLD OPEN ON FIRE ALARM"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["voltage"] == "24V_DC"


def test_plain_double_leaf():
    text = "DOUBLE FIRE DOOR MAGNETIC HOLD OPEN"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["door_leaf_configuration"] == "DOUBLE_LEAF_PLAIN"
    assert parsed["sequential_selector_required"] is False


def test_two_leaf_keyword():
    text = "2 LEAF FIRE DOOR MAG HOLD OPEN"
    parsed = parse_fire_door_mag_hold_callout(text)
    assert parsed is not None
    assert parsed["door_leaf_configuration"] == "DOUBLE_LEAF_PLAIN"
