"""Unit tests for Source Swimming Pool Overflow Scupper & Perimeter Balance Tank Shadow Authority."""

import pytest
from pb_source_pool_scupper_balance_tank_shadow import (
    PoolBalanceTankCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_pool_scupper_balance_tank_callout,
    evaluate_pool_scupper_balance_tank_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((2.6, 5.1)) == (2.5, 5.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_snap_polyline_removes_duplicates():
    pts = [(0.0, 0.0), (0.2, 0.3), (50.0, 50.0)]
    snapped = snap_polyline(pts)
    assert len(snapped) == 2
    assert snapped[0] == (0.0, 0.0)
    assert snapped[1] == (50.0, 50.0)


def test_calculate_polyline_length():
    pts = [(0.0, 0.0), (0.0, 100.0)]
    assert calculate_polyline_length(pts) == 100.0


def test_parse_pool_scupper_callout_standard_wet_deck():
    text = "WET DECK GUTTER 250X200 WITH POLYPROPYLENE TRANSVERSE GRATING DN200 DRAIN"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["system_type"] == "WET_DECK_OVERFLOW_GUTTER"
    assert parsed["grating_material"] == "POLYPROPYLENE_TRANSVERSE"
    assert parsed["gutter_width_mm"] == 250.0
    assert parsed["gutter_depth_mm"] == 200.0
    assert parsed["drain_pipe_dia_mm"] == 200.0


def test_parse_pool_scupper_callout_stainless_wedge_wire():
    text = "POOL OVERFLOW SCUPPER STAINLESS 316 WEDGE WIRE GRATING WITH LEVEL SENSOR"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["grating_material"] == "STAINLESS_STEEL_WEDGE_WIRE"
    assert parsed["level_sensors"] is True


def test_parse_pool_scupper_callout_balance_tank_litres():
    text = "CONCRETE BALANCE TANK 25,000L WITH FLOAT SWITCH AND DN250 OVERFLOW"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["system_type"] == "BALANCE_TANK"
    assert parsed["balance_tank_capacity_litres"] == 25000.0
    assert parsed["level_sensors"] is True
    assert parsed["drain_pipe_dia_mm"] == 250.0


def test_parse_pool_scupper_callout_balance_tank_m3():
    text = "SURGE TANK 20M3 CAPACITY"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["system_type"] == "BALANCE_TANK"
    assert parsed["balance_tank_capacity_litres"] == 20000.0


def test_parse_pool_scupper_callout_slot_drain():
    text = "PERIMETER SCUPPER FINGER SAFE SLOT DRAIN"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["grating_material"] == "FINGER_SAFE_SLOT_DRAIN"


def test_parse_pool_scupper_callout_unrelated():
    assert parse_pool_scupper_balance_tank_callout("HOT WATER RETICULATION PIPE") is None


def test_evaluate_pool_scupper_balance_tank_shadow_single():
    callouts = ["WET DECK GUTTER 250X200 POLYPROPYLENE"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_pool_scupper_balance_tank_shadow("H-401", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "H-401_pbt_001"
    assert c.sheet_id == "H-401"
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_pool_scupper_balance_tank_shadow_dict():
    c = PoolBalanceTankCandidate(
        candidate_id="H-402_pbt_001",
        sheet_id="H-402",
        system_type="BALANCE_TANK",
        grating_material="POLYPROPYLENE_TRANSVERSE",
        gutter_width_mm=250.0,
        gutter_depth_mm=200.0,
        balance_tank_capacity_litres=20000.0,
        drain_pipe_dia_mm=200.0,
        level_sensors=True,
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "H-402_pbt_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["balance_tank_capacity_litres"] == 20000.0


def test_evaluate_pool_scupper_balance_tank_shadow_no_polys():
    callouts = ["BALANCE TANK 20KL"]
    res = evaluate_pool_scupper_balance_tank_shadow("H-403", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_pool_scupper_balance_tank_shadow_safety_cap():
    callouts = ["WET DECK GUTTER"] * 10
    res = evaluate_pool_scupper_balance_tank_shadow("H-404", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_pool_scupper_balance_tank_shadow("H-405", []) == []


def test_unrelated_callout_filtering():
    callouts = ["CONCRETE KERB", "WET DECK GUTTER 250X200"]
    res = evaluate_pool_scupper_balance_tank_shadow("H-406", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "H-406_pbt_002"


def test_kl_capacity():
    text = "BALANCE TANK 15 KL CAPACITY"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["balance_tank_capacity_litres"] == 15000.0


def test_ultrasonic_level_sensor():
    text = "BALANCE TANK WITH ULTRASONIC LEVEL CONTROL"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["level_sensors"] is True


def test_default_values():
    text = "POOL OVERFLOW"
    parsed = parse_pool_scupper_balance_tank_callout(text)
    assert parsed is not None
    assert parsed["system_type"] == "WET_DECK_OVERFLOW_GUTTER"
    assert parsed["grating_material"] == "POLYPROPYLENE_TRANSVERSE"
    assert parsed["gutter_width_mm"] == 250.0
    assert parsed["gutter_depth_mm"] == 200.0
    assert parsed["drain_pipe_dia_mm"] == 200.0
    assert parsed["level_sensors"] is False


def test_snapping_precision():
    callouts = ["WET DECK GUTTER"]
    polys = [[(1.1, 1.1), (28.9, 1.1)]]
    res = evaluate_pool_scupper_balance_tank_shadow("H-407", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (30.0, 0.0)
    assert res[0].length_pt == 30.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0
