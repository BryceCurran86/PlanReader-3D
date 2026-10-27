"""Tests for Commercial Kitchen Exhaust Hood Grease Filter & Ansul Fire Suppression Shadow Authority."""

import pytest
from pb_source_kitchen_hood_fire_suppression_ansul_shadow import (
    KitchenHoodCandidate,
    extract_kitchen_hood_items,
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


def test_type_1_grease_hood_ansul():
    texts = [{
        "id": "kh_1",
        "text": "KH-01 Commercial Kitchen Exhaust Canopy Hood 3000x1200mm Stainless Baffle Filters with Ansul R-102 Fire Suppression 1800 L/S Gas Interlock",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "KH-01"
    assert c.hood_type == "TYPE_1_GREASE_HOOD"
    assert c.length_mm == 3000
    assert c.width_mm == 1200
    assert c.filter_type == "BAFFLE_GREASE_FILTER"
    assert c.has_fire_suppression is True
    assert c.fire_suppression_brand == "ANSUL_R102"
    assert c.exhaust_airflow_lps == 1800
    assert c.has_gas_interlock is True


def test_type_2_condensate_hood():
    texts = [{
        "id": "kh_2",
        "text": "CKH-02 Dishwasher Condensate Hood Type 2 Steam Capture 1200x900mm 450 L/S No Fire Suppression",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "CKH-02"
    assert c.hood_type == "TYPE_2_CONDENSATE_HOOD"
    assert c.length_mm == 1200
    assert c.width_mm == 900
    assert c.exhaust_airflow_lps == 450
    assert c.has_fire_suppression is False


def test_island_canopy_hood():
    texts = [{
        "id": "kh_3",
        "text": "HOOD-03 Island Canopy Hood 3600x2000mm Stainless Baffle Grease Filters 2800 L/S Ansul System",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.hood_type == "ISLAND_CANOPY"
    assert c.length_mm == 3600
    assert c.width_mm == 2000
    assert c.exhaust_airflow_lps == 2800
    assert c.has_fire_suppression is True


def test_uv_c_odour_destruction():
    texts = [{
        "id": "kh_4",
        "text": "KH-04 Kitchen Exhaust Hood with UV-C Ozone Grease Destruction Cassettes",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.filter_type == "UV_C_SYSTEM"


def test_water_wash_canopy():
    texts = [{
        "id": "kh_5",
        "text": "EC-05 Exhaust Canopy with Automated Water Wash Manifold Cleaning",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.filter_type == "WATER_WASH"


def test_amerex_kp_system():
    texts = [{
        "id": "kh_6",
        "text": "KEH-06 Wall Mounted Canopy Kitchen Hood with Amerex KP Wet Chemical Fire Suppression",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.hood_type == "WALL_MOUNTED_CANOPY"
    assert c.has_fire_suppression is True
    assert c.fire_suppression_brand == "AMEREX_KP"


def test_mesh_filter_option():
    texts = [{
        "id": "kh_7",
        "text": "KH-07 Kitchen Hood Aluminium Mesh Filter Bank",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.filter_type == "MESH_FILTER"


def test_negative_lookalike_domestic_rangehood():
    texts = [{
        "id": "neg_1",
        "text": "Domestic Rangehood 600mm Under-Cabinet 3-speed",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_fume_cupboard():
    texts = [{
        "id": "neg_2",
        "text": "Laboratory Fume Hood Fume Cupboard 1500mm",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_biosafety():
    texts = [{
        "id": "neg_3",
        "text": "Biosafety Cabinet Class II Laminar Flow",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "kh_8",
        "text": "KH-08 Commercial Kitchen Hood",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "kh_9",
        "text": "KH-09: Kitchen Canopy 2400x1200mm",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "KH-09"
    assert d["length_mm"] == 2400
    assert d["width_mm"] == 1200
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"kh_{i}", "text": "KH-01 Kitchen Exhaust Hood", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_kitchen_hood_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_kitchen_hood_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Vinyl sheet flooring 2mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "kh_def",
        "text": "Commercial Kitchen Exhaust Canopy Hood",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "KH-ITEM"
    assert c.hood_type == "TYPE_1_GREASE_HOOD"
    assert c.filter_type == "BAFFLE_GREASE_FILTER"
    assert c.has_fire_suppression is False
    assert c.has_gas_interlock is False


def test_gas_solenoid_interlock_phrase():
    texts = [{
        "id": "kh_gas",
        "text": "KH-10 Grease Hood with Gas Solenoid Interlock Valve",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.has_gas_interlock is True


def test_large_airflow_4500lps():
    texts = [{
        "id": "kh_large",
        "text": "KH-11 Island Kitchen Hood 4500 L/S Ansul R102",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.exhaust_airflow_lps == 4500
    assert c.has_fire_suppression is True
    assert c.fire_suppression_brand == "ANSUL_R102"


def test_steam_capture_hood():
    texts = [{
        "id": "kh_steam",
        "text": "HOOD-12 Steam Hood Condensate Capture 1500x900mm",
        "coordinates": (6.0, 12.0)
    }]
    candidates = extract_kitchen_hood_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.hood_type == "TYPE_2_CONDENSATE_HOOD"
