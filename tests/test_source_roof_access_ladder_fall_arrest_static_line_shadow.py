"""Tests for Roof Access Ladder with Safety Cage & Fall-Arrest Static Line Shadow Authority."""

import pytest
from pb_source_roof_access_ladder_fall_arrest_static_line_shadow import (
    RoofAccessLadderCandidate,
    extract_roof_access_ladder_items,
    snap_point,
)


def test_snap_point_exact():
    pt = (100.0, 50.0)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 50.0)


def test_snap_point_offset():
    pt = (101.1, 51.9)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 52.5)


def test_caged_access_ladder_aluminium():
    texts = [{
        "id": "lad_1",
        "text": "RAL-01 Roof Access Ladder with Safety Cage 4200mm High Aluminium with Lockable Security Gate",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "RAL-01"
    assert c.element_type == "CAGED_ACCESS_LADDER"
    assert c.ladder_height_mm == 4200
    assert c.material == "STRUCTURAL_ALUMINIUM"
    assert c.has_safety_cage is True
    assert c.has_lockable_security_gate is True
    assert c.has_rest_platform is False


def test_uncaged_cat_ladder():
    texts = [{
        "id": "lad_2",
        "text": "LAD-02 Vertical Cat Ladder 2400mm High Hot Dip Galvanized Steel",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "LAD-02"
    assert c.element_type == "UNCAGED_LADDER"
    assert c.ladder_height_mm == 2400
    assert c.material == "HOT_DIP_GALVANIZED"
    assert c.has_safety_cage is False


def test_static_line_system_stainless():
    texts = [{
        "id": "lad_3",
        "text": "SL-03 Horizontal Fall Arrest Static Line System 45m Length Stainless Steel 316 Wire Rope",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "SL-03"
    assert c.element_type == "STATIC_LINE_SYSTEM"
    assert c.material == "STAINLESS_STEEL_316"
    assert c.static_line_length_m == 45.0


def test_roof_access_hatch():
    texts = [{
        "id": "lad_4",
        "text": "RAH-04 Weatherproof Roof Access Hatch 900x900mm with Gas Struts and Lockable Latch",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "ACCESS_HATCH"


def test_step_over_platform():
    texts = [{
        "id": "lad_5",
        "text": "SOP-05 Modular Aluminium Step-Over Platform over Parapet Wall with Guardrails",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "STEP_OVER_PLATFORM"
    assert c.material == "STRUCTURAL_ALUMINIUM"


def test_ladder_with_rest_platform():
    texts = [{
        "id": "lad_6",
        "text": "RAL-06 Caged Roof Access Ladder 6800mm High with Intermediate Rest Platform and Security Gate",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.ladder_height_mm == 6800
    assert c.has_safety_cage is True
    assert c.has_rest_platform is True
    assert c.has_lockable_security_gate is True


def test_negative_lookalike_portable_ladder():
    texts = [{
        "id": "neg_1",
        "text": "Portable Ladder 1.8m A-Frame Aluminium",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_cable_ladder():
    texts = [{
        "id": "neg_2",
        "text": "Cable Ladder 300mm Electrical Cable Tray HDG",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_precast_stair():
    texts = [{
        "id": "neg_3",
        "text": "Precast Stair Flight and Rebated Landing Bearing",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "lad_7",
        "text": "LAD-07 Roof Access Ladder",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "lad_8",
        "text": "LAD-08: 3500mm Caged Ladder",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "LAD-08"
    assert d["ladder_height_mm"] == 3500
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"lad_{i}", "text": "RAL-01 Roof Ladder", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_roof_access_ladder_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_roof_access_ladder_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Curtain track recessed in ceiling", "coordinates": (0.0, 0.0)}]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "lad_def",
        "text": "Roof Access Ladder Installation",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "LAD-ITEM"
    assert c.material == "STRUCTURAL_ALUMINIUM"
    assert c.has_safety_cage is False
    assert c.has_lockable_security_gate is False


def test_horizontal_lifeline_phrase():
    texts = [{
        "id": "lad_life",
        "text": "SL-09 Roof Horizontal Lifeline 25m Stainless 316",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "STATIC_LINE_SYSTEM"
    assert c.static_line_length_m == 25.0


def test_hot_dip_galvanized_cage():
    texts = [{
        "id": "lad_hdg",
        "text": "RAL-10 Caged Ladder 5000mm High Hot Dip Galvanized Steel",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.material == "HOT_DIP_GALVANIZED"
    assert c.ladder_height_mm == 5000
    assert c.has_safety_cage is True


def test_fall_arrest_system_tag():
    texts = [{
        "id": "lad_fa",
        "text": "SL-11 Fall Arrest Static Line Cable 60m",
        "coordinates": (8.0, 16.0)
    }]
    candidates = extract_roof_access_ladder_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "SL-11"
    assert c.element_type == "STATIC_LINE_SYSTEM"
    assert c.static_line_length_m == 60.0

