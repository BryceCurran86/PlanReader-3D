"""Tests for Precast Concrete Bridge / Transfer Beam Neoprene Elastomeric Bearing Pad Shadow Authority."""

import pytest
from pb_source_elastomeric_bearing_pad_transfer_beam_shadow import (
    ElastomericBearingCandidate,
    extract_elastomeric_bearing_items,
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


def test_steel_laminated_elastomeric_bearing():
    texts = [{
        "id": "ebp_1",
        "text": "EBP-01 Steel Laminated Elastomeric Bearing Pad 400x300x52mm Shore 60A 2500 kN Vertical Load under Precast Girder",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "EBP-01"
    assert c.bearing_type == "STEEL_LAMINATED_ELASTOMERIC"
    assert c.plan_dimensions_desc == "400x300mm"
    assert c.total_thickness_mm == 52
    assert c.durometer_hardness == "SHORE_60A"
    assert c.vertical_load_capacity_kn == 2500
    assert c.has_ptfe_sliding_layer is False


def test_ptfe_sliding_bearing():
    texts = [{
        "id": "ebp_2",
        "text": "BP-02 PTFE Sliding Bearing Pad 500x400x70mm with Stainless Sliding Plate 4000 kN",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BP-02"
    assert c.bearing_type == "PTFE_SLIDING_BEARING"
    assert c.has_ptfe_sliding_layer is True
    assert c.plan_dimensions_desc == "500x400mm"
    assert c.total_thickness_mm == 70
    assert c.vertical_load_capacity_kn == 4000


def test_pot_bearing():
    texts = [{
        "id": "ebp_3",
        "text": "POT-03 Fixed Structural Pot Bearing 600x600x120mm Capacity 6000 kN under Transfer Beam",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.bearing_type == "POT_BEARING"
    assert c.plan_dimensions_desc == "600x600mm"
    assert c.total_thickness_mm == 120
    assert c.vertical_load_capacity_kn == 6000


def test_plain_elastomeric_strip():
    texts = [{
        "id": "ebp_4",
        "text": "PAD-04 Plain Elastomeric Bearing Strip 200x20mm Unreinforced Neoprene",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.bearing_type == "PLAIN_ELASTOMERIC_STRIP"
    assert c.total_thickness_mm == 20


def test_shear_dowel_pin():
    texts = [{
        "id": "ebp_5",
        "text": "BRG-05 Restraining Shear Dowel Pin Locating Stud at Girder Bearing Seat",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.bearing_type == "SHEAR_DOWEL_PIN"


def test_shore_50a_hardness():
    texts = [{
        "id": "ebp_6",
        "text": "EBP-06 Laminated Neoprene Bearing Pad 300x200x40mm 50 IRHD Hardness",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.durometer_hardness == "SHORE_50A"


def test_shore_70a_hardness():
    texts = [{
        "id": "ebp_7",
        "text": "EBP-07 High Capacity Elastomeric Bearing 70 Durometer 1500 kN",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.durometer_hardness == "SHORE_70A"
    assert c.vertical_load_capacity_kn == 1500


def test_negative_lookalike_baseplate():
    texts = [{
        "id": "neg_1",
        "text": "Steel Column Baseplate 400x400x25mm Grade 350",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_acoustic_foam():
    texts = [{
        "id": "neg_2",
        "text": "Stud Wall Acoustic Foam Resilient Channel",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_chiller_pad():
    texts = [{
        "id": "neg_3",
        "text": "Equipment Waffle Chiller Isolation Pad 100x100mm",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "ebp_8",
        "text": "EBP-08 Elastomeric Bearing Pad",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "ebp_9",
        "text": "EBP-09: 300x250x45mm Bearing Pad",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "EBP-09"
    assert d["plan_dimensions_desc"] == "300x250mm"
    assert d["total_thickness_mm"] == 45
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"ebp_{i}", "text": "EBP-01 Girder Bearing Pad", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_elastomeric_bearing_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_elastomeric_bearing_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Asphalt wearing course 40mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "ebp_def",
        "text": "Elastomeric Bearing Pad Assembly",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "EBP-ITEM"
    assert c.bearing_type == "STEEL_LAMINATED_ELASTOMERIC"
    assert c.durometer_hardness == "SHORE_60A"
    assert c.has_ptfe_sliding_layer is False


def test_teflon_keyword_sliding():
    texts = [{
        "id": "ebp_teflon",
        "text": "BP-10 Laminated Neoprene Bearing with Teflon Sliding Layer 350x250mm 1200 kN",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.bearing_type == "PTFE_SLIDING_BEARING"
    assert c.has_ptfe_sliding_layer is True
    assert c.vertical_load_capacity_kn == 1200


def test_transfer_beam_bearing():
    texts = [{
        "id": "ebp_tb",
        "text": "BRG-11 Transfer Beam Bearing Pad 500x350x65mm",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_elastomeric_bearing_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.plan_dimensions_desc == "500x350mm"
    assert c.total_thickness_mm == 65
