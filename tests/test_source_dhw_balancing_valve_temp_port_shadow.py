"""
Unit and adversarial test suite for Source Domestic Hot Water Recirculation Balancing Valve & Temperature Port Shadow Authority.
"""

import pytest
from pb_source_dhw_balancing_valve_temp_port_shadow import (
    DhwBalancingValveTempPortCallout,
    SourceDhwBalancingValveTempPortShadowAuthority,
    parse_dhw_balancing_valve_temp_port_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_thermal_balancing_valve_complete():
    text = "DHW RETURN: DN20 THERMAL BALANCING VALVE, 3.5 L/MIN, SET 60°C, WITH P/T TEST PLUGS AND AUTOMATIC LEGIONELLA DISINFECTION"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN20"
    assert res["valve_type"] == "THERMAL_BALANCING_VALVE"
    assert res["design_flow_lpm"] == 3.5
    assert res["set_temperature_deg_c"] == 60.0
    assert res["temperature_port_type"] == "PT_PRESSURE_TEMPERATURE_PLUG"
    assert res["disinfection_override"] == "AUTOMATIC_LEGIONELLA_DISINFECTION_BYPASS"


def test_parse_manual_circuit_setter():
    text = "HOT WATER RETURN: DN25 MANUAL CIRCUIT SETTER, 5.0 LPM, DIRECT IMMERSION WELL"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN25"
    assert res["valve_type"] == "MANUAL_CIRCUIT_SETTER_ORIFICE"
    assert res["design_flow_lpm"] == 5.0
    assert res["temperature_port_type"] == "DIRECT_IMMERSION_WELL"


def test_parse_dynamic_pressure_independent():
    text = "DHW RECIRCULATION: PRESSURE INDEPENDENT BALANCING VALVE DN32 WITH DIAL THERMOMETER"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN32"
    assert res["valve_type"] == "DYNAMIC_PRESSURE_INDEPENDENT"
    assert res["temperature_port_type"] == "DIAL_THERMOMETER_GAUGE"


def test_parse_autoflow_cartridge():
    text = "RETURN BALANCING VALVE: AUTOFLOW CARTRIDGE VALVE DN15, SET AT 58 DEG C"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN15"
    assert res["valve_type"] == "AUTOMATIC_CARTRIDGE_BALANCING"
    assert res["set_temperature_deg_c"] == 58.0


def test_parse_defaults():
    text = "DHW RETURN BALANCING VALVE"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN20"
    assert res["valve_type"] == "THERMAL_BALANCING_VALVE"
    assert res["design_flow_lpm"] == 2.0
    assert res["set_temperature_deg_c"] == 55.0
    assert res["temperature_port_type"] == "PT_PRESSURE_TEMPERATURE_PLUG"
    assert res["disinfection_override"] == "NONE"


def test_parse_unrelated_text_returns_none():
    assert parse_dhw_balancing_valve_temp_port_callout("PRECAST WALL EXPANSION JOINT") is None
    assert parse_dhw_balancing_valve_temp_port_callout("CEILING GRID T-BAR 24MM") is None


def test_snap_point_regular():
    pt = snap_point(24.3, 36.8, snap_tol=2.5)
    assert pt == (25.0, 37.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(24.34, 36.87, snap_tol=0.0)
    assert pt == (24.34, 36.87)


def test_authority_processing_batch():
    auth = SourceDhwBalancingValveTempPortShadowAuthority()
    candidates = [
        ("DHW RETURN BALANCING VALVE DN20", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("HOT WATER RETURN CIRCUIT SETTER DN25", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].pipe_diameter_dn == "DN25"


def test_safety_primitive_cap():
    auth = SourceDhwBalancingValveTempPortShadowAuthority()
    large_list = [("DHW RETURN BALANCING VALVE", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = DhwBalancingValveTempPortCallout(
        raw_text="SAMPLE",
        pipe_diameter_dn="DN20",
        valve_type="THERMAL_BALANCING_VALVE",
        design_flow_lpm=2.0,
        set_temperature_deg_c=55.0,
        temperature_port_type="PT_PRESSURE_TEMPERATURE_PLUG",
        disinfection_override="NONE",
    )
    with pytest.raises(Exception):
        callout.design_flow_lpm = 4.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   dhw recirculation: dn20 thermostatic balancing valve, 1.5 l/min   "
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN20"
    assert res["design_flow_lpm"] == 1.5


def test_mm_size_mapping_to_dn():
    text = "HOT WATER RETURN: 25MM BALANCING VALVE"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN25"


def test_custom_snap_tolerance():
    auth = SourceDhwBalancingValveTempPortShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("DHW RETURN BALANCING VALVE", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceDhwBalancingValveTempPortShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_manual_override_purge():
    text = "DHW BALANCING VALVE WITH MANUAL OVERRIDE PURGE LEVER"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["disinfection_override"] == "MANUAL_PURGE_OVERRIDE"


def test_dry_well_test_point():
    text = "DHW RETURN VALVE WITH DRY WELL SENSOR PORT"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["temperature_port_type"] == "INTEGRAL_DRY_WELL"


def test_binder_point_test_port():
    text = "BALANCING VALVE WITH BINDER POINT TEST PORTS"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["temperature_port_type"] == "PT_PRESSURE_TEMPERATURE_PLUG"


def test_mtcv_thermostatic_designation():
    text = "DHW RETURN: MTCV VALVE DN20 @ 60 DEG C"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["valve_type"] == "THERMAL_BALANCING_VALVE"
    assert res["set_temperature_deg_c"] == 60.0


def test_flow_litres_per_min():
    text = "DHW RECIRCULATION: 4.5 LITRES PER MIN"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["design_flow_lpm"] == 4.5


def test_adversarial_special_characters():
    text = "DHW RETURN @@@ [DN20] +++ (3.0 L/MIN) // 55°C *** PT PLUG ###"
    res = parse_dhw_balancing_valve_temp_port_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN20"
    assert res["design_flow_lpm"] == 3.0
    assert res["set_temperature_deg_c"] == 55.0
