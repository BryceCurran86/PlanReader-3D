"""Tests for Underground Water Main Fire Hydrant Booster Assembly & Storz Connections Shadow Authority."""

import pytest
from pb_source_fire_hydrant_booster_assembly_shadow import (
    FireHydrantBoosterCandidate,
    extract_fire_hydrant_booster_items,
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


def test_freestanding_cabinet_booster():
    texts = [{
        "id": "fhb_1",
        "text": "FHB-01 Fire Hydrant Booster Assembly 4-Way Storz Inlets in Weatherproof Freestanding Cabinet DN150 Main RPZD Backflow",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "FHB-01"
    assert c.assembly_type == "CABINET_ENCLOSURE"
    assert c.inlet_outlets_count == 4
    assert c.coupling_type == "STORZ"
    assert c.main_pipe_size_mm == 150
    assert c.has_cabinet_enclosure is True
    assert c.backflow_device_type == "RPZD"


def test_wall_mounted_booster():
    texts = [{
        "id": "fhb_2",
        "text": "HBA-2 Wall Mount Fire Brigade Booster 2-Way Storz Couplings DN100 Connection",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "HBA-2"
    assert c.assembly_type == "WALL_MOUNTED"
    assert c.inlet_outlets_count == 2
    assert c.main_pipe_size_mm == 100


def test_pillar_hydrant():
    texts = [{
        "id": "fhb_3",
        "text": "FH-01 External Standpipe Pillar Hydrant 100mm with Dual Storz Connections",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.assembly_type == "PILLAR_HYDRANT"
    assert c.main_pipe_size_mm == 100


def test_tank_inlet_suction_booster():
    texts = [{
        "id": "fhb_4",
        "text": "FDC-01 Fire Storage Tank Inlet Suction Booster Manifold DN200 4-Port Storz",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.assembly_type == "TANK_INLET"
    assert c.main_pipe_size_mm == 200
    assert c.inlet_outlets_count == 4


def test_dcv_backflow_device():
    texts = [{
        "id": "fhb_5",
        "text": "FHB-03 Fire Booster Assembly with Double Check Valve (DCV) Backflow 6-Way Storz",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.backflow_device_type == "DCV"
    assert c.inlet_outlets_count == 6


def test_bic_coupling_type():
    texts = [{
        "id": "fhb_6",
        "text": "FHB-04 Hydrant Booster British Instantaneous BIC Couplings 2-Way",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.coupling_type == "BIC"
    assert c.inlet_outlets_count == 2


def test_nst_threaded_coupling():
    texts = [{
        "id": "fhb_7",
        "text": "FDC-02 Fire Department Connection NST Threaded 2-Way 100mm",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.coupling_type == "NST"


def test_negative_lookalike_fire_hose_reel():
    texts = [{
        "id": "neg_1",
        "text": "FHR-01 Internal Fire Hose Reel 36m",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_domestic_meter():
    texts = [{
        "id": "neg_2",
        "text": "Domestic Water Meter Assembly DN50 with Isolation Valve",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_gas_box():
    texts = [{
        "id": "neg_3",
        "text": "Gas Regulator and Gas Meter Box Enclosure",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "fhb_8",
        "text": "FHB-08 Fire Hydrant Booster",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "fhb_9",
        "text": "FHB-09: 3-Way Storz Fire Booster in Kiosk",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "FHB-09"
    assert d["inlet_outlets_count"] == 3
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"fhb_{i}", "text": "FHB-01 Fire Booster Storz", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_fire_hydrant_booster_items(texts, max_primitives=14)
    assert len(candidates) == 14


def test_empty_drawing_texts():
    candidates = extract_fire_hydrant_booster_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Concrete footpath 100mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "fhb_def",
        "text": "Fire Hydrant Booster Connection",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "FHB-ITEM"
    assert c.coupling_type == "STORZ"
    assert c.has_cabinet_enclosure is False
    assert c.backflow_device_type is None


def test_pipe_size_dn250():
    texts = [{
        "id": "fhb_large",
        "text": "FHB-10 Fire Booster Manifold DN250 Header 6-Way Storz",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.main_pipe_size_mm == 250
    assert c.inlet_outlets_count == 6


def test_fdc_terminology():
    texts = [{
        "id": "fhb_fdc",
        "text": "FDC Fire Department Connection 2-Port Storz DN100",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_fire_hydrant_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "FDC"
    assert c.inlet_outlets_count == 2
