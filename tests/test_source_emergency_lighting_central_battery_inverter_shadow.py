"""Tests for Emergency Lighting Central Battery System & Static Inverter Shadow Authority."""

import pytest
from pb_source_emergency_lighting_central_battery_inverter_shadow import (
    CentralBatterySystemCandidate,
    extract_central_battery_systems,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_central_battery_system():
    data = [{
        "id": "c1",
        "text": "CBS-01 10KVA CENTRAL BATTERY SYSTEM 90 MIN DURATION VRLA BATTERY IP31 DALI ADDRESSABLE",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].element_type == "CENTRAL_BATTERY_SYSTEM"
    assert res[0].tag == "CBS-01"
    assert res[0].capacity_kva == 10.0
    assert res[0].autonomy_minutes == 90
    assert res[0].battery_chemistry == "VRLA"
    assert res[0].output_voltage == "230V_1PH"
    assert res[0].is_dali_addressable is True
    assert res[0].ip_rating == "IP31"


def test_static_inverter_three_phase():
    data = [{
        "id": "c2",
        "text": "INV-01 25KVA STATIC INVERTER 400V 3-PHASE 2 HR AUTONOMY LIFEPO4",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].element_type == "STATIC_INVERTER"
    assert res[0].tag == "INV-01"
    assert res[0].capacity_kva == 25.0
    assert res[0].autonomy_minutes == 120
    assert res[0].output_voltage == "400V_3PH"
    assert res[0].battery_chemistry == "LI_ION"


def test_battery_rack_for_emergency():
    data = [{
        "id": "c3",
        "text": "BATTERY RACK FOR EMERGENCY LIGHTING 3 HR AUTONOMY VRLA",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].element_type == "BATTERY_RACK"
    assert res[0].autonomy_minutes == 180


def test_emergency_ups():
    data = [{
        "id": "c4",
        "text": "UPS-EM 15KW EMERGENCY UPS WITH AUTOMATIC TEST SYSTEM",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].element_type == "EMERGENCY_UPS"
    assert res[0].tag == "UPS-EM"
    assert res[0].capacity_kva == 15.0
    assert res[0].is_dali_addressable is True


def test_110v_dc_central_battery():
    data = [{
        "id": "c5",
        "text": "CENTRAL BATTERY SYSTEM 110V DC NICD BATTERIES",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].output_voltage == "110V_DC"
    assert res[0].battery_chemistry == "NICD"


def test_24v_dc_system():
    data = [{
        "id": "c6",
        "text": "CENTRAL BATTERY UNIT 24V DC 60 MIN",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].output_voltage == "24V_DC"
    assert res[0].autonomy_minutes == 60


def test_gel_battery_chemistry():
    data = [{
        "id": "c7",
        "text": "CBS PANEL 5KVA WITH GEL BATTERIES",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].battery_chemistry == "GEL"
    assert res[0].capacity_kva == 5.0


def test_ip54_enclosure():
    data = [{
        "id": "c8",
        "text": "STATIC INVERTER IP 54 DUST PROOF",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].ip_rating == "IP54"


def test_hour_decimal_autonomy():
    data = [{
        "id": "c9",
        "text": "CENTRAL BATTERY SYSTEM 1.5 HR DURATION",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].autonomy_minutes == 90


def test_ats_addressable_testing():
    data = [{
        "id": "c10",
        "text": "CBS-02 WITH ATS ADDRESSABLE TESTING",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].is_dali_addressable is True


def test_negative_solar_inverter():
    data = [{"id": "n1", "text": "SOLAR INVERTER 50KW IP66", "coordinates": (0.0, 0.0)}]
    assert len(extract_central_battery_systems(data)) == 0


def test_negative_motor_starter():
    data = [{"id": "n2", "text": "MOTOR STARTER PANEL 15KW", "coordinates": (0.0, 0.0)}]
    assert len(extract_central_battery_systems(data)) == 0


def test_negative_fire_alarm_panel():
    data = [{"id": "n3", "text": "FIRE ALARM CONTROL PANEL FACP", "coordinates": (0.0, 0.0)}]
    assert len(extract_central_battery_systems(data)) == 0


def test_negative_smoke_damper():
    data = [{"id": "n4", "text": "SMOKE DAMPER SD-01", "coordinates": (0.0, 0.0)}]
    assert len(extract_central_battery_systems(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((14.9, 29.8), tolerance=2.5)
    assert pt == (15.0, 30.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "CBS-1 CENTRAL BATTERY SYSTEM", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_central_battery_systems(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = CentralBatterySystemCandidate(
        item_id="cand_1",
        element_type="CENTRAL_BATTERY_SYSTEM",
        tag="CBS-01",
        capacity_kva=10.0,
        autonomy_minutes=90,
        battery_chemistry="VRLA",
        output_voltage="230V_1PH",
        is_dali_addressable=True,
        ip_rating="IP31",
        coordinates=(10.0, 20.0),
        raw_text="CBS-01 10KVA",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = CentralBatterySystemCandidate(
        item_id="cand_2",
        element_type="STATIC_INVERTER",
        tag="SI-01",
        capacity_kva=20.0,
        autonomy_minutes=120,
        battery_chemistry="LI_ION",
        output_voltage="400V_3PH",
        is_dali_addressable=False,
        ip_rating="IP20",
        coordinates=(0.0, 0.0),
        raw_text="SI-01 INVERTER",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "c11",
        "text": "CBS-05 30KVA CENTRAL BATTERY SYSTEM",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_central_battery_systems(data)
    d = res[0].to_dict()
    assert d["tag"] == "CBS-05"
    assert d["capacity_kva"] == 30.0
    assert d["status"] == "CANDIDATE"


def test_lithium_iron_phosphate_spelling():
    data = [{
        "id": "c12",
        "text": "EMERGENCY BATTERY SYSTEM 10KVA LIFEPO4 90 MIN",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_central_battery_systems(data)
    assert len(res) == 1
    assert res[0].battery_chemistry == "LI_ION"
    assert res[0].autonomy_minutes == 90
