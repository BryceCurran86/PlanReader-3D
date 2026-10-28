"""Tests for Commercial Building Lightning Protection Air Terminal & Down-Conductor Shadow Authority."""

import pytest
from pb_source_lightning_protection_air_terminal_shadow import (
    LightningProtectionCandidate,
    extract_lightning_protection_items,
    snap_point,
)


def test_snap_point_exact():
    pt = (10.0, 20.0)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (10.0, 20.0)


def test_snap_point_offset():
    pt = (10.6, 21.8)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (10.0, 22.5)


def test_franklin_rod_air_terminal():
    texts = [{
        "id": "lp_1",
        "text": "AT-01: 500mm Air Terminal Franklin Rod Copper",
        "coordinates": (100.0, 200.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "AT-01"
    assert c.element_type == "AIR_TERMINAL"
    assert c.protection_method == "FRANKLIN_ROD"
    assert c.terminal_height_mm == 500
    assert c.conductor_material == "COPPER"


def test_ese_terminal_mast():
    texts = [{
        "id": "lp_2",
        "text": "ESE-1 Early Streamer Emission Air Terminal 2.0m Mast",
        "coordinates": (150.0, 250.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "ESE_TERMINAL"
    assert c.protection_method == "EARLY_STREAMER"
    assert c.terminal_height_mm == 2000


def test_down_conductor_bare_copper_tape():
    texts = [{
        "id": "lp_3",
        "text": "DC-01 Down Conductor 25x3mm Bare Copper Tape in PVC Conduit",
        "coordinates": (50.0, 75.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "DOWN_CONDUCTOR"
    assert c.conductor_size_desc == "25x3mm"
    assert c.conductor_material == "COPPER"


def test_down_conductor_cable():
    texts = [{
        "id": "lp_4",
        "text": "DC-02 Lightning Protection Down-Conductor 70mm2 Stranded Copper Cable",
        "coordinates": (60.0, 80.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "DOWN_CONDUCTOR"
    assert c.conductor_size_desc == "70mm2"


def test_aluminium_tape_conductor():
    texts = [{
        "id": "lp_5",
        "text": "LP-03 Roof Mesh Conductor 25x3mm Aluminium Tape Faraday Mesh",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.conductor_material == "ALUMINIUM"
    assert c.conductor_size_desc == "25x3mm"
    assert c.protection_method == "FARADAY_MESH"


def test_stainless_steel_down_conductor():
    texts = [{
        "id": "lp_6",
        "text": "DC-03 Down Conductor Stainless Steel 50mm2",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.conductor_material == "STAINLESS_STEEL"
    assert c.conductor_size_desc == "50mm2"


def test_earth_pit_inspection_well():
    texts = [{
        "id": "lp_7",
        "text": "EP-01 Earth Pit Inspection Well with Copper Earth Rod & Disconnect Test Clamp",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "EARTH_PIT"
    assert c.has_test_clamp is True


def test_test_clamp_element():
    texts = [{
        "id": "lp_8",
        "text": "TC-01 Lightning Protection Disconnect Test Clamp at 1500mm AFFL",
        "coordinates": (12.0, 24.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "TEST_CLAMP"
    assert c.has_test_clamp is True


def test_negative_lookalike_solar_panel():
    texts = [{
        "id": "neg_1",
        "text": "Solar Panel Array DC Inverter Cable Tray",
        "coordinates": (100.0, 200.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_tv_antenna():
    texts = [{
        "id": "neg_2",
        "text": "TV Antenna Mast on Roof Parapet",
        "coordinates": (100.0, 200.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_cellular():
    texts = [{
        "id": "neg_3",
        "text": "Cellular Antenna 4G/5G Mast Support",
        "coordinates": (100.0, 200.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "lp_9",
        "text": "AT-02: 1000mm Air Terminal Franklin Rod",
        "coordinates": (100.0, 200.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"  # frozen dataclass


def test_candidate_to_dict():
    texts = [{
        "id": "lp_10",
        "text": "AT-03: 300mm Air Terminal Copper",
        "coordinates": (50.0, 50.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "AT-03"
    assert d["terminal_height_mm"] == 300
    assert d["conductor_material"] == "COPPER"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_strike_termination_terminology():
    texts = [{
        "id": "lp_11",
        "text": "Strike Termination Device Air Terminal 1.5m Mast",
        "coordinates": (75.0, 85.0)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "AIR_TERMINAL"
    assert c.terminal_height_mm == 1500


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"lp_{i}", "text": "AT-01 Air Terminal Franklin Rod", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_lightning_protection_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_lightning_protection_items([])
    assert len(candidates) == 0


def test_generic_text_unmatched():
    texts = [{"id": "gen_1", "text": "Ceiling Access Panel 600x600", "coordinates": (10.0, 20.0)}]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "lp_default",
        "text": "Lightning Protection System Element",
        "coordinates": (10.2, 20.3)
    }]
    candidates = extract_lightning_protection_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "LPS-ITEM"
    assert c.conductor_material == "COPPER"
    assert c.protection_method == "FARADAY_MESH"
    assert c.terminal_height_mm is None
