"""
Tests for Source Emergency Eyewash & Safety Shower Thermostatic Mixing Valve (TMV) Shadow Authority.
"""

import pytest
from pb_source_emergency_shower_eyewash_tmv_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    EmergencyShowerEyewashTmvCallout,
    snap_point,
    parse_emergency_shower_eyewash_tmv_callout,
    extract_emergency_shower_eyewash_tmv_candidates,
    validate_emergency_shower_eyewash_tmv_system,
)


def test_snap_point_regular():
    pt = snap_point(56.2, 73.8, snap_tol=2.5)
    assert pt == (55.0, 75.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(56.2, 73.8, snap_tol=0.0)
    assert pt == (56.2, 73.8)


def test_parse_none_on_irrelevant_text():
    assert parse_emergency_shower_eyewash_tmv_callout("ALUMINUM WINDOW FLASHING") is None
    assert parse_emergency_shower_eyewash_tmv_callout("CARPET TILES OVER SCREED") is None
    assert parse_emergency_shower_eyewash_tmv_callout("ACOUSTIC CEILING PANEL") is None


def test_parse_combination_shower_eyewash_tmv():
    text = "COMBINATION EMERGENCY SHOWER AND EYEWASH WITH TEPID WATER TMV 95 L/MIN 28°C FAIL-SAFE COLD WATER BYPASS DN32"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["station_type"] == "COMBINATION_SHOWER_EYEWASH"
    assert parsed["tmv_capacity_lpm"] == 95.0
    assert parsed["temperature_setpoint_celsius"] == 28.0
    assert parsed["cold_water_bypass"] == "FAIL_SAFE_COLD_BYPASS"
    assert parsed["inlet_drain_dn"] == "DN32"


def test_parse_pedestal_eyewash_battery_room():
    text = "PEDESTAL EYEWASH STATION 25 LPM 25°C WITH FLOW SWITCH ALARM HORN FOR BATTERY CHARGING ROOM"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["station_type"] == "PEDESTAL_EYEWASH_STATION"
    assert parsed["tmv_capacity_lpm"] == 25.0
    assert parsed["temperature_setpoint_celsius"] == 25.0
    assert parsed["alarm_actuation"] == "FLOW_SWITCH_ALARM_HORN"
    assert parsed["service_hazard"] == "BATTERY_CHARGING_ROOM"


def test_parse_overhead_drench_shower_chemical_area():
    text = "OVERHEAD DRENCH SHOWER EMERGENCY TMV 115 L/M WITH HOT WATER SHUTOFF FOR CHEMICAL DOSING AREA"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["station_type"] == "OVERHEAD_DRENCH_SHOWER"
    assert parsed["tmv_capacity_lpm"] == 115.0
    assert parsed["cold_water_bypass"] == "POSITIVE_HOT_WATER_SHUTOFF"
    assert parsed["service_hazard"] == "CHEMICAL_DOSING_AREA"


def test_parse_wall_mounted_eye_face_wash():
    text = "WALL MOUNTED EYE/FACE WASH WITH STROBE ALARM BEACON DN25 SUPPLY FOR LABORATORY CORRIDOR"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["station_type"] == "WALL_MOUNTED_EYE_FACE_WASH"
    assert parsed["alarm_actuation"] == "STROBE_ALARM_BEACON"
    assert parsed["inlet_drain_dn"] == "DN25"
    assert parsed["service_hazard"] == "LABORATORY_CORRIDOR"


def test_parse_gpm_conversion():
    text = "SAFETY SHOWER EMERGENCY MIXING VALVE 30 GPM WITH BMS CONTACT"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["tmv_capacity_lpm"] == round(30.0 * 3.78541, 1)
    assert parsed["alarm_actuation"] == "BMS_SUPERVISORY_CONTACT"


def test_parse_inch_supply_pipe():
    text = "SAFETY EYEWASH WITH 1\" SUPPLY TMV"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["inlet_drain_dn"] == "DN25"


def test_extract_emergency_shower_eyewash_tmv_candidates():
    items = [
        ("COMBINATION EMERGENCY SHOWER AND EYEWASH 95 L/MIN", (100.2, 200.3)),
        ("TIMBER SKIRTING BOARD", (50.0, 50.0)),
        ("PEDESTAL EYEWASH STATION WITH FLOW SWITCH ALARM", (300.0, 400.0)),
    ]
    candidates = extract_emergency_shower_eyewash_tmv_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (100.0, 200.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"EMERGENCY SHOWER {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_emergency_shower_eyewash_tmv_candidates(items, max_cap=12)
    assert len(candidates) == 12


def test_system_validation_summary():
    items = [
        ("COMBINATION EMERGENCY SHOWER AND EYEWASH 95 L/MIN WITH STROBE", (10.0, 20.0)),
        ("PEDESTAL EYEWASH STATION WITH ALARM HORN", (30.0, 40.0)),
        ("OVERHEAD DRENCH SHOWER 115 L/M", (50.0, 60.0)),
    ]
    candidates = extract_emergency_shower_eyewash_tmv_candidates(items)
    summary = validate_emergency_shower_eyewash_tmv_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["alarmed_count"] == 2
    assert summary["tmv_sized_count"] == 2
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = EmergencyShowerEyewashTmvCallout(
        raw_text="SAMPLE",
        station_type="COMBINATION_SHOWER_EYEWASH",
        tmv_capacity_lpm=95.0,
        temperature_setpoint_celsius=28.0,
        cold_water_bypass="FAIL_SAFE_COLD_BYPASS",
        alarm_actuation="FLOW_SWITCH_ALARM_HORN",
        inlet_drain_dn="DN32",
        service_hazard="CHEMICAL_DOSING_AREA",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_emergency_shower_eyewash_tmv_candidates([])
    assert len(candidates) == 0
    summary = validate_emergency_shower_eyewash_tmv_system([])
    assert summary["total_candidates"] == 0
    assert summary["alarmed_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_emergency_shower_eyewash_tmv_callout("DOMESTIC BATHROOM SHOWER MIXER") is None
    assert parse_emergency_shower_eyewash_tmv_callout("DISABLED ACCESSIBLE TOILET BASIN") is None
    assert parse_emergency_shower_eyewash_tmv_callout("RAINWATER TANK PUMP") is None


def test_workshop_decontamination_service():
    text = "EMERGENCY SAFETY SHOWER FOR WORKSHOP DECONTAMINATION ZONE"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["service_hazard"] == "WORKSHOP_DECONTAMINATION"


def test_1_and_quarter_inch_supply():
    text = "TEPID WATER TMV 1-1/4\" INLET"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["inlet_drain_dn"] == "DN32"


def test_anti_scald_shutoff():
    text = "EMERGENCY TMV WITH ANTI-SCALD HOT WATER SHUTOFF"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["cold_water_bypass"] == "POSITIVE_HOT_WATER_SHUTOFF"


def test_degrees_c_variant():
    text = "SAFETY SHOWER TEPID TMV 30 DEGREES C"
    parsed = parse_emergency_shower_eyewash_tmv_callout(text)
    assert parsed is not None
    assert parsed["temperature_setpoint_celsius"] == 30.0
