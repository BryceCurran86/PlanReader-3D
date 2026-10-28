"""
tests/test_source_motorized_smoke_damper_actuator_shadow.py

Comprehensive test suite for fire life safety smoke dampers, motorized combination
fire/smoke dampers (MFSD), Class I leakage cores, and fast-acting spring-return actuators.
"""

import pytest
from pb_source_motorized_smoke_damper_actuator_shadow import (
    MotorizedSmokeDamperCandidate,
    extract_motorized_smoke_damper_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_combination_fire_smoke_damper_extraction():
    prims = [{
        "id": "p1",
        "text": "Motorized Fire Smoke Damper MFSD-01 600x450mm 24V AC/DC 120min Fire Rated 15sec Closure with Auxiliary End Switches",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_motorized_smoke_damper_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "COMBINATION_FIRE_SMOKE_DAMPER"
    assert cand.width_mm == 600
    assert cand.height_mm == 450
    assert cand.actuator_voltage == "24V_AC_DC"
    assert cand.leakage_class == "CLASS_I"
    assert cand.closure_time_sec == 15
    assert cand.fire_rating_minutes == 120
    assert cand.has_end_switches is True
    assert cand.tag == "MFSD-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_leakage_class_i_smoke_damper():
    prims = [{
        "id": "p2",
        "text": "Smoke Damper SD-02 450x450mm Class I Ultra-Low Leakage 230V Actuator",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_motorized_smoke_damper_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "LEAKAGE_CLASS_I_SMOKE_DAMPER"
    assert cand.leakage_class == "CLASS_I"
    assert cand.actuator_voltage == "230V_AC"
    assert cand.tag == "SD-02"


def test_modulating_smoke_control_damper():
    prims = [{
        "id": "p3",
        "text": "Modulating Smoke Control Damper SCD-03 800x600mm 0-10V Positioner",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_motorized_smoke_damper_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "MODULATING_SMOKE_CONTROL_DAMPER"
    assert cand.width_mm == 800
    assert cand.height_mm == 600
    assert cand.tag == "SCD-03"


def test_thermal_disc_sensor_sleeve():
    prims = [{
        "id": "p4",
        "text": "Thermal Disc Sensor Sleeve TSD-04 with Test Switch & Indicator",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_motorized_smoke_damper_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "THERMAL_DISC_SENSOR_SLEEVE"
    assert cand.tag == "TSD-04"


def test_circular_spigot_diameter():
    prims = [{
        "id": "p5",
        "text": "Motorized Fire Damper FSD-05 300mm Dia Circular Spigot",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_motorized_smoke_damper_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.width_mm == 300
    assert cand.height_mm == 300


def test_negative_lookalike_gravity_backdraft():
    prims = [{
        "id": "neg1",
        "text": "Gravity Backdraft Damper Exhaust Wall Shutter",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_motorized_smoke_damper_candidates(prims) == []


def test_negative_lookalike_manual_volume_damper():
    prims = [{
        "id": "neg2",
        "text": "Manual Volume Damper VCD Only with Quadrant Lock",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_motorized_smoke_damper_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Smoke Damper SD-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_motorized_smoke_damper_candidates(prims)


def test_empty_primitives():
    assert extract_motorized_smoke_damper_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Suspended Ceiling Grid T-Bar 24mm", "x": 0.0, "y": 0.0}
    ]
    assert extract_motorized_smoke_damper_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p6", "text": "Smoke Damper SD-01", "x": 10.0, "y": 20.0}]
    cand = extract_motorized_smoke_damper_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Fire Damper MFSD_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Smoke Damper SD-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Control Damper SCD_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_motorized_smoke_damper_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "MFSD_10"
    assert results[1].tag == "SD-04"
    assert results[2].tag == "SCD_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Smoke Damper", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Fire Smoke Damper MFSD-01 600x450mm 120min Fire",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_motorized_smoke_damper_candidates(prims_simple)[0]
    cand_rich = extract_motorized_smoke_damper_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Motorized Fire Smoke Damper", "x": 0.0, "y": 0.0}]
    cand = extract_motorized_smoke_damper_candidates(prims)[0]
    assert cand.width_mm == 450
    assert cand.height_mm == 450
    assert cand.actuator_voltage == "24V_AC_DC"
    assert cand.leakage_class == "CLASS_I"
    assert cand.closure_time_sec == 15
    assert cand.fire_rating_minutes == 120
    assert cand.tag is None


def test_pneumatic_actuator():
    prims = [{
        "id": "pn1",
        "text": "Motorized Damper Pneumatic Actuator 80 PSI",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_motorized_smoke_damper_candidates(prims)[0]
    assert cand.actuator_voltage == "PNEUMATIC"


def test_class_ii_leakage():
    prims = [{
        "id": "cl2",
        "text": "Smoke Damper Class II Leakage Rated",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_motorized_smoke_damper_candidates(prims)[0]
    assert cand.leakage_class == "CLASS_II"


def test_frl_slash_format():
    prims = [{
        "id": "frl1",
        "text": "Fire Smoke Damper -/120/120 FRL",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_motorized_smoke_damper_candidates(prims)[0]
    assert cand.fire_rating_minutes == 120


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Smoke Damper 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Smoke Damper 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_motorized_smoke_damper_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_actuator_only():
    prims = [{
        "id": "ao1",
        "text": "Damper Actuator Only Fast Acting Spring Return",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_motorized_smoke_damper_candidates(prims)[0]
    assert cand.element_type == "FAST_ACTING_SPRING_RETURN_ACTUATOR"


def test_closure_time_extraction():
    prims = [{
        "id": "ct1",
        "text": "Smoke Damper 30 sec Closure Time",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_motorized_smoke_damper_candidates(prims)[0]
    assert cand.closure_time_sec == 30
