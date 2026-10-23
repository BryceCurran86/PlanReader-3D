"""
Unit and adversarial test suite for Source Elevator Shaft Smoke Relief Vent & Motorized Louver Shadow Authority.
"""

import pytest
from pb_source_elevator_smoke_relief_vent_shadow import (
    ElevatorSmokeReliefVentCallout,
    SourceElevatorSmokeReliefVentShadowAuthority,
    parse_elevator_smoke_relief_vent_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_motorized_smoke_louver():
    text = "LIFT OVERRUN ROOF: MOTORIZED HOISTWAY SMOKE RELIEF LOUVER 1000X800MM, 0.45 M2 AERODYNAMIC FREE AREA, 24V DC FAIL-SAFE SPRING OPEN ACTUATOR, DRAINABLE WEATHER BLADES"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["vent_type"] == "MOTORIZED_HOISTWAY_SMOKE_RELIEF_LOUVER"
    assert res["width_mm"] == 1000.0
    assert res["height_mm"] == 800.0
    assert res["aerodynamic_free_area_m2"] == 0.45
    assert res["actuator_operation"] == "FAIL_SAFE_SPRING_OPEN_24V_DC"
    assert res["blade_profile"] == "DRAINABLE_WEATHER_BLADE"


def test_parse_gravity_relief_vent():
    text = "ELEVATOR SHAFT: GRAVITY COUNTERBALANCED PRESSURE RELIEF VENT 900X600, CHEVRON ACOUSTIC BLADE"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["vent_type"] == "GRAVITY_COUNTERBALANCED_PRESSURE_RELIEF_VENT"
    assert res["width_mm"] == 900.0
    assert res["height_mm"] == 600.0
    assert res["blade_profile"] == "CHEVRON_ACOUSTIC_BLADE"


def test_parse_roof_cowl():
    text = "HOISTWAY ROOF UPSTAND VENT COWL 1200X1200, 0.72 SQM FREE AREA"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["vent_type"] == "ROOF_UPSTAND_VENT_COWL"
    assert res["width_mm"] == 1200.0
    assert res["height_mm"] == 1200.0
    assert res["aerodynamic_free_area_m2"] == 0.72


def test_parse_defaults():
    text = "HOISTWAY VENT"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["width_mm"] == 800.0
    assert res["height_mm"] == 600.0
    assert res["aerodynamic_free_area_m2"] == 0.24  # 800*600*1e-6*0.5


def test_parse_non_smoke_vent():
    text = "SPRINKLER FLOW SWITCH"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(49.2, 111.8, snap_tol=2.5)
    assert pt == (50.0, 112.5)


def test_authority_processing_dedup():
    auth = SourceElevatorSmokeReliefVentShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("HOISTWAY VENT 800X600", (10.0, 20.0)),
        ("HOISTWAY VENT 800X600", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceElevatorSmokeReliefVentShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("HOISTWAY VENT 800X600", (10.0, 20.0)),
        ("HOISTWAY VENT 800X600", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceElevatorSmokeReliefVentShadowAuthority()
    oversized = [("HOISTWAY VENT", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceElevatorSmokeReliefVentShadowAuthority()
    res = auth.process_callouts([("HOISTWAY VENT", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_elevator_smoke_relief_vent_callout("") is None


def test_pneumatic_actuator():
    text = "SHAFT SMOKE VENT WITH PNEUMATIC FAIL OPEN ACTUATION"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["actuator_operation"] == "PNEUMATIC_FAIL_OPEN"


def test_fusible_link():
    text = "SMOKE RELIEF LOUVER WITH MANUAL FUSIBLE LINK"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["actuator_operation"] == "MANUAL_FUSIBLE_LINK"


def test_zero_tolerance_snap():
    pt = snap_point(9.87, 6.54, snap_tol=0.0)
    assert pt == (9.87, 6.54)


def test_frozen_dataclass_immutability():
    callout = ElevatorSmokeReliefVentCallout(
        raw_text="text",
        vent_type="LOUVER",
        width_mm=800.0,
        height_mm=600.0,
        aerodynamic_free_area_m2=0.24,
        actuator_operation="24V",
        blade_profile="WEATHER",
    )
    with pytest.raises(Exception):
        callout.width_mm = 1000.0  # type: ignore


def test_different_dims_same_point():
    auth = SourceElevatorSmokeReliefVentShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("HOISTWAY VENT 800X600", (10.0, 20.0)),
        ("HOISTWAY VENT 1000X1000", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_lift_shaft_vent_trigger():
    text = "LIFT SHAFT VENT 600X600, 0.18 M2"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["width_mm"] == 600.0
    assert res["height_mm"] == 600.0
    assert res["aerodynamic_free_area_m2"] == 0.18


def test_pressure_relief_louver_trigger():
    text = "PRESSURE RELIEF LOUVER 1200X800"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["width_mm"] == 1200.0
    assert res["height_mm"] == 800.0


def test_sqm_free_area():
    text = "SMOKE VENT LOUVER 1500X1000, 0.75 SQ M FREE AREA"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["aerodynamic_free_area_m2"] == 0.75


def test_hoistway_relief_trigger():
    text = "HOISTWAY RELIEF 800X800"
    res = parse_elevator_smoke_relief_vent_callout(text)
    assert res is not None
    assert res["width_mm"] == 800.0
    assert res["height_mm"] == 800.0
