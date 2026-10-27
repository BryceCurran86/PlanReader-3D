"""Tests for Cold Water Pressure Booster Pump Hydro-Pneumatic Variable Speed Skid Shadow Authority."""

import pytest
from pb_source_potable_water_booster_pump_skid_shadow import (
    PotableWaterBoosterCandidate,
    extract_potable_water_booster_items,
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


def test_duplex_vfd_booster_skid():
    texts = [{
        "id": "cwp_1",
        "text": "CWP-01 Duplex Potable Water Booster Pump Skid 5.5 L/S at 45m Head with Integral VFD and 100L Pressure Vessel Stainless 304 Manifold",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "CWP-01"
    assert c.skid_configuration == "DUPLEX"
    assert c.pump_count == 2
    assert c.flow_rate_lps == 5.5
    assert c.design_head_m == 45.0
    assert c.pressure_vessel_litres == 100
    assert c.has_vfd_control is True
    assert c.manifold_material == "STAINLESS_304"


def test_triplex_commercial_booster():
    texts = [{
        "id": "cwp_2",
        "text": "BPS-02 Triplex Cold Water Booster Set 3-Pump 12.0 L/S 60m Head with 200L Diaphragm Tank and Anti-Vibration Spring Mounts",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BPS-02"
    assert c.skid_configuration == "TRIPLEX"
    assert c.pump_count == 3
    assert c.flow_rate_lps == 12.0
    assert c.design_head_m == 60.0
    assert c.pressure_vessel_litres == 200
    assert c.has_anti_vibration_mounts is True


def test_quadruplex_high_rise_booster():
    texts = [{
        "id": "cwp_3",
        "text": "DWP-03 Quadruplex High Rise Water Booster Pump Skid 4-Pump Variable Frequency Inverter 25.0 L/S 95m Head Stainless 316",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.skid_configuration == "QUADRUPLEX"
    assert c.pump_count == 4
    assert c.flow_rate_lps == 25.0
    assert c.design_head_m == 95.0
    assert c.manifold_material == "STAINLESS_316"
    assert c.has_vfd_control is True


def test_simplex_domestic_booster():
    texts = [{
        "id": "cwp_4",
        "text": "BOOST-04 Simplex Domestic Water Pressure Booster Pump 1.5 L/S 30m with 24L Pressure Vessel",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.skid_configuration == "SIMPLEX"
    assert c.pump_count == 1
    assert c.flow_rate_lps == 1.5
    assert c.design_head_m == 30.0
    assert c.pressure_vessel_litres == 24


def test_copper_manifold_option():
    texts = [{
        "id": "cwp_5",
        "text": "CWP-05 Duplex Water Booster Pump Set Copper Manifolds 50L Vessel",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.manifold_material == "COPPER"
    assert c.pressure_vessel_litres == 50


def test_inertia_base_vibration_isolation():
    texts = [{
        "id": "cwp_6",
        "text": "SKID-06 Potable Water Booster Skid mounted on Concrete Inertia Base with Spring Mounts",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.has_anti_vibration_mounts is True


def test_vsd_inverter_detection():
    texts = [{
        "id": "cwp_7",
        "text": "PUMP-07 Cold Water Booster Pump Variable Speed VSD Control 8.0 L/S",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.has_vfd_control is True
    assert c.flow_rate_lps == 8.0


def test_negative_lookalike_fire_pump():
    texts = [{
        "id": "neg_1",
        "text": "Fire Sprinkler Diesel Booster Pump 50 L/S at 120m Head",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_sewage_ejector():
    texts = [{
        "id": "neg_2",
        "text": "Sewage Ejector Submersible Sump Pump Duplex Set",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_chilled_water():
    texts = [{
        "id": "neg_3",
        "text": "CHWP-01 Chilled Water Pump Secondary Variable Speed",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "cwp_8",
        "text": "CWP-08 Potable Water Booster Pump",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "cwp_9",
        "text": "CWP-09: Duplex Water Booster 4.0 L/S",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "CWP-09"
    assert d["flow_rate_lps"] == 4.0
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"cwp_{i}", "text": "CWP-01 Water Booster Pump", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_potable_water_booster_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_potable_water_booster_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Suspended plasterboard ceiling", "coordinates": (0.0, 0.0)}]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "cwp_def",
        "text": "Potable Water Booster Pump Package",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "CWP-SKID"
    assert c.skid_configuration == "DUPLEX"
    assert c.pump_count == 2
    assert c.manifold_material == "STAINLESS_304"
    assert c.has_vfd_control is False
    assert c.has_anti_vibration_mounts is False


def test_large_expansion_vessel_500l():
    texts = [{
        "id": "cwp_large_vessel",
        "text": "CWP-10 Triplex Booster Skid with 500L Diaphragm Tank",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.pressure_vessel_litres == 500


def test_duty_standby_wording():
    texts = [{
        "id": "cwp_ds",
        "text": "DWP-11 Duty/Standby Domestic Water Booster Pumps 3.5 L/S",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_potable_water_booster_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.skid_configuration == "DUPLEX"
    assert c.pump_count == 2
    assert c.flow_rate_lps == 3.5
