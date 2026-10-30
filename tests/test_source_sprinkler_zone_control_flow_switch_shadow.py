"""Tests for Fire Sprinkler Floor Zone Control Valve & Waterflow Detector Switch Shadow Authority."""

import pytest
from pb_source_sprinkler_zone_control_flow_switch_shadow import (
    SprinklerZoneControlCandidate,
    extract_sprinkler_zone_controls,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_zone_control_assembly():
    data = [{
        "id": "z1",
        "text": "ZCV-01 DN100 SPRINKLER ZONE CONTROL VALVE ASSEMBLY WITH SUPERVISED BUTTERFLY AND VANE FLOW SWITCH",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].element_type == "ZONE_CONTROL_ASSEMBLY"
    assert res[0].tag == "ZCV-01"
    assert res[0].pipe_size_mm == 100
    assert res[0].valve_type == "BUTTERFLY_MONITORED"
    assert res[0].has_tamper_switch is True
    assert res[0].has_flow_switch is True
    assert res[0].has_test_and_drain is True


def test_standalone_flow_switch():
    data = [{
        "id": "z2",
        "text": "FS-1 DN150 VANE-TYPE WATERFLOW DETECTOR SWITCH",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].element_type == "FLOW_SWITCH"
    assert res[0].tag == "FS-1"
    assert res[0].pipe_size_mm == 150
    assert res[0].has_flow_switch is True


def test_test_and_drain_valve():
    data = [{
        "id": "z3",
        "text": "TDV-02 DN50 COMBINATION TEST AND DRAIN VALVE WITH 1/2 INCH ORIFICE",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].element_type == "TEST_DRAIN_VALVE"
    assert res[0].pipe_size_mm == 50
    assert res[0].test_orifice_size_mm == 12.7


def test_inspector_test_connection():
    data = [{
        "id": "z4",
        "text": "ITC-01 INSPECTOR TEST CONNECTION WITH K=80 ORIFICE DN25",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].element_type == "INSPECTOR_TEST"
    assert res[0].test_orifice_size_mm == 80.0


def test_osy_gate_valve_zone_control():
    data = [{
        "id": "z5",
        "text": "ZCA-L2 DN150 ZONE CONTROL WITH OS&Y GATE VALVE MONITORED",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].valve_type == "OS_AND_Y_GATE"
    assert res[0].pipe_size_mm == 150
    assert res[0].has_tamper_switch is True


def test_ball_valve_zone_control():
    data = [{
        "id": "z6",
        "text": "ZCV-3 DN50 ZONE CONTROL WITH BALL VALVE",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].valve_type == "BALL_VALVE"
    assert res[0].pipe_size_mm == 50


def test_inch_pipe_size_conversion():
    data = [{
        "id": "z7",
        "text": "ZCV 2.5 INCH SPRINKLER CONTROL VALVE",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].pipe_size_mm == 64  # round(2.5 * 25.4)


def test_four_inch_pipe_size():
    data = [{
        "id": "z8",
        "text": "4 INCH FLOOR CONTROL VALVE ASSEMBLY",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].pipe_size_mm == 102  # round(4 * 25.4)


def test_wfd_tag_detection():
    data = [{
        "id": "z9",
        "text": "WFD-03 WATERFLOW DETECTOR DN100",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].tag == "WFD-03"
    assert res[0].element_type == "FLOW_SWITCH"


def test_half_inch_quote_orifice():
    data = [{
        "id": "z10",
        "text": "TEST AND DRAIN WITH 1/2\" TEST ORIFICE",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].test_orifice_size_mm == 12.7


def test_negative_gas_valve():
    data = [{"id": "n1", "text": "GAS SOLENOID VALVE DN50", "coordinates": (0.0, 0.0)}]
    assert len(extract_sprinkler_zone_controls(data)) == 0


def test_negative_chw_balancing():
    data = [{"id": "n2", "text": "CHW BALANCING VALVE DN100", "coordinates": (0.0, 0.0)}]
    assert len(extract_sprinkler_zone_controls(data)) == 0


def test_negative_domestic_water():
    data = [{"id": "n3", "text": "DOMESTIC WATER ISOLATION VALVE", "coordinates": (0.0, 0.0)}]
    assert len(extract_sprinkler_zone_controls(data)) == 0


def test_negative_air_separator():
    data = [{"id": "n4", "text": "HYDRONIC AIR SEPARATOR DN150", "coordinates": (0.0, 0.0)}]
    assert len(extract_sprinkler_zone_controls(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((24.9, 49.8), tolerance=2.5)
    assert pt == (25.0, 50.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "ZCV-1 SPRINKLER ZONE CONTROL", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_sprinkler_zone_controls(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = SprinklerZoneControlCandidate(
        item_id="cand_1",
        element_type="ZONE_CONTROL_ASSEMBLY",
        tag="ZCV-01",
        pipe_size_mm=100,
        valve_type="BUTTERFLY_MONITORED",
        has_tamper_switch=True,
        has_flow_switch=True,
        has_test_and_drain=True,
        test_orifice_size_mm=12.7,
        coordinates=(10.0, 20.0),
        raw_text="ZCV-01 ZONE CONTROL",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = SprinklerZoneControlCandidate(
        item_id="cand_2",
        element_type="FLOW_SWITCH",
        tag="FS-01",
        pipe_size_mm=150,
        valve_type="STANDARD",
        has_tamper_switch=False,
        has_flow_switch=True,
        has_test_and_drain=False,
        test_orifice_size_mm=None,
        coordinates=(0.0, 0.0),
        raw_text="FS-01 FLOW SWITCH",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "z11",
        "text": "ZCV-05 DN100 ZONE CONTROL VALVE",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    d = res[0].to_dict()
    assert d["tag"] == "ZCV-05"
    assert d["pipe_size_mm"] == 100
    assert d["status"] == "CANDIDATE"


def test_wfs_tag_detection():
    data = [{
        "id": "z12",
        "text": "WFS-2 WATERFLOW SWITCH DN80",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_sprinkler_zone_controls(data)
    assert len(res) == 1
    assert res[0].tag == "WFS-2"
    assert res[0].pipe_size_mm == 80
