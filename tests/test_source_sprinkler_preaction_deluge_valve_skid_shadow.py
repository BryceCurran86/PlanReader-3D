"""
tests/test_source_sprinkler_preaction_deluge_valve_skid_shadow.py

Comprehensive test suite for automatic sprinkler system pre-action and deluge
valve skids, trim stations, and release manifolds shadow authority.
"""

import pytest
from pb_source_sprinkler_preaction_deluge_valve_skid_shadow import (
    PreactionDelugeValveCandidate,
    extract_preaction_deluge_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_double_interlock_preaction_extraction():
    prims = [{
        "id": "p1",
        "text": "DN150 Double Interlock Pre-Action Valve Station PAV-01 (1600 kPa) with Solenoid & AMD",
        "x": 102.3,
        "y": 204.6
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "DOUBLE_INTERLOCK_PREACTION"
    assert cand.valve_size_mm == 150
    assert cand.pressure_rating_kpa == 1600
    assert cand.tag == "PAV-01"
    assert cand.has_solenoid_release is True
    assert cand.has_air_maintenance_device is True
    assert cand.supervisory_gas == "COMPRESSED_AIR"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_single_interlock_preaction_extraction():
    prims = [{
        "id": "p2",
        "text": "Single Interlock Preaction Valve Trim DN100 with Electric Actuation",
        "x": 50.0,
        "y": 60.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "SINGLE_INTERLOCK_PREACTION"
    assert cand.valve_size_mm == 100
    assert cand.actuation_type == "ELECTRIC_ONLY"


def test_deluge_valve_skid_extraction():
    prims = [{
        "id": "p3",
        "text": "Open Head Deluge Valve Skid DEL-02 DN200 2070 kPa Hydraulic Release with Water Motor Gong",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "DELUGE_VALVE_SKID"
    assert cand.valve_size_mm == 200
    assert cand.pressure_rating_kpa == 2070
    assert cand.tag == "DEL-02"
    assert cand.actuation_type == "HYDRAULIC"
    assert cand.has_water_motor_alarm_gong is True
    assert cand.supervisory_gas == "NONE"


def test_nitrogen_supervisory_gas():
    prims = [{
        "id": "p4",
        "text": "Double-Interlock Pre-action Station PAV-03 with High-Pressure Nitrogen Gas System",
        "x": 80.0,
        "y": 90.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    assert results[0].supervisory_gas == "NITROGEN"


def test_inch_pipe_size_conversion():
    prims = [{
        "id": "p5",
        "text": '4" Pre-Action Valve PAV-04 with Alarm Gong',
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    assert results[0].valve_size_mm == 100
    assert results[0].has_water_motor_alarm_gong is True


def test_negative_lookalike_domestic_prv():
    prims = [{
        "id": "neg1",
        "text": "Domestic Water Pressure Reducing Valve Only - Cold Supply",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 0


def test_negative_lookalike_standard_wet_alarm():
    prims = [{
        "id": "neg2",
        "text": "Standard Wet Alarm Valve Only (Non Preaction)",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 0


def test_grid_snapping_precision():
    x, y = 101.3, 203.7
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 102.5
    assert snapped[1] == 202.5


def test_non_interlock_system():
    prims = [{
        "id": "p6",
        "text": "Non-Interlock Preaction Valve Skid DN80 16 Bar",
        "x": 12.5,
        "y": 25.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    assert results[0].element_type == "NON_INTERLOCK_PREACTION"
    assert results[0].valve_size_mm == 80
    assert results[0].pressure_rating_kpa == 1600


def test_pressure_psi_conversion():
    prims = [{
        "id": "p7",
        "text": "Deluge Valve Station DVS-1 DN100 300 PSI Rated",
        "x": 5.0,
        "y": 10.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    # 300 psi * 6.89476 = 2068 kPa
    assert results[0].pressure_rating_kpa == 2068


def test_manual_emergency_actuation():
    prims = [{
        "id": "p8",
        "text": "Preaction Valve Station with Manual Emergency Release Handle",
        "x": 10.0,
        "y": 10.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    assert results[0].actuation_type == "MANUAL_EMERGENCY"


def test_pneumatic_only_actuation():
    prims = [{
        "id": "p9",
        "text": "Deluge Valve with Dry Pilot Pneumatic Only Actuation",
        "x": 10.0,
        "y": 10.0
    }]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 1
    assert results[0].actuation_type == "PNEUMATIC_ONLY"


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Preaction Valve", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_preaction_deluge_candidates(prims)


def test_empty_primitive_list():
    assert extract_preaction_deluge_candidates([]) == []


def test_blank_or_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Architectural Column Detail 400x400 RC", "x": 0.0, "y": 0.0}
    ]
    assert extract_preaction_deluge_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p10", "text": "Preaction Valve Station PAV-1", "x": 10.0, "y": 20.0}]
    cand = extract_preaction_deluge_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Preaction station tagged PAV-12", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Deluge station tagged DEL_9", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Preaction skid PA-03", "x": 0.0, "y": 0.0},
    ]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "PAV-12"
    assert results[1].tag == "DEL_9"
    assert results[2].tag == "PA-03"


def test_confidence_scoring_variations():
    prims_simple = [{"id": "c1", "text": "Preaction Valve", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Preaction Valve PAV-01 DN100 1600 kPa with AMD",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_preaction_deluge_candidates(prims_simple)[0]
    cand_rich = extract_preaction_deluge_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values_when_unspecified():
    prims = [{"id": "d1", "text": "Preaction Trim Station", "x": 0.0, "y": 0.0}]
    cand = extract_preaction_deluge_candidates(prims)[0]
    assert cand.valve_size_mm == 100
    assert cand.pressure_rating_kpa == 1725
    assert cand.tag is None
    assert cand.has_water_motor_alarm_gong is False


def test_deluge_without_gas_defaults_none():
    prims = [{"id": "d2", "text": "Open Deluge Valve Assembly", "x": 0.0, "y": 0.0}]
    cand = extract_preaction_deluge_candidates(prims)[0]
    assert cand.supervisory_gas == "NONE"


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Preaction Valve 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Preaction Valve 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_preaction_deluge_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id
