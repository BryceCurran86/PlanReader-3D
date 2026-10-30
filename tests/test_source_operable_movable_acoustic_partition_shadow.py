"""
tests/test_source_operable_movable_acoustic_partition_shadow.py

Comprehensive test suite for architectural operable movable acoustic partition walls,
stacking pocket enclosures, pass-door inserts, and overhead structural tracks.
"""

import pytest
from pb_source_operable_movable_acoustic_partition_shadow import (
    OperableWallCandidate,
    extract_operable_wall_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_operable_acoustic_wall_run_extraction():
    prims = [{
        "id": "p1",
        "text": "Operable Acoustic Wall OW-01 Rw 52 100mm Panel 3000mm High High Pressure Laminate with Mechanical Retractable Seals",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "OPERABLE_ACOUSTIC_WALL_RUN"
    assert cand.acoustic_rating_rw_stc == 52
    assert cand.panel_thickness_mm == 100
    assert cand.panel_height_mm == 3000
    assert cand.surface_finish == "HIGH_PRESSURE_LAMINATE"
    assert cand.has_retractable_seals is True
    assert cand.suspension_type == "TOP_HUNG_OMNI_DIRECTIONAL"
    assert cand.tag == "OW-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_stacking_pocket_enclosure():
    prims = [{
        "id": "p2",
        "text": "Movable Wall Panel Stacking Pocket Enclosure SP-02 with Acoustic Pocket Door",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "STACKING_POCKET_ENCLOSURE"
    assert cand.tag == "SP-02"


def test_pass_door_insert_panel():
    prims = [{
        "id": "p3",
        "text": "Operable Partition Pass-Door Panel OP-03 Single Inset Exit Door with Panic Hardware",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "PASS_DOOR_INSERT_PANEL"
    assert cand.tag == "OP-03"


def test_overhead_structural_track():
    prims = [{
        "id": "p4",
        "text": "Overhead Track Structural Suspension OHT-04 Extruded Aluminum with Drop-Rod Unistrut Brackets",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "OVERHEAD_STRUCTURAL_TRACK"
    assert cand.tag == "OHT-04"


def test_motorized_electric_operable_wall():
    prims = [{
        "id": "p5",
        "text": "Motorized Electric Operable Wall Continuous Hinge 55 dB RW-05",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "MOTORIZED_ELECTRIC_OPERABLE_WALL"
    assert cand.acoustic_rating_rw_stc == 55


def test_fabric_acoustic_wrapped():
    prims = [{
        "id": "p6",
        "text": "Operable Partition Wall Fabric Acoustic Wrapped Finish",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 1
    assert results[0].surface_finish == "FABRIC_ACOUSTIC_WRAPPED"


def test_timber_veneer():
    prims = [{
        "id": "p7",
        "text": "Operable Wall Timber Veneer Natural Oak Finish",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 1
    assert results[0].surface_finish == "TIMBER_VENEER"


def test_negative_lookalike_standard_drywall():
    prims = [{
        "id": "neg1",
        "text": "Standard Drywall Stud Partition Wall 90mm Steel Studs",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_operable_wall_candidates(prims) == []


def test_negative_lookalike_fixed_glass():
    prims = [{
        "id": "neg2",
        "text": "Fixed Glass Partition 12mm Toughened Frameless",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_operable_wall_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Operable Wall OW-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_operable_wall_candidates(prims)


def test_empty_primitives():
    assert extract_operable_wall_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Concrete Core Wall Reinforcement Schedule", "x": 0.0, "y": 0.0}
    ]
    assert extract_operable_wall_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p8", "text": "Operable Wall OW-01", "x": 10.0, "y": 20.0}]
    cand = extract_operable_wall_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Operable Wall OW_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Movable Partition MAP-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Operable Panel OP_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "OW_10"
    assert results[1].tag == "MAP-04"
    assert results[2].tag == "OP_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Operable Wall", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Operable Wall OW-01 Rw 50 100mm Panel 3600mm High",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_operable_wall_candidates(prims_simple)[0]
    cand_rich = extract_operable_wall_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Operable Partition Wall System", "x": 0.0, "y": 0.0}]
    cand = extract_operable_wall_candidates(prims)[0]
    assert cand.acoustic_rating_rw_stc == 50
    assert cand.panel_thickness_mm == 100
    assert cand.panel_height_mm == 3000
    assert cand.surface_finish == "HIGH_PRESSURE_LAMINATE"
    assert cand.suspension_type == "TOP_HUNG_OMNI_DIRECTIONAL"
    assert cand.tag is None


def test_center_stack_suspension():
    prims = [{
        "id": "cs1",
        "text": "Operable Wall Center Stack Suspension System",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_operable_wall_candidates(prims)[0]
    assert cand.suspension_type == "TOP_HUNG_CENTER_STACK"


def test_magnetic_whiteboard_finish():
    prims = [{
        "id": "wb1",
        "text": "Operable Partition with Magnetic Whiteboard Writing Surface",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_operable_wall_candidates(prims)[0]
    assert cand.surface_finish == "MAGNETIC_WHITEBOARD"


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Operable Wall 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Operable Wall 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_operable_wall_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_stc_syntax():
    prims = [{
        "id": "stc1",
        "text": "Movable Wall STC = 48 Rating",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_operable_wall_candidates(prims)[0]
    assert cand.acoustic_rating_rw_stc == 48


def test_panel_thickness_125mm():
    prims = [{
        "id": "thk1",
        "text": "Operable Wall 125mm Thick Panel Acoustic Heavy Duty",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_operable_wall_candidates(prims)[0]
    assert cand.panel_thickness_mm == 125
