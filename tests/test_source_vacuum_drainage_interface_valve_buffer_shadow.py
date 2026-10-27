"""Tests for Sanitary Plumbing Vacuum Drainage Interface Valve & Buffer Tank Shadow Authority."""

import pytest
from pb_source_vacuum_drainage_interface_valve_buffer_shadow import (
    VacuumDrainageCandidate,
    extract_vacuum_drainage_items,
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


def test_pneumatic_vacuum_interface_valve():
    texts = [{
        "id": "vac_1",
        "text": "VIV-01 50mm Vacuum Interface Valve Pneumatic Diaphragm Actuation connected to DN50 Vacuum Collection Main at -50 kPa",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "VIV-01"
    assert c.element_type == "VACUUM_INTERFACE_VALVE"
    assert c.valve_size_mm == 50
    assert c.pipe_diameter_mm == 50
    assert c.actuation_mechanism == "PNEUMATIC_DIAPHRAGM"
    assert c.operating_vacuum_kpa == -50


def test_graywater_buffer_sump_unit():
    texts = [{
        "id": "vac_2",
        "text": "VBU-02 Vacuum Buffer Unit 30L Graywater Collection Sump with Controller",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "VBU-02"
    assert c.element_type == "BUFFER_SUMP_UNIT"
    assert c.buffer_capacity_litres == 30


def test_vacuum_toilet_pan():
    texts = [{
        "id": "vac_3",
        "text": "VWC-03 Commercial Vacuum Toilet WC Pan with Integral Push-Button Pneumatic Valve",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "VWC-03"
    assert c.element_type == "VACUUM_TOILET"
    assert c.actuation_mechanism == "PNEUMATIC_DIAPHRAGM"


def test_central_vacuum_station_skid():
    texts = [{
        "id": "vac_4",
        "text": "VS-04 Central Vacuum Station Generator Skid with Dual Vacuum Pumps at -60 kPa",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "VS-04"
    assert c.element_type == "VACUUM_STATION_SKID"
    assert c.operating_vacuum_kpa == -60


def test_65mm_vacuum_valve():
    texts = [{
        "id": "vac_5",
        "text": "VIV-05 65mm Vacuum Interface Valve for Kitchen Waste Drainage",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.valve_size_mm == 65


def test_electronic_solenoid_valve():
    texts = [{
        "id": "vac_6",
        "text": "VIV-06 Vacuum Valve with Electronic Solenoid Actuator and BMS Monitoring",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.actuation_mechanism == "ELECTRONIC_SOLENOID"


def test_dn100_vacuum_main():
    texts = [{
        "id": "vac_7",
        "text": "VDP-07 Vacuum Drainage System DN100 Main Header",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.pipe_diameter_mm == 100


def test_negative_lookalike_gravity_sewer():
    texts = [{
        "id": "neg_1",
        "text": "Gravity Sewer 100mm PVC Soil Stack Drain to Manhole",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_medical_vacuum():
    texts = [{
        "id": "neg_2",
        "text": "Medical Vacuum Outlet Med Gas Pipeline in Hospital Operating Theatre",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_siphonic():
    texts = [{
        "id": "neg_3",
        "text": "Siphonic Roof Drainage System HDPE Downpipe",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "vac_8",
        "text": "VIV-08 Vacuum Interface Valve",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "vac_9",
        "text": "VIV-09: 50mm Vacuum Valve -55 kPa",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "VIV-09"
    assert d["valve_size_mm"] == 50
    assert d["operating_vacuum_kpa"] == -55
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"vac_{i}", "text": "VIV-01 Vacuum Valve", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_vacuum_drainage_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_vacuum_drainage_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Acoustic plaster ceiling 13mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "vac_def",
        "text": "Vacuum Drainage Collection Interface",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "VAC-ITEM"
    assert c.element_type == "VACUUM_INTERFACE_VALVE"
    assert c.actuation_mechanism == "PNEUMATIC_DIAPHRAGM"
    assert c.operating_vacuum_kpa is None


def test_buffer_box_15_litres():
    texts = [{
        "id": "vac_box",
        "text": "VBU-10 Vacuum Buffer Box 15 Litres Suspended in Ceiling Space",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "BUFFER_SUMP_UNIT"
    assert c.buffer_capacity_litres == 15


def test_80mm_valve_size():
    texts = [{
        "id": "vac_80",
        "text": "VIV-11 Heavy Duty 80mm Vacuum Valve for High Flow Drainage",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.valve_size_mm == 80


def test_vacuum_sewer_pipe():
    texts = [{
        "id": "vac_pipe",
        "text": "VDP-12 Vacuum Sewer Pipe DN65 PE-100 Electrofusion Welded",
        "coordinates": (6.0, 12.0)
    }]
    candidates = extract_vacuum_drainage_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.pipe_diameter_mm == 65
