"""Tests for HVAC VRF / VRV Branch Selector Box & Refnet Joint Shadow Authority."""

import pytest
from pb_source_vrf_branch_selector_refnet_joint_shadow import (
    VRFComponentCandidate,
    extract_vrf_components,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_multi_port_bs_box():
    data = [{
        "id": "v1",
        "text": "BS-01 4-PORT VRF BRANCH SELECTOR BOX 3-PIPE HEAT RECOVERY 230V POWER WITH CONDENSATE DRAIN",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].element_type == "BRANCH_SELECTOR_BOX"
    assert res[0].tag == "BS-01"
    assert res[0].port_count == 4
    assert res[0].system_architecture == "HEAT_RECOVERY_3_PIPE"
    assert res[0].requires_power_supply is True
    assert res[0].has_condensate_drain is True


def test_single_port_bs_box():
    data = [{
        "id": "v2",
        "text": "BSB-1 SINGLE PORT MODE CONTROL UNIT NO DRAIN REQUIRED",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].element_type == "BRANCH_SELECTOR_BOX"
    assert res[0].tag == "BSB-1"
    assert res[0].port_count == 1
    assert res[0].has_condensate_drain is False


def test_refnet_joint_binary_branch():
    data = [{
        "id": "v3",
        "text": "RJ-01 REFRIGERANT REFNET JOINT 9.52MM LIQUID 19.05MM GAS",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].element_type == "REFNET_JOINT"
    assert res[0].tag == "RJ-01"
    assert res[0].port_count == 2
    assert res[0].liquid_pipe_mm == 9.52
    assert res[0].gas_pipe_mm == 19.05


def test_refnet_header_multi_branch():
    data = [{
        "id": "v4",
        "text": "RH-1 6-PORT REFNET HEADER MANIFOLD",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].element_type == "REFNET_HEADER"
    assert res[0].port_count == 6


def test_8_port_mcu():
    data = [{
        "id": "v5",
        "text": "MCU-02 8-BRANCH MODE CONTROL UNIT 240V",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].element_type == "BRANCH_SELECTOR_BOX"
    assert res[0].port_count == 8
    assert res[0].requires_power_supply is True


def test_heat_pump_2_pipe():
    data = [{
        "id": "v6",
        "text": "VRF BRANCH Y-JOINT 2-PIPE HEAT PUMP SYSTEM",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].system_architecture == "HEAT_PUMP_2_PIPE"


def test_water_cooled_vrf():
    data = [{
        "id": "v7",
        "text": "BS BOX FOR WATER-COOLED VRF 4 PORT",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].system_architecture == "WATER_COOLED"
    assert res[0].port_count == 4


def test_pipe_size_extraction():
    data = [{
        "id": "v8",
        "text": "REFNET JOINT 12.7MM AND 22.2MM",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].liquid_pipe_mm == 12.7
    assert res[0].gas_pipe_mm == 22.2


def test_condensate_tray_detection():
    data = [{
        "id": "v9",
        "text": "BRANCH SELECTOR WITH CONDENSATE TRAY AND DRAIN CONNECTION",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].has_condensate_drain is True


def test_comm_powered_box():
    data = [{
        "id": "v10",
        "text": "BS BOX COMM POWERED NO DRAIN",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].requires_power_supply is False
    assert res[0].has_condensate_drain is False


def test_negative_chilled_water():
    data = [{"id": "n1", "text": "CHILLED WATER FCU FAN COIL UNIT", "coordinates": (0.0, 0.0)}]
    assert len(extract_vrf_components(data)) == 0


def test_negative_air_dirt_separator():
    data = [{"id": "n2", "text": "HYDRONIC AIR DIRT SEPARATOR DN100", "coordinates": (0.0, 0.0)}]
    assert len(extract_vrf_components(data)) == 0


def test_negative_vav_box():
    data = [{"id": "n3", "text": "VAV BOX 01 WITH REHEAT", "coordinates": (0.0, 0.0)}]
    assert len(extract_vrf_components(data)) == 0


def test_negative_fire_damper():
    data = [{"id": "n4", "text": "FIRE DAMPER 600x300", "coordinates": (0.0, 0.0)}]
    assert len(extract_vrf_components(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((22.4, 45.1), tolerance=2.5)
    assert pt == (22.5, 45.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "BS-1 BRANCH SELECTOR BOX", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_vrf_components(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = VRFComponentCandidate(
        item_id="cand_1",
        element_type="BRANCH_SELECTOR_BOX",
        tag="BS-01",
        port_count=4,
        system_architecture="HEAT_RECOVERY_3_PIPE",
        has_condensate_drain=True,
        requires_power_supply=True,
        liquid_pipe_mm=9.52,
        gas_pipe_mm=19.05,
        coordinates=(10.0, 20.0),
        raw_text="BS-01 4-PORT BOX",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = VRFComponentCandidate(
        item_id="cand_2",
        element_type="REFNET_JOINT",
        tag="RJ-01",
        port_count=2,
        system_architecture="HEAT_PUMP_2_PIPE",
        has_condensate_drain=False,
        requires_power_supply=False,
        liquid_pipe_mm=None,
        gas_pipe_mm=None,
        coordinates=(0.0, 0.0),
        raw_text="RJ-01 REFNET",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "v11",
        "text": "BS-05 6-PORT VRF BRANCH SELECTOR BOX",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_vrf_components(data)
    d = res[0].to_dict()
    assert d["tag"] == "BS-05"
    assert d["port_count"] == 6
    assert d["status"] == "CANDIDATE"


def test_hrv_tag_detection():
    data = [{
        "id": "v12",
        "text": "HRV-03 HEAT RECOVERY BOX 8 PORT",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_vrf_components(data)
    assert len(res) == 1
    assert res[0].tag == "HRV-03"
    assert res[0].port_count == 8
