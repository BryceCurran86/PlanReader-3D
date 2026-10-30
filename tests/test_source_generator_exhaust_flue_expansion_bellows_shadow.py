"""Tests for Emergency Generator Exhaust Flue & Expansion Bellows Compensator Shadow Authority."""

import pytest
from pb_source_generator_exhaust_flue_expansion_bellows_shadow import (
    GeneratorExhaustCandidate,
    extract_generator_exhaust_items,
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


def test_twin_wall_exhaust_flue():
    texts = [{
        "id": "gen_ex_1",
        "text": "GEN-EX-01 Generator Exhaust Flue DN250 Twin Wall Factory Insulated Stainless 316 with Condensate Drain Plug",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GEN-EX-01"
    assert c.element_type == "EXHAUST_FLUE"
    assert c.flue_diameter_mm == 250
    assert c.wall_construction == "TWIN_WALL_INSULATED"
    assert c.flue_material == "STAINLESS_316"
    assert c.has_drain_plug is True


def test_corrugated_expansion_bellows():
    texts = [{
        "id": "gen_ex_2",
        "text": "BEL-02 Engine Exhaust Expansion Bellows Multi-Ply Stainless Steel DN200 at Turbo Outlet",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BEL-02"
    assert c.element_type == "EXPANSION_BELLOWS"
    assert c.flue_diameter_mm == 200


def test_hospital_grade_silencer():
    texts = [{
        "id": "gen_ex_3",
        "text": "SIL-03 Generator Exhaust Silencer Hospital Grade 35 dBA Reduction DN300",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "SIL-03"
    assert c.element_type == "EXHAUST_SILENCER"
    assert c.silencer_attenuation_grade == "HOSPITAL"
    assert c.flue_diameter_mm == 300


def test_critical_grade_silencer():
    texts = [{
        "id": "gen_ex_4",
        "text": "SIL-04 Genset Exhaust Muffler Critical Grade Attenuation DN250",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.silencer_attenuation_grade == "CRITICAL"


def test_residential_grade_silencer():
    texts = [{
        "id": "gen_ex_5",
        "text": "SIL-05 Generator Exhaust Silencer Residential Grade DN200",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.silencer_attenuation_grade == "RESIDENTIAL"


def test_discharge_cowl_jet_cap():
    texts = [{
        "id": "gen_ex_6",
        "text": "COWL-06 Generator Exhaust High Velocity Discharge Cowl Rain Cap DN300",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "DISCHARGE_COWL"
    assert c.flue_diameter_mm == 300


def test_wall_penetration_thimble():
    texts = [{
        "id": "gen_ex_7",
        "text": "THM-07 Generator Exhaust Roof Thimble Insulated Sleeve Penetration",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "WALL_THIMBLE"


def test_single_wall_clad_lagged():
    texts = [{
        "id": "gen_ex_8",
        "text": "EXH-08 Single Wall Diesel Exhaust Pipe Lagged with Ceramic Blanket and Clad DN150",
        "coordinates": (120.0, 130.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.wall_construction == "SINGLE_WALL_CLAD"
    assert c.flue_diameter_mm == 150


def test_negative_lookalike_boiler():
    texts = [{
        "id": "neg_1",
        "text": "Condensing Boiler Flue Stainless Steel DN150",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_kitchen_hood():
    texts = [{
        "id": "neg_2",
        "text": "Kitchen Hood Exhaust Grease Duct Fire Rated",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_toilet_exhaust():
    texts = [{
        "id": "neg_3",
        "text": "EAD-01 Toilet Exhaust Air Duct 300x200mm",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "gen_ex_9",
        "text": "GEN-EX-09 Diesel Generator Exhaust Flue",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "gen_ex_10",
        "text": "GEN-EX-10: Generator Exhaust DN350",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "GEN-EX-10"
    assert d["flue_diameter_mm"] == 350
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"gen_{i}", "text": "GEN-EX-01 Generator Exhaust Flue", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_generator_exhaust_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_generator_exhaust_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Acoustic ceiling tile 600x600", "coordinates": (0.0, 0.0)}]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "gen_def",
        "text": "Emergency Generator Exhaust Stack",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GEN-EX-ITEM"
    assert c.flue_material == "STAINLESS_316"
    assert c.wall_construction == "TWIN_WALL_INSULATED"
    assert c.has_drain_plug is False


def test_large_diameter_500():
    texts = [{
        "id": "gen_large",
        "text": "GEN-EX-11 Genset Engine Exhaust Flue DN500 Mild Steel",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_generator_exhaust_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.flue_diameter_mm == 500
    assert c.flue_material == "MILD_STEEL"
