"""
tests/test_source_driven_precast_concrete_pile_splice_shadow.py

Comprehensive test suite for structural deep foundation driven precast concrete piles,
mechanical locking splices, hardened rock shoes, and pile cut-off starter assemblies.
"""

import pytest
from pb_source_driven_precast_concrete_pile_splice_shadow import (
    DrivenPileCandidate,
    extract_driven_pile_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_driven_precast_square_pile_extraction():
    prims = [{
        "id": "p1",
        "text": "Driven Precast Concrete Pile DP-01 350x350mm 12.0m Long Grade 60 MPa SWL 1200 kN with Chisel Rock Shoe & Mechanical Splice",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "DRIVEN_PRECAST_SQUARE_PILE"
    assert cand.pile_size_mm == 350
    assert cand.segment_length_m == 12.0
    assert cand.concrete_strength_mpa == 60
    assert cand.working_load_kn == 1200
    assert cand.shoe_type == "CHISEL_ROCK_SHOE"
    assert cand.splice_type == "MECHANICAL_LOCKING_PINS"
    assert cand.tag == "DP-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_mechanical_pile_splice_joint():
    prims = [{
        "id": "p2",
        "text": "Mechanical Pile Splice Joint PJ-02 400mm with Locking Pins",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "MECHANICAL_PILE_SPLICE_JOINT"
    assert cand.pile_size_mm == 400
    assert cand.tag == "PJ-02"


def test_driving_rock_shoe():
    prims = [{
        "id": "p3",
        "text": "Cast Steel Hardened Driving Rock Shoe Point 350mm Oslo Point",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "DRIVING_ROCK_SHOE_POINT"
    assert cand.shoe_type == "OSLO_POINT"


def test_pile_head_cutoff_assembly():
    prims = [{
        "id": "p4",
        "text": "Pile Cut-Off Head Assembly with Exposed Starter Bars into Pile Cap",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "PILE_HEAD_CUTOFF_ASSEMBLY"


def test_cylindrical_spun_concrete_pile():
    prims = [{
        "id": "p5",
        "text": "Spun Concrete Cylinder Pile PHC-05 500mm Dia 14.0m Length 80 MPa",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CYLINDRICAL_SPUN_CONCRETE_PILE"
    assert cand.pile_size_mm == 500
    assert cand.segment_length_m == 14.0
    assert cand.concrete_strength_mpa == 80
    assert cand.tag == "PHC-05"


def test_flat_steel_shoe():
    prims = [{
        "id": "p6",
        "text": "Driven Concrete Pile 300mm Flat Steel Driving Shoe Blunt",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 1
    assert results[0].shoe_type == "FLAT_STEEL_SHOE"


def test_welded_collar_splice():
    prims = [{
        "id": "p7",
        "text": "Precast Pile Splice Welded Steel Collar Band Joint",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 1
    assert results[0].splice_type == "WELDED_COLLAR"


def test_negative_lookalike_cfa_piling():
    prims = [{
        "id": "neg1",
        "text": "CFA Piling Continuous Flight Auger Bored In-situ Concrete",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_driven_pile_candidates(prims) == []


def test_negative_lookalike_carpet_pile():
    prims = [{
        "id": "neg2",
        "text": "Carpet Pile Height 12mm Cut Pile Broadloom",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_driven_pile_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Driven Pile DP-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_driven_pile_candidates(prims)


def test_empty_primitives():
    assert extract_driven_pile_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Aluminum Window Frame Section Detail", "x": 0.0, "y": 0.0}
    ]
    assert extract_driven_pile_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p8", "text": "Driven Pile DP-01", "x": 10.0, "y": 20.0}]
    cand = extract_driven_pile_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Driven Pile DP_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Pile Splice PJ-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Spun Pile PHC_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "DP_10"
    assert results[1].tag == "PJ-04"
    assert results[2].tag == "PHC_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Driven Pile", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Driven Precast Pile DP-01 350x350mm 60 MPa SWL 1200 kN",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_driven_pile_candidates(prims_simple)[0]
    cand_rich = extract_driven_pile_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Precast Concrete Pile Section", "x": 0.0, "y": 0.0}]
    cand = extract_driven_pile_candidates(prims)[0]
    assert cand.pile_size_mm == 350
    assert cand.segment_length_m == 12.0
    assert cand.concrete_strength_mpa == 60
    assert cand.working_load_kn == 1200
    assert cand.shoe_type == "CHISEL_ROCK_SHOE"
    assert cand.splice_type == "MECHANICAL_LOCKING_PINS"
    assert cand.tag is None


def test_single_length_no_splice():
    prims = [{
        "id": "sl1",
        "text": "Driven Concrete Pile Single Length No Splice Required",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_driven_pile_candidates(prims)[0]
    assert cand.splice_type == "NONE_SINGLE_LENGTH"


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Driven Pile 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Driven Pile 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_driven_pile_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_pile_size_250mm():
    prims = [{
        "id": "ps1",
        "text": "Driven Precast Pile 250mm Square DP-25",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_driven_pile_candidates(prims)[0]
    assert cand.pile_size_mm == 250


def test_working_load_2000kn():
    prims = [{
        "id": "wl1",
        "text": "Concrete Pile SWL = 2000 kN DP-50",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_driven_pile_candidates(prims)[0]
    assert cand.working_load_kn == 2000
