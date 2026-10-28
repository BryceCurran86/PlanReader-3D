"""
tests/test_source_compressed_air_rotary_screw_dryer_skid_shadow.py

Comprehensive test suite for industrial compressed air rotary screw compressors,
refrigerated and desiccant dryers, vertical receiver vessels, and total air skids.
"""

import pytest
from pb_source_compressed_air_rotary_screw_dryer_skid_shadow import (
    CompressedAirCandidate,
    extract_compressed_air_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_rotary_screw_air_compressor_extraction():
    prims = [{
        "id": "p1",
        "text": "Rotary Screw Air Compressor CMP-01 45 kW VSD Inverter 120 L/s at 8.0 bar working pressure",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "ROTARY_SCREW_AIR_COMPRESSOR"
    assert cand.motor_power_kw == 45.0
    assert cand.free_air_delivery_l_s == 120
    assert cand.working_pressure_bar == 8.0
    assert cand.is_variable_speed_drive is True
    assert cand.tag == "CMP-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_refrigerated_air_dryer():
    prims = [{
        "id": "p2",
        "text": "Refrigerated Air Dryer RAD-02 Cycling +3°C Dew Point ISO Class 4",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "REFRIGERATED_AIR_DRYER"
    assert cand.pressure_dew_point_c == 3
    assert cand.tag == "RAD-02"


def test_desiccant_air_dryer():
    prims = [{
        "id": "p3",
        "text": "Desiccant Air Dryer DAD-03 Heated Blower -40°C Dew Point",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "DESICCANT_AIR_DRYER"
    assert cand.pressure_dew_point_c == -40
    assert cand.tag == "DAD-03"


def test_vertical_air_receiver():
    prims = [{
        "id": "p4",
        "text": "Vertical Air Receiver Vessel ARV-04 1500L Pressure Tank with Safety Relief Valve",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "VERTICAL_AIR_RECEIVER_VESSEL"
    assert cand.receiver_volume_liters == 1500
    assert cand.tag == "ARV-04"


def test_compact_total_air_system_skid():
    prims = [{
        "id": "p5",
        "text": "Compressed Air Skid Package CAS-05 Total Air System 22 kW with Integrated Tank & Dryer",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "COMPACT_TOTAL_AIR_SYSTEM_SKID"
    assert cand.motor_power_kw == 22.0
    assert cand.tag == "CAS-05"


def test_hp_motor_power_conversion():
    prims = [{
        "id": "p6",
        "text": "Rotary Screw Compressor 50 HP 10 bar",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 1
    # 50 HP * 0.7457 = 37.3 kW
    assert results[0].motor_power_kw == 37.3
    assert results[0].working_pressure_bar == 10.0


def test_negative_lookalike_chiller_compressor():
    prims = [{
        "id": "neg1",
        "text": "Water Chiller Refrigerant Compressor R134a Semi-Hermetic",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_compressed_air_candidates(prims) == []


def test_negative_lookalike_vacuum_pump():
    prims = [{
        "id": "neg2",
        "text": "Medical Vacuum Pump System Duplex Rotary Vane",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_compressed_air_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Air Compressor CMP-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_compressed_air_candidates(prims)


def test_empty_primitives():
    assert extract_compressed_air_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Plaster Ceiling Cornice 90mm Cove", "x": 0.0, "y": 0.0}
    ]
    assert extract_compressed_air_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Screw Compressor CMP-01", "x": 10.0, "y": 20.0}]
    cand = extract_compressed_air_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Air Compressor CMP_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Refrigerated Dryer RAD-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Air Receiver ARV_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "CMP_10"
    assert results[1].tag == "RAD-04"
    assert results[2].tag == "ARV_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Screw Compressor", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Rotary Screw Air Compressor CMP-01 37 kW 8 bar",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_compressed_air_candidates(prims_simple)[0]
    cand_rich = extract_compressed_air_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Screw Compressor Station", "x": 0.0, "y": 0.0}]
    cand = extract_compressed_air_candidates(prims)[0]
    assert cand.motor_power_kw == 37.0
    assert cand.free_air_delivery_l_s == 100
    assert cand.working_pressure_bar == 8.0
    assert cand.is_variable_speed_drive is False
    assert cand.pressure_dew_point_c == 3
    assert cand.receiver_volume_liters == 1000
    assert cand.tag is None


def test_flow_rate_m3_min():
    prims = [{
        "id": "m3",
        "text": "Rotary Screw Compressor 6.0 m3/min FAD",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_compressed_air_candidates(prims)[0]
    # 6.0 * 1000 / 60 = 100 L/s
    assert cand.free_air_delivery_l_s == 100


def test_psi_pressure_conversion():
    prims = [{
        "id": "psi1",
        "text": "Air Compressor 145 PSI Working Pressure",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_compressed_air_candidates(prims)[0]
    # 145 * 0.0689476 = 10.0 bar
    assert cand.working_pressure_bar == 10.0


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Air Compressor 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Air Compressor 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_compressed_air_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_receiver_volume_500l():
    prims = [{
        "id": "rv1",
        "text": "Air Receiver Vessel 500L Tank AR-12",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_compressed_air_candidates(prims)[0]
    assert cand.receiver_volume_liters == 500


def test_dew_point_parsing():
    prims = [{
        "id": "dp1",
        "text": "Air Dryer +5°C Dew Point",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_compressed_air_candidates(prims)[0]
    assert cand.pressure_dew_point_c == 5
