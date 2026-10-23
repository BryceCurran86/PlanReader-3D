"""
Unit and adversarial test suite for Source Cold Water Booster Pump Variable Speed Hydro-Pneumatic Pressure Vessel Shadow Authority.
"""

import pytest
from pb_source_booster_pump_pressure_vessel_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    BoosterPumpPressureVesselCallout,
    snap_point,
    parse_booster_pump_pressure_vessel_callout,
    evaluate_booster_pump_pressure_vessel_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_booster_pump_basic():
    text = "COLD WATER BOOSTER PUMP SET DUPLEX VSD PUMP WITH 200L PN16 HYDRO-PNEUMATIC PRESSURE VESSEL DN80 MANIFOLD ON INERTIA BASE"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["pump_configuration"] == "DUPLEX_PUMP_SET"
    assert parsed["pressure_vessel_litres"] == 200.0
    assert parsed["pressure_rating"] == "PN16"
    assert parsed["control_mode"] == "VARIABLE_SPEED_DRIVE_VSD"
    assert parsed["manifold_diameter_mm"] == 80.0
    assert parsed["vibration_isolation"] is True


def test_parse_triplex_high_pressure():
    text = "POTABLE WATER BOOSTER TRIPLEX PUMP SET WITH 300L PN25 PRESSURE VESSEL DN100 HEADER"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["pump_configuration"] == "TRIPLEX_PUMP_SET"
    assert parsed["pressure_vessel_litres"] == 300.0
    assert parsed["pressure_rating"] == "PN25"
    assert parsed["manifold_diameter_mm"] == 100.0


def test_parse_simplex_pressure_switch():
    text = "PRESSURE BOOSTER SIMPLEX WITH 50L PN10 PRESSURE TANK FIXED SPEED PRESSURE SWITCH"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["pump_configuration"] == "SIMPLEX_PUMP_SET"
    assert parsed["pressure_vessel_litres"] == 50.0
    assert parsed["pressure_rating"] == "PN10"
    assert parsed["control_mode"] == "FIXED_SPEED_PRESSURE_SWITCH"


def test_parse_unrelated():
    assert parse_booster_pump_pressure_vessel_callout("FIRE SPRINKLER DRENCH HEAD") is None
    assert parse_booster_pump_pressure_vessel_callout("DUCTWORK SUPPLY REGISTER") is None


def test_evaluate_booster_pump_shadow_single():
    callouts = ["BOOSTER PUMP DUPLEX 100L"]
    positions = [(10.1, 20.2)]
    results = evaluate_booster_pump_pressure_vessel_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_booster_pump_shadow_dict():
    items = [{"text": "VSD PUMP SET 200L", "position": (5.0, 7.6)}]
    results = evaluate_booster_pump_pressure_vessel_shadow(items)
    assert len(results) == 1
    assert results[0].pressure_vessel_litres == 200.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_booster_pump_shadow_no_positions():
    results = evaluate_booster_pump_pressure_vessel_shadow(["WATER PRESSURE SET"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_booster_pump_shadow_safety_cap():
    huge_input = ["BOOSTER PUMP SET"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_booster_pump_pressure_vessel_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_booster_pump_pressure_vessel_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "BOOSTER PUMP DUPLEX", "ROOM 101"]
    results = evaluate_booster_pump_pressure_vessel_shadow(items)
    assert len(results) == 1
    assert results[0].pump_configuration == "DUPLEX_PUMP_SET"


def test_quadplex_configuration():
    text = "COLD WATER BOOSTER QUADPLEX PUMP SET"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["pump_configuration"] == "QUADPLEX_PUMP_SET"


def test_expansion_vessel_trigger():
    text = "EXPANSION VESSEL 500 LITRES PN16"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["pressure_vessel_litres"] == 500.0


def test_default_values():
    text = "BOOSTER PUMP"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["pump_configuration"] == "DUPLEX_PUMP_SET"
    assert parsed["pressure_vessel_litres"] == 100.0
    assert parsed["pressure_rating"] == "PN16"
    assert parsed["control_mode"] == "VARIABLE_SPEED_DRIVE_VSD"
    assert parsed["manifold_diameter_mm"] == 65.0
    assert parsed["vibration_isolation"] is True


def test_snapping_precision():
    callouts = ["PRESSURE VESSEL"]
    positions = [(12.49, 13.76)]
    results = evaluate_booster_pump_pressure_vessel_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_no_isolation_negation():
    text = "BOOSTER PUMP WITHOUT ISOLATION"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["vibration_isolation"] is False


def test_bar_rating():
    text = "PRESSURE BOOSTER 10 BAR"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["pressure_rating"] == "PN10"


def test_dn50_header():
    text = "BOOSTER PUMP SET DN50"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["manifold_diameter_mm"] == 50.0


def test_invalid_item_types():
    results = evaluate_booster_pump_pressure_vessel_shadow([123, None, object()])
    assert results == []


def test_diameter_symbol():
    text = "BOOSTER PUMP Ø80 MANIFOLD"
    parsed = parse_booster_pump_pressure_vessel_callout(text)
    assert parsed is not None
    assert parsed["manifold_diameter_mm"] == 80.0
