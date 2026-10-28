"""
tests/test_source_expansion_joint_cover_seismic_bellows_shadow.py

Comprehensive test suite for architectural expansion joint covers, seismic floor/wall
bellows, fire-rated barriers, and roof weather-seal joints.
"""

import pytest
from pb_source_expansion_joint_cover_seismic_bellows_shadow import (
    ExpansionJointCoverCandidate,
    extract_expansion_joint_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_seismic_floor_joint_cover_extraction():
    prims = [{
        "id": "p1",
        "text": "Seismic Floor Expansion Joint Cover SJC-01 100mm Gap +/- 50% Anodized Aluminum with Fire Blanket & Moisture Barrier",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_expansion_joint_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "SEISMIC_FLOOR_JOINT_COVER"
    assert cand.nominal_joint_gap_mm == 100
    assert cand.movement_capacity_percent == 50
    assert cand.cover_material == "ANODIZED_ALUMINUM"
    assert cand.has_fire_barrier is True
    assert cand.has_vapor_water_barrier is True
    assert cand.tag == "SJC-01"
    assert cand.load_rating == "PEDESTRIAN_STANDARD"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_flush_wall_joint_cover():
    prims = [{
        "id": "p2",
        "text": "Flush Wall Expansion Joint Cover WJC-02 50mm Gap Santoprene Elastomer",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_expansion_joint_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "FLUSH_WALL_JOINT_COVER"
    assert cand.cover_material == "SANTOPRENE_ELASTOMER"
    assert cand.tag == "WJC-02"


def test_ceiling_expansion_cover():
    prims = [{
        "id": "p3",
        "text": "Ceiling Expansion Joint Cover 75mm Gap Clip-In Concealed",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_expansion_joint_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CEILING_EXPANSION_COVER"
    assert cand.nominal_joint_gap_mm == 75


def test_roof_expansion_bellows():
    prims = [{
        "id": "p4",
        "text": "Roof Expansion Joint Bellows RJC-04 EPDM Weatherproof Membrane 150mm Gap",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_expansion_joint_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "ROOF_EXPANSION_BELLOWS"
    assert cand.cover_material == "WATERPROOF_EPDM"
    assert cand.has_vapor_water_barrier is True
    assert cand.tag == "RJC-04"


def test_heavy_forklift_loading():
    prims = [{
        "id": "p5",
        "text": "Floor Expansion Joint Heavy Forklift Steel Wheel Load Rated Stainless Steel Plate",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_expansion_joint_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.load_rating == "HEAVY_FORKLIFT_STEEL_WHEEL"
    assert cand.cover_material == "STAINLESS_STEEL"


def test_negative_lookalike_saw_cut():
    prims = [{
        "id": "neg1",
        "text": "Saw Cut Control Joint with Polyurethane Sealant Only",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_expansion_joint_candidates(prims) == []


def test_negative_lookalike_pipe_bellows():
    prims = [{
        "id": "neg2",
        "text": "Hydronic Pipe Bellows Axial Expansion Compensator",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_expansion_joint_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Expansion Joint EJC-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_expansion_joint_candidates(prims)


def test_empty_primitives():
    assert extract_expansion_joint_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Timber Skirting Board 100mm MDF", "x": 0.0, "y": 0.0}
    ]
    assert extract_expansion_joint_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p6", "text": "Expansion Joint EJC-01", "x": 10.0, "y": 20.0}]
    cand = extract_expansion_joint_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Expansion Joint EJC_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Seismic Joint SJC-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Floor Joint FJC_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_expansion_joint_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "EJC_10"
    assert results[1].tag == "SJC-04"
    assert results[2].tag == "FJC_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Expansion Joint Cover", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Expansion Joint Cover EJC-01 100mm Gap +/- 50%",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_expansion_joint_candidates(prims_simple)[0]
    cand_rich = extract_expansion_joint_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Floor Movement Joint", "x": 0.0, "y": 0.0}]
    cand = extract_expansion_joint_candidates(prims)[0]
    assert cand.nominal_joint_gap_mm == 50
    assert cand.movement_capacity_percent == 50
    assert cand.cover_material == "ANODIZED_ALUMINUM"
    assert cand.has_fire_barrier is False
    assert cand.tag is None


def test_fire_rated_blanket_barrier():
    prims = [{
        "id": "fb1",
        "text": "Expansion Joint Fire Blanket Barrier 2-Hour Rated Under-Slab",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_expansion_joint_candidates(prims)[0]
    assert cand.element_type == "FIRE_RATED_BLANKET_BARRIER"
    assert cand.has_fire_barrier is True


def test_pneumatic_tire_loading():
    prims = [{
        "id": "pt1",
        "text": "Floor Seismic Joint Car Parking Deck Pneumatic Tire Load Rated",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_expansion_joint_candidates(prims)[0]
    assert cand.load_rating == "PNEUMATIC_TIRE"


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Expansion Joint 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Expansion Joint 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_expansion_joint_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_extruded_bronze():
    prims = [{
        "id": "b1",
        "text": "Architectural Expansion Joint Extruded Bronze Architectural Finish",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_expansion_joint_candidates(prims)[0]
    assert cand.cover_material == "EXTRUDED_BRONZE"


def test_movement_capacity_100_percent():
    prims = [{
        "id": "m1",
        "text": "Seismic Expansion Joint SJC-05 +/- 100% Full Movement",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_expansion_joint_candidates(prims)[0]
    assert cand.movement_capacity_percent == 100


def test_gap_200mm():
    prims = [{
        "id": "g1",
        "text": "Expansion Joint Gap = 200mm EJC-20",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_expansion_joint_candidates(prims)[0]
    assert cand.nominal_joint_gap_mm == 200
