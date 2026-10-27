"""Tests for Structural Glazed Balustrade & Base U-Channel Shoe Shadow Authority."""

import pytest
from pb_source_glazed_balustrade_base_shoe_shadow import (
    GlazedBalustradeCandidate,
    extract_glazed_balustrade_items,
    snap_point,
)


def test_snap_point_exact():
    pt = (100.0, 200.0)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 200.0)


def test_snap_point_offset():
    pt = (101.2, 203.7)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 202.5)


def test_base_shoe_toughened_laminated():
    texts = [{
        "id": "gb_1",
        "text": "BAL-01: Continuous Aluminium Base Shoe Channel with 21.52mm Toughened Laminated Glass 1100mm High",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BAL-01"
    assert c.system_type == "BASE_SHOE"
    assert c.glass_thickness_mm == 21.52
    assert c.glass_type == "TOUGHENED_LAMINATED"
    assert c.height_mm == 1100
    assert c.mounting_type == "TOP_MOUNT"


def test_spigot_mounted_balustrade():
    texts = [{
        "id": "gb_2",
        "text": "GB-02 Stainless Steel Spigot Clamps Core-Drilled 12mm Toughened Glass Balustrade",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GB-02"
    assert c.system_type == "SPIGOT"
    assert c.mounting_type == "CORE_DRILLED"
    assert c.glass_thickness_mm == 12.0
    assert c.glass_type == "TOUGHENED_MONOLITHIC"


def test_point_fixed_standoff():
    texts = [{
        "id": "gb_3",
        "text": "GLB-10 Face Fixed Disc Standoff Point Fixing 17.52mm Toughened Laminated Glass Balustrade Side Mount",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.system_type == "POINT_FIXED"
    assert c.mounting_type == "SIDE_MOUNT"
    assert c.glass_thickness_mm == 17.52
    assert c.glass_type == "TOUGHENED_LAMINATED"


def test_post_and_rail():
    texts = [{
        "id": "gb_4",
        "text": "BAL-04 Stainless Steel Post and Rail Glass Balustrade with Top Rail",
        "coordinates": (120.0, 140.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.system_type == "POST_AND_RAIL"
    assert c.handrail_type == "TOP_RAIL"


def test_channel_cap_handrail():
    texts = [{
        "id": "gb_5",
        "text": "BAL-05 Base Channel Glass Balustrade with Slimline Cap Channel",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.handrail_type == "CHANNEL_CAP"


def test_offset_handrail():
    texts = [{
        "id": "gb_6",
        "text": "BAL-06 Structural Glass Balustrade with Offset Handrail 1000mm High",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.handrail_type == "OFFSET_HANDRAIL"
    assert c.height_mm == 1000


def test_frameless_option():
    texts = [{
        "id": "gb_7",
        "text": "BAL-07 Frameless Glass Balustrade No Handrail 1200mm High",
        "coordinates": (35.0, 45.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.handrail_type == "FRAMELESS"
    assert c.height_mm == 1200


def test_sentryglas_interlayer_detection():
    texts = [{
        "id": "gb_8",
        "text": "BAL-08 Base Shoe Glazed Barrier 21.52mm SentryGlas Interlayer",
        "coordinates": (40.0, 50.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.glass_type == "TOUGHENED_LAMINATED"
    assert c.glass_thickness_mm == 21.52


def test_negative_lookalike_shower_screen():
    texts = [{
        "id": "neg_1",
        "text": "Shower Screen 10mm Toughened Glass Enclosure",
        "coordinates": (100.0, 100.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_curtain_wall():
    texts = [{
        "id": "neg_2",
        "text": "Curtain Wall Glazing Vision Glass Unit",
        "coordinates": (100.0, 100.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_office_partition():
    texts = [{
        "id": "neg_3",
        "text": "Office Partition 12mm Glass Demountable Wall",
        "coordinates": (100.0, 100.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "gb_9",
        "text": "BAL-09 Base Channel Glass Balustrade",
        "coordinates": (10.0, 10.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "gb_10",
        "text": "BAL-10: Base Shoe Balustrade 15mm Toughened Glass",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "BAL-10"
    assert d["glass_thickness_mm"] == 15.0
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"gb_{i}", "text": "BAL-01 Glass Balustrade Base Shoe", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_glazed_balustrade_items(texts, max_primitives=12)
    assert len(candidates) == 12


def test_empty_drawing_texts():
    candidates = extract_glazed_balustrade_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Timber skirting board 100mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "gb_def",
        "text": "Glass Balustrade Edge Barrier",
        "coordinates": (10.0, 10.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BAL-ITEM"
    assert c.system_type == "BASE_SHOE"
    assert c.mounting_type == "TOP_MOUNT"
    assert c.handrail_type == "STANDARD"


def test_edge_barrier_terminology():
    texts = [{
        "id": "gb_edge",
        "text": "BL-01 Glass Railing Edge Barrier 1100mm High",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_glazed_balustrade_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BL-01"
    assert c.height_mm == 1100
