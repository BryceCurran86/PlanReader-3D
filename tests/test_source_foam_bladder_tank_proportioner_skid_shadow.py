"""
tests/test_source_foam_bladder_tank_proportioner_skid_shadow.py

Comprehensive test suite for fire protection foam-water deluge systems, bladder tanks,
ratio controllers, proportioner skids, and high-expansion foam generators.
"""

import pytest
from pb_source_foam_bladder_tank_proportioner_skid_shadow import (
    FoamBladderTankCandidate,
    extract_foam_bladder_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_vertical_bladder_tank_proportioner_extraction():
    prims = [{
        "id": "p1",
        "text": "Vertical Foam Bladder Tank FBT-01 3000L Capacity 3% Ratio Controller DN100 Fluorine-Free SFFF Foam 1725 kPa",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "VERTICAL_BLADDER_TANK_PROPORTIONER"
    assert cand.tank_capacity_liters == 3000
    assert cand.proportioning_ratio_percent == 3
    assert cand.ratio_controller_size_mm == 100
    assert cand.foam_concentrate_type == "FLUORINE_FREE_SFFF"
    assert cand.design_pressure_kpa == 1725
    assert cand.has_water_actuated_foam_valve is True
    assert cand.tag == "FBT-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_horizontal_bladder_tank():
    prims = [{
        "id": "p2",
        "text": "Horizontal Foam Bladder Tank FBT-02 5000L with 1% Ratio Controller DN150 AR-AFFF",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "HORIZONTAL_BLADDER_TANK_PROPORTIONER"
    assert cand.tank_capacity_liters == 5000
    assert cand.proportioning_ratio_percent == 1
    assert cand.ratio_controller_size_mm == 150
    assert cand.foam_concentrate_type == "AR_AFFF_ALCOHOL_RESISTANT"
    assert cand.tag == "FBT-02"


def test_foam_water_deluge_valve_skid():
    prims = [{
        "id": "p3",
        "text": "Foam-Water Deluge Valve Skid FDV-03 DN150 with Hydraulic Concentrate Control Valve 1600 kPa",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "FOAM_WATER_DELUGE_VALVE_SKID"
    assert cand.ratio_controller_size_mm == 150
    assert cand.design_pressure_kpa == 1600
    assert cand.tag == "FDV-03"


def test_inline_balanced_pressure_proportioner():
    prims = [{
        "id": "p4",
        "text": "In-line Balanced Pressure Proportioner Skid FPS-04 DN200 Wide Range Proportioner",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "INLINE_BALANCED_PRESSURE_PROPORTIONER"
    assert cand.ratio_controller_size_mm == 200
    assert cand.tag == "FPS-04"


def test_high_expansion_foam_generator():
    prims = [{
        "id": "p5",
        "text": "High Expansion Foam Generator HFG-05 Aircraft Hangar Total Flooding 500:1 Expansion",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "HIGH_EXPANSION_FOAM_GENERATOR"
    assert cand.tank_capacity_liters == 0
    assert cand.foam_concentrate_type == "HIGH_EXPANSION_DETERGENT"
    assert cand.tag == "HFG-05"


def test_bar_pressure_conversion():
    prims = [{
        "id": "p6",
        "text": "Foam Bladder Tank 16 bar Working Pressure",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 1
    assert results[0].design_pressure_kpa == 1600


def test_negative_lookalike_domestic_expansion_tank():
    prims = [{
        "id": "neg1",
        "text": "Domestic Potable Water Expansion Tank 50L Potable Diaphragm",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_foam_bladder_candidates(prims) == []


def test_negative_lookalike_spray_foam():
    prims = [{
        "id": "neg2",
        "text": "Spray Foam Insulation Polyurethane Closed Cell",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_foam_bladder_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Bladder Tank FBT-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_foam_bladder_candidates(prims)


def test_empty_primitives():
    assert extract_foam_bladder_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Timber Floor Joist 240x45 LVL", "x": 0.0, "y": 0.0}
    ]
    assert extract_foam_bladder_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Bladder Tank FBT-01", "x": 10.0, "y": 20.0}]
    cand = extract_foam_bladder_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Bladder Tank FBT_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Proportioner Skid FPS-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Deluge Valve FDV_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "FBT_10"
    assert results[1].tag == "FPS-04"
    assert results[2].tag == "FDV_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Foam Bladder Tank", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Foam Bladder Tank FBT-01 2000L Capacity 3% Ratio Controller",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_foam_bladder_candidates(prims_simple)[0]
    cand_rich = extract_foam_bladder_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Foam Bladder Tank Assembly", "x": 0.0, "y": 0.0}]
    cand = extract_foam_bladder_candidates(prims)[0]
    assert cand.tank_capacity_liters == 2000
    assert cand.proportioning_ratio_percent == 3
    assert cand.ratio_controller_size_mm == 100
    assert cand.foam_concentrate_type == "FLUORINE_FREE_SFFF"
    assert cand.design_pressure_kpa == 1725
    assert cand.tag is None


def test_6_percent_ratio():
    prims = [{
        "id": "r6",
        "text": "Foam Bladder Tank 6% Proportioning Ratio",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_foam_bladder_candidates(prims)[0]
    assert cand.proportioning_ratio_percent == 6


def test_psi_pressure_conversion():
    prims = [{
        "id": "psi1",
        "text": "Foam Deluge Skid 250 PSI Rated",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_foam_bladder_candidates(prims)[0]
    # 250 * 6.89476 = 1723 kPa
    assert cand.design_pressure_kpa == 1723


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Bladder Tank 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Bladder Tank 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_foam_bladder_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_tank_capacity_10000l():
    prims = [{
        "id": "cap1",
        "text": "Horizontal Bladder Tank 10000 Litres FBT-100",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_foam_bladder_candidates(prims)[0]
    assert cand.tank_capacity_liters == 10000


def test_dn80_ratio_controller():
    prims = [{
        "id": "rc1",
        "text": "Foam Proportioner Skid DN80 FPS-08",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_foam_bladder_candidates(prims)[0]
    assert cand.ratio_controller_size_mm == 80
