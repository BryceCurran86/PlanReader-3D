"""Tests for Building Automation System (BAS/BMS) Direct Digital Controller (DDC) Panel Shadow Authority."""

import pytest
from pb_source_bas_ddc_control_panel_enclosure_shadow import (
    BASDDCPanelCandidate,
    extract_bas_ddc_panel_items,
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


def test_main_plant_ddc_panel():
    texts = [{
        "id": "ddc_1",
        "text": "DDC-01 Main Central Plant DDC Panel 128 I/O Points BACnet/IP with UPS Backup in 1200x1000x300mm IP54 Enclosure",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "DDC-01"
    assert c.panel_type == "MAIN_PLANT_DDC"
    assert c.io_point_capacity == 128
    assert c.comm_protocol == "BACNET_IP"
    assert c.has_ups_backup is True
    assert c.ip_rating == "IP54"
    assert c.enclosure_size_desc == "1200x1000x300mm"


def test_floor_ddc_ahu_controller():
    texts = [{
        "id": "ddc_2",
        "text": "BMS-CP-02 Level 1 Floor DDC Panel AHU Controls 64 I/O Points BACnet MS/TP IP54",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BMS-CP-02"
    assert c.panel_type == "FLOOR_DDC"
    assert c.io_point_capacity == 64
    assert c.comm_protocol == "BACNET_MSTP"
    assert c.ip_rating == "IP54"


def test_rooftop_weatherproof_ddc():
    texts = [{
        "id": "ddc_3",
        "text": "DDC-03 Rooftop Weatherproof BMS Control Panel IP65 Enclosure Modbus RTU 32 Point",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.panel_type == "ROOFTOP_DDC"
    assert c.ip_rating == "IP65"
    assert c.comm_protocol == "MODBUS_RTU"
    assert c.io_point_capacity == 32


def test_remote_io_panel():
    texts = [{
        "id": "ddc_4",
        "text": "RIO-04 Remote I/O Expansion Panel 16 I/O Points in 600x400x200mm Enclosure",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.panel_type == "REMOTE_IO_PANEL"
    assert c.io_point_capacity == 16


def test_chiller_plant_ddc():
    texts = [{
        "id": "ddc_5",
        "text": "BCP-05 Chiller Plantroom BMS Control Panel 96 Point Controller BACnet/IP",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.panel_type == "MAIN_PLANT_DDC"
    assert c.io_point_capacity == 96


def test_lonworks_protocol():
    texts = [{
        "id": "ddc_6",
        "text": "DDC-06 Building Automation Panel LonWorks FTT-10 Network 32 I/O",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.comm_protocol == "LONWORKS"


def test_ip66_heavy_duty_enclosure():
    texts = [{
        "id": "ddc_7",
        "text": "DDC-07 Outdoor Plant DDC Enclosure IP66 Stainless Steel",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.ip_rating == "IP66"


def test_negative_lookalike_switchboard():
    texts = [{
        "id": "neg_1",
        "text": "MSB-01 Main Switchboard 1600A Form 4b",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_fire_alarm():
    texts = [{
        "id": "neg_2",
        "text": "FACP-02 Fire Alarm Control Panel and EWIS Master",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_mcc():
    texts = [{
        "id": "neg_3",
        "text": "MCC-03 Mechanical Motor Control Centre VSD Starters",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "ddc_8",
        "text": "DDC-08 Direct Digital Controller Panel",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "ddc_9",
        "text": "DDC-09: 64 I/O Point DDC Panel",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "DDC-09"
    assert d["io_point_capacity"] == 64
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"ddc_{i}", "text": "DDC-01 Building Automation Panel", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_bas_ddc_panel_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_bas_ddc_panel_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Timber door solid core 40mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "ddc_def",
        "text": "Direct Digital Control Enclosure",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "DDC-PANEL"
    assert c.panel_type == "FLOOR_DDC"
    assert c.ip_rating == "IP54"
    assert c.comm_protocol == "BACNET_IP"
    assert c.has_ups_backup is False


def test_battery_backup_phrase():
    texts = [{
        "id": "ddc_batt",
        "text": "DDC-10 BMS Panel with Battery Backup 32 Point",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.has_ups_backup is True


def test_boiler_room_main_plant():
    texts = [{
        "id": "ddc_boiler",
        "text": "DDC-11 Boiler Plantroom BMS Panel BACnet/IP",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_bas_ddc_panel_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.panel_type == "MAIN_PLANT_DDC"
