"""
Unit and adversarial test suite for Source Chilled Water Balancing & Modulating Control Valve Shadow Authority.
"""

import pytest
from pb_source_chw_balancing_control_valve_shadow import (
    ChwBalancingControlValveCallout,
    SourceChwBalancingControlValveShadowAuthority,
    parse_chw_balancing_control_valve_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_picv_complete():
    text = "CHW FCU-01: DN25 PICV PRESSURE INDEPENDENT CONTROL VALVE, 1.25 L/S, MIN DP 25 KPA, 0-10V MODULATING, SPRING RETURN NORMALLY CLOSED"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN25"
    assert res["valve_type"] == "PRESSURE_INDEPENDENT_CONTROL_VALVE_PICV"
    assert res["design_flow_lps"] == 1.25
    assert res["differential_pressure_kpa"] == 25.0
    assert res["actuator_signal"] == "0_10V_ANALOG"
    assert res["fail_safe_position"] == "SPRING_RETURN_NORMALLY_CLOSED"


def test_parse_3way_valve_digital():
    text = "CHILLED WATER: DN50 3-WAY MIXING CONTROL VALVE, 4.5 L/S, BACNET MS/TP DIGITAL ACTUATOR, FAIL OPEN"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN50"
    assert res["valve_type"] == "THREE_WAY_MODULATING_MIXING"
    assert res["design_flow_lps"] == 4.5
    assert res["actuator_signal"] == "BACNET_MODBUS_DIGITAL"
    assert res["fail_safe_position"] == "SPRING_RETURN_NORMALLY_OPEN"


def test_parse_2way_valve_current_loop():
    text = "AHU-04 CHW 2-WAY MODULATING VALVE DN80, 12.0 LPS, 4-20MA ACTUATOR"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN80"
    assert res["valve_type"] == "TWO_WAY_MODULATING"
    assert res["design_flow_lps"] == 12.0
    assert res["actuator_signal"] == "4_20MA_CURRENT_LOOP"


def test_parse_lpm_flow_conversion():
    text = "CHW BALANCING VALVE DN20, 30 L/MIN, 0-10V"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN20"
    assert res["design_flow_lps"] == 0.5


def test_parse_non_chw_returns_none():
    text = "DOMESTIC COLD WATER ISOLATION VALVE DN25"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is None


def test_parse_default_fallback():
    text = "CHW CONTROL VALVE"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN25"
    assert res["valve_type"] == "TWO_WAY_MODULATING"


def test_snap_point_regular():
    pt = snap_point(10.1, 19.9, snap_tol=2.5)
    assert pt == (10.0, 20.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(10.123, 19.456, snap_tol=0.0)
    assert pt == (10.123, 19.456)


def test_authority_processing_dedup():
    auth = SourceChwBalancingControlValveShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("CHW PICV DN25, 1.0 L/S", (10.0, 20.0)),
        ("CHW PICV DN25, 1.0 L/S", (10.2, 20.1)),  # duplicates after snap
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_authority_different_positions():
    auth = SourceChwBalancingControlValveShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("CHW PICV DN25, 1.0 L/S", (10.0, 20.0)),
        ("CHW PICV DN25, 1.0 L/S", (50.0, 80.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceChwBalancingControlValveShadowAuthority()
    oversized = [("CHW PICV DN25", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 50)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_invariance():
    auth = SourceChwBalancingControlValveShadowAuthority()
    res = auth.process_callouts([("CHW PICV DN32, 2.0 L/S", (100.0, 200.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_characterized_control_valve():
    text = "CHW CCV CHARACTERIZED BALL VALVE DN32, 2.5 L/S"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["valve_type"] == "CHARACTERIZED_CONTROL_BALL_VALVE"


def test_floating_actuator():
    text = "CHILLED WATER VALVE DN20, 3-POINT FLOATING CONTROL"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["actuator_signal"] == "FLOATING_3_POINT"


def test_fail_in_place():
    text = "CHW MODULATING VALVE DN50, NON-SPRING RETURN FAIL IN PLACE"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["fail_safe_position"] == "FAIL_IN_PLACE"


def test_empty_string():
    assert parse_chw_balancing_control_valve_callout("") is None


def test_fcu_control_valve():
    text = "FCU CONTROL VALVE DN20, 0.4 LPS"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["design_flow_lps"] == 0.4


def test_ahu_control_valve():
    text = "AHU CONTROL VALVE DN65, 8.0 L/SEC"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["design_flow_lps"] == 8.0


def test_dn100_large_chw_valve():
    text = "PRIMARY CHW 2-WAY VALVE DN100, 35.0 L/S, 40 KPA DP"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["differential_pressure_kpa"] == 40.0


def test_modbus_digital():
    text = "CHW PICV DN40, MODBUS DIGITAL ACTUATOR"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["actuator_signal"] == "BACNET_MODBUS_DIGITAL"


def test_picv_default_dp():
    text = "CHW PICV DN25, 0.8 L/S"
    res = parse_chw_balancing_control_valve_callout(text)
    assert res is not None
    assert res["differential_pressure_kpa"] == 20.0


def test_frozen_dataclass_immutability():
    callout = ChwBalancingControlValveCallout(
        raw_text="CHW",
        pipe_diameter_dn="DN25",
        valve_type="PICV",
        design_flow_lps=1.0,
        differential_pressure_kpa=20.0,
        actuator_signal="0_10V",
        fail_safe_position="NC",
    )
    with pytest.raises(Exception):
        callout.design_flow_lps = 2.0  # type: ignore
