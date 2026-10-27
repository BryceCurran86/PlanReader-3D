"""Tests for Variable Air Volume (VAV) Terminal Unit & Electric Reheat Coil Shadow Authority."""

import pytest
from pb_source_vav_terminal_unit_reheat_coil_shadow import (
    VAVTerminalUnitCandidate,
    extract_vav_terminal_unit_items,
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


def test_single_duct_vav_electric_reheat():
    texts = [{
        "id": "vav_1",
        "text": "VAV-1-01 Single Duct VAV Terminal Unit 200mm Inlet 180 L/S with 1.5 kW Electric Reheat Coil",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "VAV-1-01"
    assert c.unit_type == "SINGLE_DUCT_VAV"
    assert c.inlet_diameter_mm == 200
    assert c.airflow_lps == 180
    assert c.reheat_type == "ELECTRIC_REHEAT"
    assert c.reheat_capacity_kw == 1.5
    assert c.has_discharge_attenuator is False


def test_fan_powered_parallel_box():
    texts = [{
        "id": "vav_2",
        "text": "FPB-02 Parallel Fan Powered Terminal Box 250mm Spigot 320 L/S 3.0 kW SCR Reheat",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "FPB-02"
    assert c.unit_type == "FAN_POWERED_PARALLEL"
    assert c.inlet_diameter_mm == 250
    assert c.airflow_lps == 320
    assert c.reheat_type == "ELECTRIC_REHEAT"
    assert c.reheat_capacity_kw == 3.0


def test_fan_powered_series_box():
    texts = [{
        "id": "vav_3",
        "text": "FPB-03 Series Fan Powered Box 300mm Collar 450 L/S with Discharge Attenuator",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.unit_type == "FAN_POWERED_SERIES"
    assert c.inlet_diameter_mm == 300
    assert c.airflow_lps == 450
    assert c.has_discharge_attenuator is True


def test_cooling_only_single_duct():
    texts = [{
        "id": "vav_4",
        "text": "VAV-04 Cooling Only Throttling VAV Box 150mm Inlet 90 L/S No Reheat",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.reheat_type == "NO_REHEAT"
    assert c.reheat_capacity_kw is None
    assert c.inlet_diameter_mm == 150
    assert c.airflow_lps == 90


def test_hot_water_reheat_coil():
    texts = [{
        "id": "vav_5",
        "text": "TU-05 VAV Terminal Unit 200mm Dia with LTHW Hot Water Heating Coil 2.5 kW",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.reheat_type == "HOT_WATER_REHEAT"
    assert c.reheat_capacity_kw == 2.5


def test_dual_duct_box():
    texts = [{
        "id": "vav_6",
        "text": "VAV-06 Dual Duct Mixing VAV Box 250mm Inlets 350 L/S",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.unit_type == "DUAL_DUCT_VAV"
    assert c.inlet_diameter_mm == 250


def test_integral_sound_silencer():
    texts = [{
        "id": "vav_7",
        "text": "VAV-07 Variable Air Volume Unit with Acoustic Silencer Casing",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.has_discharge_attenuator is True


def test_negative_lookalike_ahu():
    texts = [{
        "id": "neg_1",
        "text": "AHU-01 Primary Air Handling Unit 2500 L/S Chilled Water Coil",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_fcu():
    texts = [{
        "id": "neg_2",
        "text": "FCU-02 Fan Coil Unit 350 L/S Ceiling Concealed",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_mvd():
    texts = [{
        "id": "neg_3",
        "text": "MVD-03 Manual Volume Damper 300x200mm in Branch Duct",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "vav_8",
        "text": "VAV-08 Variable Air Volume Terminal",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "vav_9",
        "text": "VAV-09: 150mm Inlet 120 L/S 1.0 kW Reheat",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "VAV-09"
    assert d["inlet_diameter_mm"] == 150
    assert d["reheat_capacity_kw"] == 1.0
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"vav_{i}", "text": "VAV-01 Terminal Box", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_vav_terminal_unit_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_vav_terminal_unit_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Plasterboard partition wall", "coordinates": (0.0, 0.0)}]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "vav_def",
        "text": "Variable Air Volume Terminal Unit",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "VAV-ITEM"
    assert c.unit_type == "SINGLE_DUCT_VAV"
    assert c.reheat_type == "NO_REHEAT"
    assert c.has_discharge_attenuator is False


def test_large_diameter_spigot_400():
    texts = [{
        "id": "vav_large",
        "text": "VAV-10 Single Duct VAV Box 400mm Collar 800 L/S",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.inlet_diameter_mm == 400
    assert c.airflow_lps == 800


def test_stepped_electric_heater():
    texts = [{
        "id": "vav_stepped",
        "text": "TU-11 Terminal Unit with 4.5 kW Electric Heater Battery",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_vav_terminal_unit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.reheat_type == "ELECTRIC_REHEAT"
    assert c.reheat_capacity_kw == 4.5
