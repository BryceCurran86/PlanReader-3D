"""
tests/test_source_glulam_clt_concealed_knife_plate_shadow.py

Comprehensive test suite for structural timber glulam and CLT concealed knife plate
connections, internal slotted steel blades, drift dowel pins, and standoff column bases.
"""

import pytest
from pb_source_glulam_clt_concealed_knife_plate_shadow import (
    KnifePlateCandidate,
    extract_knife_plate_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_concealed_beam_column_knife_plate_extraction():
    prims = [{
        "id": "p1",
        "text": "Glulam Beam-Column Connection KP-01 with 12mm Thk Internal Slotted Knife Plate and 8x16 Dowels 60min Fire",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CONCEALED_BEAM_COLUMN_KNIFE_PLATE"
    assert cand.plate_thickness_mm == 12
    assert cand.num_knife_slots == 1
    assert cand.dowel_diameter_mm == 16
    assert cand.num_dowels == 8
    assert cand.fire_rating_minutes == 60
    assert cand.standoff_height_mm == 0
    assert cand.tag == "KP-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_concealed_column_base_knife_plate():
    prims = [{
        "id": "p2",
        "text": "Glulam Column Base Knife Plate CBP-02 16mm Plate with 75mm Standoff Boot",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CONCEALED_COLUMN_BASE_KNIFE_PLATE"
    assert cand.plate_thickness_mm == 16
    assert cand.standoff_height_mm == 75
    assert cand.tag == "CBP-02"


def test_clt_shear_panel_splice():
    prims = [{
        "id": "p3",
        "text": "CLT Connector Panel Shear Splice Knife Plate CLTK-03 10mm Steel Blade",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CLT_SHEAR_PANEL_SPLICE_PLATE"
    assert cand.plate_thickness_mm == 10
    assert cand.tag == "CLTK-03"


def test_truss_node_multiaxial_knife_plate():
    prims = [{
        "id": "p4",
        "text": "Glulam Timber Truss Node Multiaxial Knife Plate TCP-04 Double Blade",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "TRUSS_NODE_MULTIAXIAL_KNIFE_PLATE"
    assert cand.num_knife_slots == 2
    assert cand.tag == "TCP-04"


def test_tension_tie_hold_down_blade():
    prims = [{
        "id": "p5",
        "text": "Mass Timber Tension Tie Hold Down Blade Uplift Connection KP-05",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "TENSION_TIE_HOLD_DOWN_BLADE"
    assert cand.tag == "KP-05"


def test_triple_blade_slot():
    prims = [{
        "id": "p6",
        "text": "Glulam Knife Plate Triple Blade 20mm Plate 12x20 Dowels",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.num_knife_slots == 3
    assert cand.plate_thickness_mm == 20
    assert cand.num_dowels == 12
    assert cand.dowel_diameter_mm == 20


def test_negative_lookalike_steel_beam_to_steel():
    prims = [{
        "id": "neg1",
        "text": "Steel Beam to Steel Column Welded Shear Tab Connection",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_knife_plate_candidates(prims) == []


def test_negative_lookalike_drywall_stud():
    prims = [{
        "id": "neg2",
        "text": "Drywall Stud Knife Edge Trim Aluminum Profile",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_knife_plate_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Knife Plate KP-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_knife_plate_candidates(prims)


def test_empty_primitives():
    assert extract_knife_plate_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Acoustic Wall Insulation Batts R2.5", "x": 0.0, "y": 0.0}
    ]
    assert extract_knife_plate_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Knife Plate KP-01", "x": 10.0, "y": 20.0}]
    cand = extract_knife_plate_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Knife Plate KP_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Column Base CBP-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Truss Connector TCP_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "KP_10"
    assert results[1].tag == "CBP-04"
    assert results[2].tag == "TCP_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Knife Plate Connection", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Concealed Knife Plate KP-01 12mm Plate 8x16 Dowels",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_knife_plate_candidates(prims_simple)[0]
    cand_rich = extract_knife_plate_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Timber Slotted Knife Plate Connection", "x": 0.0, "y": 0.0}]
    cand = extract_knife_plate_candidates(prims)[0]
    assert cand.plate_thickness_mm == 12
    assert cand.num_knife_slots == 1
    assert cand.dowel_diameter_mm == 16
    assert cand.num_dowels == 8
    assert cand.fire_rating_minutes == 60
    assert cand.standoff_height_mm == 0
    assert cand.tag is None


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Knife Plate 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Knife Plate 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_knife_plate_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_frl_90_min():
    prims = [{
        "id": "f1",
        "text": "Concealed Knife Plate 90 min fire rating char layer",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_knife_plate_candidates(prims)[0]
    assert cand.fire_rating_minutes == 90


def test_single_slot_specification():
    prims = [{
        "id": "s1",
        "text": "Single Slot Knife Plate KP-11",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_knife_plate_candidates(prims)[0]
    assert cand.num_knife_slots == 1


def test_standoff_boot_default_for_column_base():
    prims = [{
        "id": "cb1",
        "text": "Concealed Column Base Knife Plate",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_knife_plate_candidates(prims)[0]
    assert cand.element_type == "CONCEALED_COLUMN_BASE_KNIFE_PLATE"
    assert cand.standoff_height_mm == 50


def test_glulam_tag_prefix():
    prims = [{
        "id": "gl1",
        "text": "Glulam Connection GLK-05 with Internal Steel Blade",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_knife_plate_candidates(prims)[0]
    assert cand.tag == "GLK-05"
