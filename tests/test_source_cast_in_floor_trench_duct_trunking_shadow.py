"""
tests/test_source_cast_in_floor_trench_duct_trunking_shadow.py

Comprehensive test suite for cast-in and in-screed electrical floor trench ducts,
multi-compartment trunking, service outlet boxes, and crossover junction boxes.
"""

import pytest
from pb_source_cast_in_floor_trench_duct_trunking_shadow import (
    FloorTrenchDuctCandidate,
    extract_floor_trench_duct_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_flush_floor_trunking_3_compartment_extraction():
    prims = [{
        "id": "p1",
        "text": "Flush Floor Trunking FT-01 300x38mm 3-Compartment Carpet Infill Tray",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "FLUSH_FLOOR_TRUNK_3_COMPARTMENT"
    assert cand.width_mm == 300
    assert cand.depth_mm == 38
    assert cand.num_compartments == 3
    assert cand.cover_type == "CARPET_INFILL_TRAY"
    assert cand.tag == "FT-01"
    assert cand.load_class == "MEDIUM_COMMERCIAL"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_2_compartment_trunking():
    prims = [{
        "id": "p2",
        "text": "Floor Trunking 2-Compartment 225x38mm FT-02 with Brass Trim",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "FLUSH_FLOOR_TRUNK_2_COMPARTMENT"
    assert cand.num_compartments == 2
    assert cand.cover_type == "FLUSH_BRASS_TRIM"
    assert cand.tag == "FT-02"


def test_service_outlet_box():
    prims = [{
        "id": "p3",
        "text": "Flush Service Outlet Box SOB-01 with 4x RJ45 and 2x Double GPO Carpet Flange",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "SERVICE_OUTLET_BOX"
    assert cand.tag == "SOB-01"


def test_intersection_junction_box():
    prims = [{
        "id": "p4",
        "text": "Floor Trunking Junction Box JB-03 350x65mm with Flyover Segregation Bridge",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "INTERSECTION_JUNCTION_BOX"
    assert cand.has_flyover_bridge is True
    assert cand.tag == "JB-03"


def test_in_screed_floor_duct():
    prims = [{
        "id": "p5",
        "text": "In-Screed Floor Duct Run TD-04 225x38mm Screed Enclosed",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "IN_SCREED_FLOOR_DUCT"
    assert cand.cover_type == "SCREED_ENCLOSED"
    assert cand.tag == "TD-04"


def test_tile_infill_lid():
    prims = [{
        "id": "p6",
        "text": "Flush Floor Trench with Tile Infill Lid Stainless Steel Trim",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 1
    assert results[0].cover_type == "TILE_INFILL_LID"


def test_heavy_wheeled_load_class():
    prims = [{
        "id": "p7",
        "text": "Flush Floor Trench Heavy Wheeled Vehicle Loading Forklift Rated",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 1
    assert results[0].load_class == "HEAVY_WHEELED"


def test_negative_lookalike_civil_stormwater_trench():
    prims = [{
        "id": "neg1",
        "text": "Civil Grate Drain Stormwater Trench 300mm Wide",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_floor_trench_duct_candidates(prims) == []


def test_negative_lookalike_shower_waste():
    prims = [{
        "id": "neg2",
        "text": "Bathroom Shower Waste Linear Trench Grate",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_floor_trench_duct_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Floor Trunking FT-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_floor_trench_duct_candidates(prims)


def test_empty_primitives():
    assert extract_floor_trench_duct_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Gyprock Partition 90mm Stud Wall", "x": 0.0, "y": 0.0}
    ]
    assert extract_floor_trench_duct_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p8", "text": "Floor Trunking FT-01", "x": 10.0, "y": 20.0}]
    cand = extract_floor_trench_duct_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Floor Trench FT_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Junction Box JB-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Service Outlet SOB_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "FT_10"
    assert results[1].tag == "JB-04"
    assert results[2].tag == "SOB_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Floor Trunking", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Flush Floor Trunking FT-01 300x38mm 3-Compartment",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_floor_trench_duct_candidates(prims_simple)[0]
    cand_rich = extract_floor_trench_duct_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Floor Trunking Run", "x": 0.0, "y": 0.0}]
    cand = extract_floor_trench_duct_candidates(prims)[0]
    assert cand.width_mm == 300
    assert cand.depth_mm == 38
    assert cand.num_compartments == 3
    assert cand.load_class == "MEDIUM_COMMERCIAL"
    assert cand.tag is None


def test_light_pedestrian_loading():
    prims = [{
        "id": "l1",
        "text": "Flush Floor Duct Light Pedestrian Loading Domestic Office",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_floor_trench_duct_candidates(prims)[0]
    assert cand.load_class == "LIGHT_PEDESTRIAN"


def test_dimension_extraction_single_spec():
    prims = [{
        "id": "w1",
        "text": "Flush Floor Trunking 450mm Wide",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_floor_trench_duct_candidates(prims)[0]
    assert cand.width_mm == 450


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Floor Trunking 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Floor Trunking 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_floor_trench_duct_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_stainless_trim_cover():
    prims = [{
        "id": "s1",
        "text": "Floor Trunking with Stainless Trim Edge",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_floor_trench_duct_candidates(prims)[0]
    assert cand.cover_type == "FLUSH_STAINLESS_TRIM"
