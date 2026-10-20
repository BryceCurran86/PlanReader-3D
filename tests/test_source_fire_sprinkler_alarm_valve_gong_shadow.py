"""Unit tests for Source Fire Sprinkler Alarm Check Valve & Water Motor Gong Shadow Authority."""

import pytest
from pb_source_fire_sprinkler_alarm_valve_gong_shadow import (
    SprinklerAlarmValveCandidate,
    snap_point,
    parse_sprinkler_alarm_valve_callout,
    evaluate_fire_sprinkler_alarm_valve_gong_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((12.4, 14.9)) == (12.5, 15.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_sprinkler_alarm_valve_callout_variable_retard():
    text = "WET ALARM VALVE DN150 WITH RETARD CHAMBER WATER MOTOR GONG AND PRESSURE SWITCH 1200 KPA"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["valve_configuration"] == "VARIABLE_PRESSURE_RETARD"
    assert parsed["valve_size_mm"] == 150.0
    assert parsed["retard_chamber_present"] is True
    assert parsed["water_motor_gong_present"] is True
    assert parsed["pressure_switch_present"] is True
    assert parsed["working_pressure_kpa"] == 1200.0


def test_parse_sprinkler_alarm_valve_callout_constant_pressure():
    text = "ALARM CHECK VALVE DN100 CONSTANT PRESSURE WITH MOTOR GONG"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["valve_configuration"] == "CONSTANT_PRESSURE"
    assert parsed["valve_size_mm"] == 100.0
    assert parsed["retard_chamber_present"] is False
    assert parsed["water_motor_gong_present"] is True


def test_parse_sprinkler_alarm_valve_callout_psi():
    text = "SPRINKLER ALARM VALVE 200MM 175 PSI WITH DN50 DRAIN"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["valve_size_mm"] == 200.0
    assert parsed["working_pressure_kpa"] == 1207.0
    assert parsed["main_drain_size_mm"] == 50.0


def test_parse_sprinkler_alarm_valve_callout_fip_interface():
    text = "ALARM CHECK VALVE WITH FIP INTERFACE"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["pressure_switch_present"] is True


def test_parse_sprinkler_alarm_valve_callout_unrelated():
    assert parse_sprinkler_alarm_valve_callout("HOT WATER STORAGE CYLINDER 300L") is None


def test_evaluate_fire_sprinkler_alarm_valve_gong_shadow_single():
    callouts = ["WET ALARM VALVE DN150 WITH RETARD CHAMBER"]
    positions = [(100.2, 200.4)]
    res = evaluate_fire_sprinkler_alarm_valve_gong_shadow("FP-101", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "FP-101_avg_001"
    assert c.sheet_id == "FP-101"
    assert c.position == (100.0, 200.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_fire_sprinkler_alarm_valve_gong_shadow_dict():
    c = SprinklerAlarmValveCandidate(
        candidate_id="FP-102_avg_001",
        sheet_id="FP-102",
        valve_configuration="VARIABLE_PRESSURE_RETARD",
        valve_size_mm=150.0,
        water_motor_gong_present=True,
        retard_chamber_present=True,
        pressure_switch_present=True,
        main_drain_size_mm=50.0,
        working_pressure_kpa=1200.0,
        position=(50.0, 50.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "FP-102_avg_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["valve_size_mm"] == 150.0


def test_evaluate_fire_sprinkler_alarm_valve_gong_shadow_no_positions():
    callouts = ["WET ALARM VALVE"]
    res = evaluate_fire_sprinkler_alarm_valve_gong_shadow("FP-103", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_fire_sprinkler_alarm_valve_gong_shadow_safety_cap():
    callouts = ["WET ALARM VALVE"] * 10
    res = evaluate_fire_sprinkler_alarm_valve_gong_shadow("FP-104", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_fire_sprinkler_alarm_valve_gong_shadow("FP-105", []) == []


def test_unrelated_callout_filtering():
    callouts = ["COPPER PIPE 20MM", "WET ALARM VALVE DN150"]
    res = evaluate_fire_sprinkler_alarm_valve_gong_shadow("FP-106", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "FP-106_avg_002"


def test_hydraulic_alarm_trigger():
    text = "SPRINKLER CONTROL VALVE WITH HYDRAULIC ALARM"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["water_motor_gong_present"] is True


def test_flow_switch_trigger():
    text = "ALARM CHECK VALVE WITH FLOW SWITCH"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["pressure_switch_present"] is True


def test_default_values():
    text = "SPRINKLER ALARM VALVE"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["valve_configuration"] == "CONSTANT_PRESSURE"
    assert parsed["valve_size_mm"] == 150.0
    assert parsed["water_motor_gong_present"] is False
    assert parsed["retard_chamber_present"] is False
    assert parsed["main_drain_size_mm"] == 50.0
    assert parsed["working_pressure_kpa"] == 1200.0


def test_snapping_precision():
    callouts = ["ALARM CHECK VALVE"]
    positions = [(4.9, 9.9)]
    res = evaluate_fire_sprinkler_alarm_valve_gong_shadow("FP-107", callouts, positions)
    assert res[0].position == (5.0, 10.0)


def test_1400_kpa_detection():
    text = "WET ALARM VALVE 1400 KPA"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["working_pressure_kpa"] == 1400.0


def test_retard_chamber_trigger():
    text = "RETARD CHAMBER ON ALARM RISER"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["retard_chamber_present"] is True
    assert parsed["valve_configuration"] == "VARIABLE_PRESSURE_RETARD"


def test_100mm_alarm_valve():
    text = "100MM ALARM VALVE"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["valve_size_mm"] == 100.0


def test_alarm_gong_keyword():
    text = "ALARM VALVE WITH ALARM GONG"
    parsed = parse_sprinkler_alarm_valve_callout(text)
    assert parsed is not None
    assert parsed["water_motor_gong_present"] is True
