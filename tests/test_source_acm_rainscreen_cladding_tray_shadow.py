"""Tests for Architectural Metal Composite Material (MCM) / ACM Rainscreen Cladding Shadow Authority."""

import pytest
from pb_source_acm_rainscreen_cladding_tray_shadow import (
    ACMRainscreenCandidate,
    extract_acm_rainscreen_items,
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


def test_acm_routed_cassette_tray():
    texts = [{
        "id": "acm_1",
        "text": "ACM-01 4mm Aluminium Composite Material Cassette Tray Non-Combustible Mineral Core A2 Open Joint Ventilated Rainscreen with 75mm Cavity",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "ACM-01"
    assert c.element_type == "CASSETTE_TRAY"
    assert c.panel_thickness_mm == 4
    assert c.core_material_type == "NON_COMBUSTIBLE_MINERAL"
    assert c.mounting_system == "CASSETTE_TRAY"
    assert c.rainscreen_joint_type == "OPEN_JOINT_VENTILATED"
    assert c.cavity_depth_mm == 75


def test_face_fixed_panel():
    texts = [{
        "id": "acm_2",
        "text": "MCM-02 4mm Metal Composite Panel Flat Sheet Face Fixed with Structural Rivets Sealed Joint",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "MCM-02"
    assert c.element_type == "FLAT_SHEET"
    assert c.mounting_system == "FACE_FIXED"
    assert c.rainscreen_joint_type == "SEALED_JOINT"


def test_solid_aluminium_plate():
    texts = [{
        "id": "acm_3",
        "text": "CLAD-03 3mm Solid Aluminium Panel Cassette Tray Rainscreen Cladding",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.core_material_type == "SOLID_ALUMINIUM"
    assert c.panel_thickness_mm == 3


def test_honeycomb_composite_panel():
    texts = [{
        "id": "acm_4",
        "text": "ACM-04 6mm Aluminium Honeycomb Core Composite Cassette Panel",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.core_material_type == "ALUMINIUM_HONEYCOMB"
    assert c.panel_thickness_mm == 6


def test_top_hat_subframe():
    texts = [{
        "id": "acm_5",
        "text": "TH-01 Extruded Aluminium Top Hat Subframe for ACM Cladding 50mm Cavity",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "SUBFRAME_TOP_HAT"
    assert c.cavity_depth_mm == 50


def test_helping_hand_bracket():
    texts = [{
        "id": "acm_6",
        "text": "HHB-02 Helping Hand Adjustable Wall Bracket for Rainscreen Cladding Subframe",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "HELPING_HAND_BRACKET"


def test_parapet_capping_flashing():
    texts = [{
        "id": "acm_7",
        "text": "CLAD-07 Aluminium Parapet Capping Flashing over ACM Rainscreen",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "FLASHING"


def test_tongue_and_groove_interlocking():
    texts = [{
        "id": "acm_8",
        "text": "ACM-08 Interlocking Tongue and Groove Aluminium Composite Plank Cladding",
        "coordinates": (120.0, 130.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.mounting_system == "TONGUE_AND_GROOVE"


def test_negative_lookalike_fibre_cement():
    texts = [{
        "id": "neg_1",
        "text": "CFC-01 Compressed Fibre Cement Sheet 9mm Facade",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_timber_shiplap():
    texts = [{
        "id": "neg_2",
        "text": "Western Red Cedar Timber Shiplap Weatherboard Cladding",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_terracotta():
    texts = [{
        "id": "neg_3",
        "text": "Terracotta Rainscreen Tile Facade System",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "acm_9",
        "text": "ACM-09 Aluminium Composite Cladding Panel",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "acm_10",
        "text": "ACM-10: 4mm ACM Cassette Tray",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "ACM-10"
    assert d["panel_thickness_mm"] == 4
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"acm_{i}", "text": "ACM-01 Cladding Panel", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_acm_rainscreen_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_acm_rainscreen_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Concrete slab on grade 150mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "acm_def",
        "text": "Aluminium Composite Rainscreen Cladding",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "ACM-ITEM"
    assert c.core_material_type == "NON_COMBUSTIBLE_MINERAL"
    assert c.mounting_system == "CASSETTE_TRAY"
    assert c.rainscreen_joint_type == "OPEN_JOINT_VENTILATED"


def test_alpolic_fr_brand_callout():
    texts = [{
        "id": "acm_brand",
        "text": "PNL-11 Alpolic/FR Fire Rated Cladding Panel 4mm Cassette",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_acm_rainscreen_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.core_material_type == "NON_COMBUSTIBLE_MINERAL"
    assert c.panel_thickness_mm == 4
