"""Tests for Commercial Kitchen Grease Arrestor / Interceptor Pit & Sampling Shaft Shadow Authority."""

import pytest
from pb_source_grease_interceptor_sampling_shaft_shadow import (
    GreaseInterceptorCandidate,
    extract_grease_interceptor_items,
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


def test_below_ground_precast_arrestor():
    texts = [{
        "id": "gt_1",
        "text": "GT-01 Below Ground Commercial Grease Arrestor 2000L Precast Concrete with Class D Gastight Cover and Remote Pump-Out Line",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GT-01"
    assert c.element_type == "BELOW_GROUND_ARRESTOR"
    assert c.capacity_litres == 2000
    assert c.tank_material == "PRECAST_CONCRETE"
    assert c.cover_class == "CLASS_D"
    assert c.has_remote_pump_out is True
    assert c.has_coalescing_plates is False


def test_above_ground_polyethylene_arrestor():
    texts = [{
        "id": "gt_2",
        "text": "GA-02 Above Ground Polyethylene Grease Trap 1000L with Coalescing Plate Pack in Basement Plantroom",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GA-02"
    assert c.element_type == "ABOVE_GROUND_ARRESTOR"
    assert c.capacity_litres == 1000
    assert c.tank_material == "POLYETHYLENE"
    assert c.has_coalescing_plates is True


def test_trade_waste_sampling_shaft():
    texts = [{
        "id": "gt_3",
        "text": "SS-03 Trade Waste Sampling Shaft DN300 PVC with Gastight Sealed Cover",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "SS-03"
    assert c.element_type == "SAMPLING_SHAFT"
    assert c.cover_class == "GASTIGHT"


def test_remote_pump_out_line():
    texts = [{
        "id": "gt_4",
        "text": "TW-04 Remote Pump-Out Line 50mm Copper with Camlock Tanker Coupling",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "PUMP_OUT_LINE"
    assert c.has_remote_pump_out is True


def test_biological_dosing_unit():
    texts = [{
        "id": "gt_5",
        "text": "GT-05 Automatic Bio-Dosing Unit for Commercial Kitchen Grease Interceptor",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "DOSING_UNIT"


def test_fibreglass_tank_material():
    texts = [{
        "id": "gt_6",
        "text": "GI-06 Fibreglass GRP Commercial Grease Interceptor 3000L Class B Cover",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tank_material == "FIBREGLASS_GRP"
    assert c.capacity_litres == 3000
    assert c.cover_class == "CLASS_B"


def test_class_b_cover_light_duty():
    texts = [{
        "id": "gt_7",
        "text": "GT-07 1500 Litre Trade Waste Grease Trap Class B Cover in Footpath",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.capacity_litres == 1500
    assert c.cover_class == "CLASS_B"


def test_negative_lookalike_gpt():
    texts = [{
        "id": "neg_1",
        "text": "Gross Pollutant Trap CDS Unit Stormwater Chamber",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_oil_water():
    texts = [{
        "id": "neg_2",
        "text": "Oil Water Separator Hydrocarbon Coalescer 5000L",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_septic():
    texts = [{
        "id": "neg_3",
        "text": "Septic Sewage Tank Below Ground Holding Tank",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "gt_8",
        "text": "GT-08 Commercial Grease Arrestor",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "gt_9",
        "text": "GT-09: 2500L Grease Trap",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "GT-09"
    assert d["capacity_litres"] == 2500
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"gt_{i}", "text": "GT-01 Commercial Grease Trap", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_grease_interceptor_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_grease_interceptor_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Aluminium entrance matting", "coordinates": (0.0, 0.0)}]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "gt_def",
        "text": "Trade Waste Grease Interceptor Trap",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GT-ITEM"
    assert c.element_type == "BELOW_GROUND_ARRESTOR"
    assert c.tank_material == "PRECAST_CONCRETE"
    assert c.cover_class == "GASTIGHT"
    assert c.has_remote_pump_out is False


def test_large_capacity_5000l():
    texts = [{
        "id": "gt_large",
        "text": "GA-10 Precast Concrete Grease Arrestor 5000 Litres Class D",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.capacity_litres == 5000
    assert c.cover_class == "CLASS_D"


def test_gss_tag_sampling_shaft():
    texts = [{
        "id": "gt_gss",
        "text": "GSS-11 Grease Sampling Shaft at Property Boundary",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_grease_interceptor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GSS-11"
    assert c.element_type == "SAMPLING_SHAFT"
