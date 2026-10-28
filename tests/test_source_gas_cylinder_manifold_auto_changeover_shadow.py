"""
tests/test_source_gas_cylinder_manifold_auto_changeover_shadow.py

Comprehensive test suite for high-purity laboratory gas cylinder manifolds, automatic
changeover panels, point-of-use pressure stations, and ventilated gas cabinets.
"""

import pytest
from pb_source_gas_cylinder_manifold_auto_changeover_shadow import (
    GasManifoldCandidate,
    extract_gas_manifold_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_auto_changeover_gas_manifold_extraction():
    prims = [{
        "id": "p1",
        "text": "Nitrogen Auto-Changeover Gas Manifold ACM-01 2x2 Cylinders 200 bar inlet 7 bar outlet Grade 5.0 with Depletion Alarm",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "AUTO_CHANGEOVER_GAS_MANIFOLD"
    assert cand.gas_service == "NITROGEN"
    assert cand.num_cylinders == 4
    assert cand.inlet_pressure_bar == 200
    assert cand.outlet_pressure_bar == 7
    assert cand.purity_grade == "GRADE_5_0"
    assert cand.has_auto_purge_assembly is True
    assert cand.has_alarm_annunciator is True
    assert cand.tag == "ACM-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_point_of_use_regulator():
    prims = [{
        "id": "p2",
        "text": "Helium Point-of-Use Regulator Panel POU-02 Bench Mount with Needle Valve",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "POINT_OF_USE_REGULATOR_PANEL"
    assert cand.gas_service == "HELIUM"
    assert cand.tag == "POU-02"


def test_toxic_gas_safety_cabinet():
    prims = [{
        "id": "p3",
        "text": "Hydrogen Toxic Gas Safety Cabinet GC-03 Exhausted Enclosure with Automatic Purge & Leak Detector",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "TOXIC_GAS_SAFETY_CABINET"
    assert cand.gas_service == "HYDROGEN"
    assert cand.has_auto_purge_assembly is True
    assert cand.has_alarm_annunciator is True
    assert cand.tag == "GC-03"


def test_external_gas_cylinder_cage():
    prims = [{
        "id": "p4",
        "text": "External Gas Cylinder Cage 12 Bottles Storage Bank with Manifold Racks GCM-04",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "EXTERNAL_GAS_CYLINDER_CAGE"
    assert cand.num_cylinders == 12
    assert cand.tag == "GCM-04"


def test_manual_gas_manifold_argon():
    prims = [{
        "id": "p5",
        "text": "Argon Gas Cylinder Manifold 2x1 Cylinders Manual Header MGC-05",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "MANUAL_GAS_MANIFOLD"
    assert cand.gas_service == "ARGON"
    assert cand.num_cylinders == 2
    assert cand.tag == "MGC-05"


def test_grade_6_0_purity():
    prims = [{
        "id": "p6",
        "text": "Gas Manifold Grade 6.0 99.9999% Ultra Pure Nitrogen",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 1
    assert results[0].purity_grade == "GRADE_6_0"


def test_negative_lookalike_natural_gas_meter():
    prims = [{
        "id": "neg1",
        "text": "Natural Gas Meter and Regulator Assembly External Gas Train",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_gas_manifold_candidates(prims) == []


def test_negative_lookalike_bbq():
    prims = [{
        "id": "neg2",
        "text": "Domestic BBQ Gas Bottle Regulator Hose 9kg",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_gas_manifold_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Gas Manifold GCM-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_gas_manifold_candidates(prims)


def test_empty_primitives():
    assert extract_gas_manifold_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Plasterboard Partition Wall Detail 13mm", "x": 0.0, "y": 0.0}
    ]
    assert extract_gas_manifold_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Gas Manifold GCM-01", "x": 10.0, "y": 20.0}]
    cand = extract_gas_manifold_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Gas Manifold GCM_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Auto Changeover ACM-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Regulator Panel POU_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "GCM_10"
    assert results[1].tag == "ACM-04"
    assert results[2].tag == "POU_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Gas Manifold", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Auto Changeover Gas Manifold ACM-01 2x2 Cylinders Grade 5.0",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_gas_manifold_candidates(prims_simple)[0]
    cand_rich = extract_gas_manifold_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Gas Cylinder Manifold Header", "x": 0.0, "y": 0.0}]
    cand = extract_gas_manifold_candidates(prims)[0]
    assert cand.gas_service == "NITROGEN"
    assert cand.num_cylinders == 4
    assert cand.inlet_pressure_bar == 200
    assert cand.outlet_pressure_bar == 7
    assert cand.purity_grade == "GRADE_5_0"
    assert cand.tag is None


def test_carbon_dioxide_gas_service():
    prims = [{
        "id": "co2",
        "text": "Carbon Dioxide Gas Manifold GCM-07 with Heated Regulator",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_gas_manifold_candidates(prims)[0]
    assert cand.gas_service == "CARBON_DIOXIDE"


def test_oxygen_gas_service():
    prims = [{
        "id": "ox",
        "text": "Oxygen Gas Panel POU-08 Degreased Cleaned for O2 Service",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_gas_manifold_candidates(prims)[0]
    assert cand.gas_service == "OXYGEN"


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Gas Manifold 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Gas Manifold 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_gas_manifold_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_inlet_outlet_pressure_parsing():
    prims = [{
        "id": "pr1",
        "text": "Gas Manifold 300 bar inlet 4 bar outlet GCM-15",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_gas_manifold_candidates(prims)[0]
    assert cand.inlet_pressure_bar == 300
    assert cand.outlet_pressure_bar == 4


def test_specialty_mix():
    prims = [{
        "id": "sm1",
        "text": "Specialty Gas Manifold GCM-22 for GC-MS Calibration",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_gas_manifold_candidates(prims)[0]
    assert cand.gas_service == "SPECIALTY_MIX"
