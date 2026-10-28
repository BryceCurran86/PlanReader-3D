"""Tests for Chilled Water / Condenser Water Thermal Storage Stratified Buffer Tank Shadow Authority."""

import pytest
from pb_source_chilled_water_thermal_buffer_tank_shadow import (
    ChilledWaterBufferCandidate,
    extract_chilled_water_buffer_items,
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


def test_vertical_chilled_water_buffer():
    texts = [{
        "id": "cwt_1",
        "text": "CHW-BT-01 Chilled Water Buffer Tank 5000L Vertical Cylindrical with Internal Diffusers 1000 kPa Rated Insulated and Clad",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "CHW-BT-01"
    assert c.tank_type == "CHILLED_WATER_BUFFER"
    assert c.storage_volume_litres == 5000
    assert c.orientation == "VERTICAL"
    assert c.has_internal_diffusers is True
    assert c.design_pressure_kpa == 1000
    assert c.insulation_type == "CLOSED_CELL_FOAM_CLAD"


def test_horizontal_low_headroom_buffer():
    texts = [{
        "id": "cwt_2",
        "text": "BT-02 Horizontal Chilled Water Buffer Tank 3000 Litres in Basement Plantroom 10 bar",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BT-02"
    assert c.orientation == "HORIZONTAL"
    assert c.storage_volume_litres == 3000
    assert c.design_pressure_kpa == 1000


def test_thermal_stratified_storage_tank():
    texts = [{
        "id": "cwt_3",
        "text": "TES-03 Stratified Chilled Water Thermal Storage Tank 20000L with Radial Diffusers 1600 kPa",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "TES-03"
    assert c.tank_type == "THERMAL_STRATIFIED_STORAGE"
    assert c.storage_volume_litres == 20000
    assert c.has_internal_diffusers is True
    assert c.design_pressure_kpa == 1600


def test_heating_water_buffer_tank():
    texts = [{
        "id": "cwt_4",
        "text": "HHW-BT-04 Heating Hot Water Buffer Tank 2000L Vertical Insulated with PIR Foam",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tank_type == "HEATING_WATER_BUFFER"
    assert c.storage_volume_litres == 2000


def test_hydraulic_separator_low_loss():
    texts = [{
        "id": "cwt_5",
        "text": "HS-05 4-Pipe Hydraulic Separator Low Loss Header Tank 1500L with Internal Baffle",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tank_type == "HYDRAULIC_SEPARATOR"
    assert c.storage_volume_litres == 1500


def test_uninsulated_tank_specification():
    texts = [{
        "id": "cwt_6",
        "text": "BT-06 Condenser Water Buffer Tank 4000L Uninsulated Bare Steel",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.insulation_type == "UNINSULATED"


def test_16_bar_rating():
    texts = [{
        "id": "cwt_7",
        "text": "CHW-BT-07 High Rise Chilled Water Buffer Tank 10000L 16 bar Working Pressure",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.design_pressure_kpa == 1600
    assert c.storage_volume_litres == 10000


def test_negative_lookalike_fire_water():
    texts = [{
        "id": "neg_1",
        "text": "Fire Water Tank 150kL Bolted Steel Suction Tank",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_potable_break():
    texts = [{
        "id": "neg_2",
        "text": "Potable Water Tank Domestic Break Tank 5000L",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_diesel_fuel():
    texts = [{
        "id": "neg_3",
        "text": "Diesel Fuel Day Tank 1000L Double Wall",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "cwt_8",
        "text": "BT-08 Chilled Water Buffer Tank",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "cwt_9",
        "text": "BT-09: 2500L Buffer Tank",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "BT-09"
    assert d["storage_volume_litres"] == 2500
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"cwt_{i}", "text": "BT-01 Chilled Water Buffer", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_chilled_water_buffer_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_chilled_water_buffer_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Wall skirting 100mm timber", "coordinates": (0.0, 0.0)}]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "cwt_def",
        "text": "Chilled Water Buffer Vessel",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BT-ITEM"
    assert c.tank_type == "CHILLED_WATER_BUFFER"
    assert c.orientation == "VERTICAL"
    assert c.has_internal_diffusers is False
    assert c.insulation_type == "CLOSED_CELL_FOAM_CLAD"


def test_stratification_baffles_phrase():
    texts = [{
        "id": "cwt_baff",
        "text": "BT-10 Buffer Tank with Stratification Baffles 6000L",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.has_internal_diffusers is True
    assert c.storage_volume_litres == 6000


def test_hot_water_buffer_phrase():
    texts = [{
        "id": "cwt_hw",
        "text": "BT-11 Hot Water Buffer Tank 3500L Vertical Cylindrical",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tank_type == "HEATING_WATER_BUFFER"
    assert c.storage_volume_litres == 3500
    assert c.orientation == "VERTICAL"


def test_1200_kpa_pressure():
    texts = [{
        "id": "cwt_1200",
        "text": "CHW-BT-12 Chilled Water Buffer 1200 kPa 8000L",
        "coordinates": (6.0, 12.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.design_pressure_kpa == 1200
    assert c.storage_volume_litres == 8000


def test_hst_tag():
    texts = [{
        "id": "cwt_hst",
        "text": "HST-13 Hydraulic Separator Tank 2000L",
        "coordinates": (8.0, 16.0)
    }]
    candidates = extract_chilled_water_buffer_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "HST-13"
    assert c.tank_type == "HYDRAULIC_SEPARATOR"
