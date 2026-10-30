"""Tests for High-Voltage Electrical Ring Main Unit (RMU) & SF6/Dry Air Switchgear Shadow Authority."""

import pytest
from pb_source_high_voltage_ring_main_unit_rmu_shadow import (
    HighVoltageRMUCandidate,
    extract_high_voltage_rmu_items,
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


def test_11kv_3way_sf6_rmu():
    texts = [{
        "id": "rmu_1",
        "text": "RMU-01 11kV 3-way CCV Ring Main Unit SF6 Gas Insulated 21kA 3s with IAC AFLR Arc Containment",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "RMU-01"
    assert c.switchgear_type == "RING_MAIN_UNIT"
    assert c.rated_voltage_kv == 11
    assert c.switch_function_desc == "3-way CCV"
    assert c.insulation_medium == "SF6_GAS"
    assert c.short_circuit_ka == 21
    assert c.has_iac_arc_containment is True


def test_22kv_4way_dry_air_rmu():
    texts = [{
        "id": "rmu_2",
        "text": "HVSWG-02 22kV 4-way CCVV Ring Main Unit Dry Air SF6-Free Eco Switchgear 25kA",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "HVSWG-02"
    assert c.rated_voltage_kv == 22
    assert c.switch_function_desc == "4-way CCVV"
    assert c.insulation_medium == "DRY_AIR_SF6_FREE"
    assert c.short_circuit_ka == 25


def test_33kv_extensible_switchgear():
    texts = [{
        "id": "rmu_3",
        "text": "SWG-03 33kV Extensible Gas Insulated Switchgear Panel 25kA",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.switchgear_type == "EXTENSIBLE_SWITCHGEAR"
    assert c.rated_voltage_kv == 33
    assert c.short_circuit_ka == 25


def test_hv_metering_unit():
    texts = [{
        "id": "rmu_4",
        "text": "RMU-04 11kV Tariff Metering Unit VT/CT Panel",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.switchgear_type == "METERING_UNIT"
    assert c.rated_voltage_kv == 11


def test_vacuum_circuit_breaker_unit():
    texts = [{
        "id": "rmu_5",
        "text": "VCB-05 11kV Vacuum Circuit Breaker Unit for Transformer Feeder 20kA",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.switchgear_type == "CIRCUIT_BREAKER_UNIT"
    assert c.short_circuit_ka == 20


def test_solid_insulated_medium():
    texts = [{
        "id": "rmu_6",
        "text": "RMU-06 11kV Solid Insulated Switchgear 16kA",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.insulation_medium == "SOLID_INSULATED"
    assert c.short_circuit_ka == 16


def test_negative_lookalike_415v_switchboard():
    texts = [{
        "id": "neg_1",
        "text": "Main Switchboard 415V 2500A Form 4b",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_transformer():
    texts = [{
        "id": "neg_2",
        "text": "Cast Resin Transformer 11kV/415V 1500kVA",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_dc_battery():
    texts = [{
        "id": "neg_3",
        "text": "110V DC Battery Charger and Tripping Unit",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "rmu_7",
        "text": "RMU-07 11kV Ring Main Unit",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "rmu_8",
        "text": "RMU-08: 11kV 20kA RMU",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "RMU-08"
    assert d["rated_voltage_kv"] == 11
    assert d["short_circuit_ka"] == 20
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"rmu_{i}", "text": "RMU-01 11kV Switchgear", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_high_voltage_rmu_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_high_voltage_rmu_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Ceramic wall tiles 200x100", "coordinates": (0.0, 0.0)}]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "rmu_def",
        "text": "High Voltage Ring Main Unit Switchgear",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "RMU-ITEM"
    assert c.switchgear_type == "RING_MAIN_UNIT"
    assert c.insulation_medium == "SF6_GAS"
    assert c.has_iac_arc_containment is False


def test_iac_containment_phrase():
    texts = [{
        "id": "rmu_iac",
        "text": "RMU-09 22kV RMU Internal Arc Classified Substation",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.has_iac_arc_containment is True


def test_31_5ka_breaking_capacity():
    texts = [{
        "id": "rmu_heavy",
        "text": "HVSWG-10 33kV GIS Switchgear 31.5kA Breaking Capacity",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.short_circuit_ka == 32  # rounded float(31.5)
    assert c.rated_voltage_kv == 33


def test_lbs_tag():
    texts = [{
        "id": "rmu_lbs",
        "text": "LBS-11 Load Break Switch 11kV GIS",
        "coordinates": (8.0, 16.0)
    }]
    candidates = extract_high_voltage_rmu_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "LBS-11"
    assert c.rated_voltage_kv == 11
