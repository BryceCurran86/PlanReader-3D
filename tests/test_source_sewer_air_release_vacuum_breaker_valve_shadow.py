"""
tests/test_source_sewer_air_release_vacuum_breaker_valve_shadow.py

Comprehensive test suite for civil sewer force main combination air valves,
vacuum breaker valves, isolation/flush assemblies, and valve chamber pits.
"""

import pytest
from pb_source_sewer_air_release_vacuum_breaker_valve_shadow import (
    SewerAirValveCandidate,
    extract_sewer_air_valve_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_sewage_combination_air_valve_extraction():
    prims = [{
        "id": "p1",
        "text": "Sewage Combination Air Valve CAV-01 DN80 PN16 Ductile Iron Epoxy Coated with Odor Control Filter & Flush Attachment",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_sewer_air_valve_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "SEWAGE_COMBINATION_AIR_VALVE"
    assert cand.valve_size_mm == 80
    assert cand.pressure_class_pn == 16
    assert cand.body_material == "DUCTILE_IRON_EPOXY_COATED"
    assert cand.has_odor_control_filter is True
    assert cand.has_backflush_assembly is True
    assert cand.tag == "CAV-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_vacuum_breaker_valve():
    prims = [{
        "id": "p2",
        "text": "Sewer Force Main Vacuum Breaker Valve VBV-02 DN100 PN10 316 Stainless Steel",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_sewer_air_valve_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "VACUUM_BREAKER_VALVE"
    assert cand.valve_size_mm == 100
    assert cand.pressure_class_pn == 10
    assert cand.body_material == "STAINLESS_STEEL_316"
    assert cand.tag == "VBV-02"


def test_air_valve_chamber_pit():
    prims = [{
        "id": "p3",
        "text": "Air Valve Pit AVP-03 1500mm Dia Precast Concrete Chamber with Vented Cover",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_sewer_air_valve_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "AIR_VALVE_CHAMBER_PIT"
    assert cand.pit_diameter_mm == 1500
    assert cand.tag == "AVP-03"


def test_sewage_air_release_valve():
    prims = [{
        "id": "p4",
        "text": "Sewage Air Release Valve SAV-04 DN50 PN25 Reinforced Nylon Body",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_sewer_air_valve_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "SEWAGE_AIR_RELEASE_VALVE"
    assert cand.valve_size_mm == 50
    assert cand.pressure_class_pn == 25
    assert cand.body_material == "REINFORCED_NYLON_POLYMERIC"
    assert cand.tag == "SAV-04"


def test_class_150_conversion():
    prims = [{
        "id": "p5",
        "text": "Sewer Air Valve SAV-05 DN150 Class 150 Flanged",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_sewer_air_valve_candidates(prims)
    assert len(results) == 1
    assert results[0].pressure_class_pn == 20


def test_negative_lookalike_hvac_diffuser():
    prims = [{
        "id": "neg1",
        "text": "HVAC Air Diffuser Supply 4-Way 600x600mm",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_sewer_air_valve_candidates(prims) == []


def test_negative_lookalike_pneumatic_actuator():
    prims = [{
        "id": "neg2",
        "text": "Pneumatic Actuator Solenoid Air Valve 24V DC",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_sewer_air_valve_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Sewer Air Valve SAV-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_sewer_air_valve_candidates(prims)


def test_empty_primitives():
    assert extract_sewer_air_valve_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Structural Steel Girder Schedule", "x": 0.0, "y": 0.0}
    ]
    assert extract_sewer_air_valve_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p6", "text": "Sewer Air Valve SAV-01", "x": 10.0, "y": 20.0}]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Sewer Air Valve SAV_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Combination Valve CAV-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Air Valve Pit AVP_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_sewer_air_valve_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "SAV_10"
    assert results[1].tag == "CAV-04"
    assert results[2].tag == "AVP_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Sewer Air Valve", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Sewage Combination Air Valve CAV-01 DN80 PN16",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_sewer_air_valve_candidates(prims_simple)[0]
    cand_rich = extract_sewer_air_valve_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Sewer Air Valve Assembly", "x": 0.0, "y": 0.0}]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    assert cand.valve_size_mm == 80
    assert cand.pressure_class_pn == 16
    assert cand.body_material == "DUCTILE_IRON_EPOXY_COATED"
    assert cand.pit_diameter_mm == 1200
    assert cand.tag is None
    assert cand.has_odor_control_filter is False


def test_activated_carbon_odor_filter():
    prims = [{
        "id": "of1",
        "text": "Sewage Combination Air Valve with Activated Carbon Filter",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    assert cand.has_odor_control_filter is True


def test_quick_connect_rinse_coupling():
    prims = [{
        "id": "rf1",
        "text": "Sewage Air Valve with Backflush Quick Connect Rinse Port",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    assert cand.has_backflush_assembly is True


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Sewer Air Valve 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Sewer Air Valve 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_sewer_air_valve_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_dn200_large_size():
    prims = [{
        "id": "s1",
        "text": "Sewage Combination Air Valve DN200 PN16 CAV-20",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    assert cand.valve_size_mm == 200


def test_pit_diameter_1800mm():
    prims = [{
        "id": "pd1",
        "text": "Sewer Air Valve Chamber Pit 1800mm Dia AVP-18",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    assert cand.pit_diameter_mm == 1800


def test_class_300_conversion():
    prims = [{
        "id": "p6",
        "text": "Sewage Air Valve Class 300 SAV-30",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    assert cand.pressure_class_pn == 40


def test_isolation_and_flush_assembly():
    prims = [{
        "id": "ifa1",
        "text": "Air Valve Isolation and Flush Assembly with Knife Gate Valve",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_sewer_air_valve_candidates(prims)[0]
    assert cand.element_type == "ISOLATION_AND_FLUSH_ASSEMBLY"
