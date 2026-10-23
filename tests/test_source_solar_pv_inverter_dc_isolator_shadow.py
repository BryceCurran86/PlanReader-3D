"""Tests for Solar PV Roof Array DC Isolator Switch & Inverter Shadow Authority."""

import pytest
from pb_source_solar_pv_inverter_dc_isolator_shadow import (
    SolarPVItemCandidate,
    extract_solar_pv_items,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_dc_isolator():
    data = [{"id": "p1", "text": "DCI-01 ROOFTOP DC ISOLATOR 1000V 32A IP66 WITH SUNSHADE", "coordinates": (100.2, 200.4)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].element_type == "DC_ISOLATOR"
    assert res[0].tag == "DCI-01"
    assert res[0].voltage_rating_v == 1000
    assert res[0].current_rating_a == 32
    assert res[0].ip_rating == "IP66"
    assert res[0].mounting_type == "SHADE_COVERED"


def test_string_inverter_extraction():
    data = [{"id": "p2", "text": "INV-01 50KW SOLAR STRING INVERTER 4 MPPT WALL MOUNTED", "coordinates": (50.0, 75.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].element_type == "STRING_INVERTER"
    assert res[0].tag == "INV-01"
    assert res[0].power_rating_kw == 50.0
    assert res[0].mppt_channels == 4
    assert res[0].mounting_type == "WALL_MOUNTED"


def test_central_inverter_extraction():
    data = [{"id": "p3", "text": "INV-02 250KW CENTRAL INVERTER IP56", "coordinates": (10.0, 20.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].element_type == "CENTRAL_INVERTER"
    assert res[0].power_rating_kw == 250.0
    assert res[0].ip_rating == "IP56"


def test_dc_combiner_box():
    data = [{"id": "p4", "text": "CB-01 DC COMBINER BOX 1500V IP65", "coordinates": (0.0, 0.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].element_type == "COMBINER_BOX"
    assert res[0].tag == "CB-01"
    assert res[0].voltage_rating_v == 1500
    assert res[0].ip_rating == "IP65"


def test_1500v_dc_isolator():
    data = [{"id": "p5", "text": "DC ISOLATOR 1500V 40A IP66", "coordinates": (15.0, 15.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].voltage_rating_v == 1500
    assert res[0].current_rating_a == 40
    assert res[0].ip_rating == "IP66"


def test_kva_rating_inverter():
    data = [{"id": "p6", "text": "PV-INV-1 100KVA SOLAR INVERTER", "coordinates": (25.0, 25.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].power_rating_kw == 100.0


def test_roof_mounted_mounting_type():
    data = [{"id": "p7", "text": "ROOF MOUNTED DC ISOLATOR SWITCH", "coordinates": (30.0, 60.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].mounting_type == "ROOF_MOUNTED"


def test_mppt_channel_count():
    data = [{"id": "p8", "text": "SOLAR INVERTER WITH 8 MPPT", "coordinates": (40.0, 80.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].mppt_channels == 8


def test_pv_array_item():
    data = [{"id": "p9", "text": "SOLAR PV ARRAY ROOFTOP ISOLATOR 600V DC", "coordinates": (50.0, 100.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].voltage_rating_v == 600


def test_negative_ac_isolator():
    data = [{"id": "n1", "text": "AC ISOLATOR 415V 63A", "coordinates": (0.0, 0.0)}]
    assert len(extract_solar_pv_items(data)) == 0


def test_negative_main_switchboard():
    data = [{"id": "n2", "text": "MAIN SWITCHBOARD MSB-1", "coordinates": (0.0, 0.0)}]
    assert len(extract_solar_pv_items(data)) == 0


def test_negative_distribution_board():
    data = [{"id": "n3", "text": "DISTRIBUTION BOARD DB-L1", "coordinates": (0.0, 0.0)}]
    assert len(extract_solar_pv_items(data)) == 0


def test_negative_smoke_damper():
    data = [{"id": "n4", "text": "SMOKE DAMPER SD-01", "coordinates": (0.0, 0.0)}]
    assert len(extract_solar_pv_items(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((17.4, 32.6), tolerance=2.5)
    assert pt == (17.5, 32.5)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "DCI-1 DC ISOLATOR 1000V", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_solar_pv_items(items, max_primitives=35)
    assert len(res) == 35


def test_candidate_guardrails_default():
    candidate = SolarPVItemCandidate(
        item_id="cand_1",
        element_type="DC_ISOLATOR",
        tag="DCI-01",
        power_rating_kw=None,
        voltage_rating_v=1000,
        current_rating_a=32,
        ip_rating="IP66",
        mounting_type="SHADE_COVERED",
        mppt_channels=None,
        coordinates=(10.0, 20.0),
        raw_text="DCI-01 DC ISOLATOR",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = SolarPVItemCandidate(
        item_id="cand_2",
        element_type="STRING_INVERTER",
        tag="INV-01",
        power_rating_kw=50.0,
        voltage_rating_v=None,
        current_rating_a=None,
        ip_rating="IP65",
        mounting_type="WALL_MOUNTED",
        mppt_channels=4,
        coordinates=(0.0, 0.0),
        raw_text="INV-01 50KW INVERTER",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "p10", "text": "INV-03 25KW SOLAR INVERTER IP65", "coordinates": (30.0, 40.0)}]
    res = extract_solar_pv_items(data)
    d = res[0].to_dict()
    assert d["element_type"] == "STRING_INVERTER"
    assert d["power_rating_kw"] == 25.0
    assert d["ip_rating"] == "IP65"
    assert d["status"] == "CANDIDATE"


def test_decimal_power_kw():
    data = [{"id": "p11", "text": "8.5KW SOLAR INVERTER 2 MPPT", "coordinates": (5.0, 5.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].power_rating_kw == 8.5
    assert res[0].mppt_channels == 2


def test_ip_spacing_cleanup():
    data = [{"id": "p12", "text": "DC ISOLATOR IP 66 WEATHERPROOF", "coordinates": (10.0, 10.0)}]
    res = extract_solar_pv_items(data)
    assert len(res) == 1
    assert res[0].ip_rating == "IP66"
