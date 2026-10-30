"""Tests for Civil Stormwater Detention Orifice Plate & Trash Screen Pit Shadow Authority."""

import pytest
from pb_source_stormwater_orifice_plate_trash_screen_shadow import (
    StormwaterOrificeCandidate,
    extract_stormwater_orifice_items,
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


def test_dcp_complete_assembly():
    texts = [{
        "id": "dcp_1",
        "text": "DCP-01 On-Site Detention Discharge Control Pit with 100mm Orifice Plate Stainless 316 and Inclined Trash Screen with Overflow Weir 600mm Wide",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "DCP-01"
    assert c.element_type == "DISCHARGE_CONTROL_PIT"
    assert c.orifice_diameter_mm == 100
    assert c.plate_material == "STAINLESS_316"
    assert c.trash_screen_type == "INCLINED_SCREEN"
    assert c.has_overflow_weir is True
    assert c.weir_width_mm == 600


def test_orifice_plate_standalone():
    texts = [{
        "id": "dcp_2",
        "text": "OP-02 Laser Cut Stainless 304 Orifice Plate 75mm Dia bolted over DN150 outlet pipe",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "OP-02"
    assert c.element_type == "ORIFICE_PLATE"
    assert c.orifice_diameter_mm == 75
    assert c.plate_material == "STAINLESS_304"


def test_trash_screen_inclined():
    texts = [{
        "id": "dcp_3",
        "text": "TS-03 Galvanized Steel Inclined Trash Screen 45 Deg Maxi-Mesh protecting orifice",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "TS-03"
    assert c.element_type == "TRASH_SCREEN"
    assert c.trash_screen_type == "INCLINED_SCREEN"
    assert c.plate_material == "GALVANIZED_STEEL"


def test_vertical_box_cage_screen():
    texts = [{
        "id": "dcp_4",
        "text": "TS-04 Vertical Box Cage Debris Screen Stainless Steel 316",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "TRASH_SCREEN"
    assert c.trash_screen_type == "VERTICAL_CAGE"
    assert c.plate_material == "STAINLESS_316"


def test_internal_overflow_weir():
    texts = [{
        "id": "dcp_5",
        "text": "WEIR-05 Emergency Overflow Weir Crest 900mm in OSD Chamber",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "OVERFLOW_WEIR"
    assert c.has_overflow_weir is True
    assert c.weir_width_mm == 900


def test_large_orifice_200mm():
    texts = [{
        "id": "dcp_6",
        "text": "DCP-06 OSD Outlet Pit with 200mm Orifice Plate Restrictor",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.orifice_diameter_mm == 200


def test_stepped_trash_screen():
    texts = [{
        "id": "dcp_7",
        "text": "TS-07 Stepped Trash Screen Stainless 316 over OSD Orifice",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.trash_screen_type == "STEPPED_SCREEN"


def test_negative_lookalike_roof_strainer():
    texts = [{
        "id": "neg_1",
        "text": "Roof Drain Strainer Leaf Guard Dome",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_gully_pit():
    texts = [{
        "id": "neg_2",
        "text": "Kerb Gully Inlet Pit Type SA Pit with Cast Iron Grate",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_trench_drain():
    texts = [{
        "id": "neg_3",
        "text": "Heelguard Trench Drain with Slotted Cast Iron Grate",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "dcp_8",
        "text": "DCP-08 Discharge Control Pit",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "dcp_9",
        "text": "DCP-09: 125mm Orifice Plate",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "DCP-09"
    assert d["orifice_diameter_mm"] == 125
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"dcp_{i}", "text": "DCP-01 OSD Orifice Pit", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_stormwater_orifice_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_stormwater_orifice_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Timber fencing 1800mm high", "coordinates": (0.0, 0.0)}]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "dcp_def",
        "text": "Stormwater Detention Orifice Plate and Screen",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "DCP-ITEM"
    assert c.plate_material == "STAINLESS_316"
    assert c.trash_screen_type == "INCLINED_SCREEN"
    assert c.has_overflow_weir is False


def test_do_notation_diameter():
    texts = [{
        "id": "dcp_do",
        "text": "OP-10 Orifice Restrictor Do=50mm Stainless Steel",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.orifice_diameter_mm == 50


def test_osd_pit_tag():
    texts = [{
        "id": "dcp_osd",
        "text": "OSD-11 On-Site Detention Outlet Pit with 150mm Orifice",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_stormwater_orifice_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "OSD-11"
    assert c.orifice_diameter_mm == 150
