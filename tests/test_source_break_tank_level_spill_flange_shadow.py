"""
Unit and adversarial test suite for Source Cold Water Storage Tank Break Tank Level Transmitter & Spill Flange Shadow Authority.
"""

import pytest
from pb_source_break_tank_level_spill_flange_shadow import (
    BreakTankLevelSpillFlangeCallout,
    SourceBreakTankLevelSpillFlangeShadowAuthority,
    parse_break_tank_level_spill_flange_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_break_tank_complete():
    text = "POTABLE WATER TANK: 25,000L BREAK TANK, HYDROSTATIC LEVEL TRANSMITTER, OVERFLOW SPILL FLANGE DN150, TYPE AA AIR GAP"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["tank_type"] == "BREAK_TANK_POTABLE"
    assert res["effective_capacity_litres"] == 25000.0
    assert res["level_transmitter_type"] == "HYDROSTATIC_SUBMERSIBLE_PRESSURE"
    assert res["overflow_spill_flange_dn"] == "DN150"
    assert res["air_gap_type"] == "TYPE_AA_AIR_GAP"


def test_parse_rainwater_tank_ultrasonic():
    text = "NON-POTABLE RAINWATER TANK: 50000L STORAGE, ULTRASONIC LEVEL SENSOR, DN200 OVERFLOW, TYPE AB AIR GAP"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["tank_type"] == "NON_POTABLE_RAINWATER_TANK"
    assert res["effective_capacity_litres"] == 50000.0
    assert res["level_transmitter_type"] == "ULTRASONIC_NON_CONTACT"
    assert res["overflow_spill_flange_dn"] == "DN200"
    assert res["air_gap_type"] == "TYPE_AB_NON_CIRCULAR_OVERFLOW"


def test_parse_fire_tank_radar():
    text = "FIRE WATER STORAGE TANK: 120,000L WITH GUIDED WAVE RADAR LEVEL TRANSMITTER"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["tank_type"] == "FIRE_WATER_STORAGE_TANK"
    assert res["effective_capacity_litres"] == 120000.0
    assert res["level_transmitter_type"] == "RADAR_GUIDED_WAVE"


def test_parse_header_tank_float():
    text = "HEADER TANK: 5,000 LITRES WITH MULTI-POINT FLOAT LEVEL SWITCH AND TYPE AF AIR GAP"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["tank_type"] == "HEADER_TANK"
    assert res["effective_capacity_litres"] == 5000.0
    assert res["level_transmitter_type"] == "MULTI_POINT_CONDUCTIVITY_FLOAT"
    assert res["air_gap_type"] == "TYPE_AF_DROPLET_AIR_GAP"


def test_parse_defaults():
    text = "BREAK TANK"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["tank_type"] == "BREAK_TANK_POTABLE"
    assert res["effective_capacity_litres"] == 10000.0
    assert res["level_transmitter_type"] == "HYDROSTATIC_SUBMERSIBLE_PRESSURE"
    assert res["overflow_spill_flange_dn"] == "DN100"
    assert res["air_gap_type"] == "TYPE_AA_AIR_GAP"


def test_parse_unrelated_text_returns_none():
    assert parse_break_tank_level_spill_flange_callout("CARPET TILES IN OFFICE 102") is None
    assert parse_break_tank_level_spill_flange_callout("GYPROCK CEILING ACCESS PANEL") is None


def test_snap_point_regular():
    pt = snap_point(18.3, 31.8, snap_tol=2.5)
    assert pt == (17.5, 32.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(18.34, 31.87, snap_tol=0.0)
    assert pt == (18.34, 31.87)


def test_authority_processing_batch():
    auth = SourceBreakTankLevelSpillFlangeShadowAuthority()
    candidates = [
        ("BREAK TANK 10,000L", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("RAINWATER TANK DN150 OVERFLOW", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].tank_type == "NON_POTABLE_RAINWATER_TANK"


def test_safety_primitive_cap():
    auth = SourceBreakTankLevelSpillFlangeShadowAuthority()
    large_list = [("BREAK TANK", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = BreakTankLevelSpillFlangeCallout(
        raw_text="SAMPLE",
        tank_type="BREAK_TANK_POTABLE",
        effective_capacity_litres=10000.0,
        level_transmitter_type="HYDROSTATIC_SUBMERSIBLE_PRESSURE",
        overflow_spill_flange_dn="DN100",
        air_gap_type="TYPE_AA_AIR_GAP",
    )
    with pytest.raises(Exception):
        callout.effective_capacity_litres = 20000.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   cold water tank: 15000 l storage with pressure transmitter   "
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["effective_capacity_litres"] == 15000.0
    assert res["level_transmitter_type"] == "HYDROSTATIC_SUBMERSIBLE_PRESSURE"


def test_spill_flange_trigger():
    text = "SPILL FLANGE DN200 ON WATER STORAGE TANK"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["overflow_spill_flange_dn"] == "DN200"


def test_custom_snap_tolerance():
    auth = SourceBreakTankLevelSpillFlangeShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("BREAK TANK", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceBreakTankLevelSpillFlangeShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_submersible_level_probe():
    text = "BREAK TANK WITH SUBMERSIBLE LEVEL PROBE TRANSMITTER"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["level_transmitter_type"] == "HYDROSTATIC_SUBMERSIBLE_PRESSURE"


def test_recycled_water_tank():
    text = "RECYCLED WATER TANK: 30,000L CAPACITY"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["tank_type"] == "NON_POTABLE_RAINWATER_TANK"
    assert res["effective_capacity_litres"] == 30000.0


def test_overflow_flange_trigger():
    text = "WATER STORAGE TANK WITH OVERFLOW FLANGE DN150"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["overflow_spill_flange_dn"] == "DN150"


def test_type_ab_air_gap_variant():
    text = "BREAK TANK: TYPE-AB AIR GAP SPILL WEIR"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["air_gap_type"] == "TYPE_AB_NON_CIRCULAR_OVERFLOW"


def test_type_af_air_gap_variant():
    text = "COLD WATER BREAK TANK: TYPE-AF AIR GAP"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["air_gap_type"] == "TYPE_AF_DROPLET_AIR_GAP"


def test_adversarial_special_characters():
    text = "BREAK TANK @@@ [20,000L] +++ (DN150 SPILL) // TYPE AA *** ULTRASONIC ###"
    res = parse_break_tank_level_spill_flange_callout(text)
    assert res is not None
    assert res["effective_capacity_litres"] == 20000.0
    assert res["overflow_spill_flange_dn"] == "DN150"
    assert res["level_transmitter_type"] == "ULTRASONIC_NON_CONTACT"
    assert res["air_gap_type"] == "TYPE_AA_AIR_GAP"
