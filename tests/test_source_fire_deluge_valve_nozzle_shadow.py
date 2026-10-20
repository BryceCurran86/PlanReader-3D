"""
Unit and adversarial test suite for Source Fire Protection Deluge Valve & Open Nozzle Water Spray Shadow Authority.
"""

import pytest
from pb_source_fire_deluge_valve_nozzle_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    FireDelugeValveNozzleCallout,
    snap_point,
    parse_fire_deluge_valve_nozzle_callout,
    evaluate_fire_deluge_valve_nozzle_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_deluge_valve_basic():
    text = "TRANSFORMER DELUGE SYSTEM DN150 DELUGE VALVE WITH 24V SOLENOID RELEASE AND EMERGENCY MANUAL PULL STATION"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["component_category"] == "DELUGE_VALVE_SET"
    assert parsed["valve_diameter_mm"] == 150.0
    assert parsed["actuation_mode"] == "SOLENOID_ELECTRIC_RELEASE"
    assert parsed["manual_release_included"] is True


def test_parse_spray_nozzle_basic():
    text = "HIGH VELOCITY SPRAY WATER SPRAY NOZZLE K23 90 DEG OPEN NOZZLE SPRAY"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["component_category"] == "OPEN_WATER_SPRAY_NOZZLE"
    assert parsed["nozzle_k_factor"] == 23.0
    assert parsed["spray_angle_deg"] == 90.0


def test_parse_combined_deluge_array():
    text = "DELUGE SYSTEM DN100 DELUGE VALVE WITH OPEN SPRAY PROJECTOR K44 120 DEG PNEUMATIC PILOT LINE"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["component_category"] == "COMBINED_DELUGE_ARRAY"
    assert parsed["valve_diameter_mm"] == 100.0
    assert parsed["actuation_mode"] == "PNEUMATIC_DRY_PILOT"
    assert parsed["nozzle_k_factor"] == 44.0
    assert parsed["spray_angle_deg"] == 120.0


def test_parse_unrelated():
    assert parse_fire_deluge_valve_nozzle_callout("ALUMINIUM WINDOW FRAME") is None
    assert parse_fire_deluge_valve_nozzle_callout("CARPET TILES FINISH") is None


def test_evaluate_deluge_shadow_single():
    callouts = ["DELUGE VALVE DN100"]
    positions = [(10.1, 20.2)]
    results = evaluate_fire_deluge_valve_nozzle_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_deluge_shadow_dict():
    items = [{"text": "WATER SPRAY NOZZLE K80", "position": (5.0, 7.6)}]
    results = evaluate_fire_deluge_valve_nozzle_shadow(items)
    assert len(results) == 1
    assert results[0].nozzle_k_factor == 80.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_deluge_shadow_no_positions():
    results = evaluate_fire_deluge_valve_nozzle_shadow(["MEDIUM VELOCITY NOZZLE"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_deluge_shadow_safety_cap():
    huge_input = ["DELUGE VALVE"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_fire_deluge_valve_nozzle_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_fire_deluge_valve_nozzle_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "DELUGE VALVE DN100", "ROOM 101"]
    results = evaluate_fire_deluge_valve_nozzle_shadow(items)
    assert len(results) == 1
    assert results[0].valve_diameter_mm == 100.0


def test_hydraulic_wet_pilot():
    text = "DELUGE VALVE DN80 WITH WET PILOT LINE"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["actuation_mode"] == "HYDRAULIC_WET_PILOT"
    assert parsed["valve_diameter_mm"] == 80.0


def test_deluge_skid_trigger():
    text = "DELUGE SKID WITH MANUAL TRIP"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["manual_release_included"] is True


def test_default_values():
    text = "DELUGE SYSTEM"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["valve_diameter_mm"] == 100.0
    assert parsed["actuation_mode"] == "SOLENOID_ELECTRIC_RELEASE"
    assert parsed["nozzle_k_factor"] == 44.0
    assert parsed["spray_angle_deg"] == 120.0
    assert parsed["manual_release_included"] is True


def test_snapping_precision():
    callouts = ["OPEN NOZZLE SPRAY"]
    positions = [(12.49, 13.76)]
    results = evaluate_fire_deluge_valve_nozzle_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_without_manual_negation():
    text = "DELUGE VALVE WITHOUT MANUAL RELEASE"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["manual_release_included"] is False


def test_k115_large_nozzle():
    text = "WATER SPRAY NOZZLE K115 60 DEG"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["nozzle_k_factor"] == 115.0
    assert parsed["spray_angle_deg"] == 60.0


def test_drain_down_deluge_trigger():
    text = "DRAIN DOWN DELUGE DN50"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["valve_diameter_mm"] == 50.0


def test_invalid_item_types():
    results = evaluate_fire_deluge_valve_nozzle_shadow([123, None, object()])
    assert results == []


def test_degree_symbol():
    text = "OPEN SPRAY PROJECTOR 90° K80"
    parsed = parse_fire_deluge_valve_nozzle_callout(text)
    assert parsed is not None
    assert parsed["spray_angle_deg"] == 90.0
