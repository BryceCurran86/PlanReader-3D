"""
Tests for Source Condenser Water Cooling Tower Side Stream Centrifugal Separator Shadow Authority.
"""

import pytest
from pb_source_cooling_tower_side_stream_separator_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    CoolingTowerSideStreamSeparatorCallout,
    snap_point,
    parse_cooling_tower_side_stream_separator_callout,
    extract_cooling_tower_side_stream_separator_candidates,
    validate_cooling_tower_side_stream_separator_system,
)


def test_snap_point_regular():
    pt = snap_point(22.3, 37.7, snap_tol=2.5)
    assert pt == (22.5, 37.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(22.3, 37.7, snap_tol=0.0)
    assert pt == (22.3, 37.7)


def test_parse_none_on_irrelevant_text():
    assert parse_cooling_tower_side_stream_separator_callout("ALUMINUM DOOR THRESHOLD") is None
    assert parse_cooling_tower_side_stream_separator_callout("FIRE SPRINKLER HEAD PENDENT") is None
    assert parse_cooling_tower_side_stream_separator_callout("SUSPENDED CEILING ACOUSTIC TILE") is None


def test_parse_centrifugal_hydrocyclone_skid():
    text = "COOLING TOWER SIDE STREAM CENTRIFUGAL SEPARATOR SKID 25 L/S DN100 WITH AUTOMATIC MOTORIZED PURGE VALVE AND RECOVERY BAG VESSEL"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "CENTRIFUGAL_HYDROCYCLONE"
    assert parsed["flow_rate_lps"] == 25.0
    assert parsed["nominal_pipe_dn"] == "DN100"
    assert parsed["purge_mechanism"] == "AUTOMATIC_MOTORIZED_PURGE_VALVE"
    assert parsed["solids_recovery_vessel"] == "RECOVERY_BAG_VESSEL"
    assert parsed["pump_skid_mount"] == "SKID_MOUNTED_PACKAGE"


def test_parse_basin_sweeper_system():
    text = "COOLING TOWER BASIN SWEEPER PIPING PACKAGE WITH HYDROCYCLONE SEPARATOR AND EDUCTOR JET NOZZLES"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["service_designation"] == "COOLING_TOWER_BASIN"
    assert parsed["separator_type"] == "CENTRIFUGAL_HYDROCYCLONE"
    assert parsed["pump_skid_mount"] == "BASIN_SUCTION_JET"


def test_parse_gpm_flow_conversion():
    text = "LAKOS SIDE-STREAM SEPARATOR 100 GPM DN80 WITH TIMED PURGE SOLENOID VALVE"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "CENTRIFUGAL_HYDROCYCLONE"
    assert parsed["flow_rate_lps"] == round(100.0 * 0.06309, 2)
    assert parsed["nominal_pipe_dn"] == "DN80"
    assert parsed["purge_mechanism"] == "SOLENOID_TIMED_PURGE"


def test_parse_sand_filter_side_stream():
    text = "CONDENSER WATER SIDE STREAM MULTIMEDIA SAND FILTER 15 LPS WITH BACKWASH BLOWDOWN TO DRAIN"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "SIDE_STREAM_SAND_FILTER"
    assert parsed["flow_rate_lps"] == 15.0
    assert parsed["solids_recovery_vessel"] == "SUMP_BLOWDOWN_DRAIN"


def test_parse_auto_backwash_strainer():
    text = "CONDENSER WATER SIDE STREAM AUTOMATIC BACKWASH STRAINER WITH SEPARATE BOOSTER PUMP"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "AUTOMATIC_BACKWASH_STRAINER"
    assert parsed["pump_skid_mount"] == "SEPARATE_BOOSTER_PUMP"


def test_parse_sludge_settling_chamber():
    text = "VORTEX SEPARATOR FOR COOLING TOWER WITH SLUDGE SETTLING CHAMBER AND MANUAL BLOWDOWN"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["solids_recovery_vessel"] == "SLUDGE_SETTLING_CHAMBER"
    assert parsed["purge_mechanism"] == "MANUAL_BLOWDOWN"


def test_parse_fluid_cooler_service():
    text = "CLOSED CIRCUIT FLUID COOLER SIDE STREAM CENTRIFUGAL SEPARATOR DN50"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["service_designation"] == "CLOSED_CIRCUIT_FLUID_COOLER"
    assert parsed["nominal_pipe_dn"] == "DN50"


def test_parse_inch_pipe_diameter():
    text = "HYDROCYCLONE SOLIDS SEPARATOR 3 INCH FLANGE 20 L/S"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["nominal_pipe_dn"] == "DN80"
    assert parsed["flow_rate_lps"] == 20.0


def test_extract_cooling_tower_side_stream_separator_candidates():
    items = [
        ("COOLING TOWER SIDE STREAM SEPARATOR SKID 25 L/S DN100", (150.2, 250.3)),
        ("FIRE HOSE REEL RECESS", (80.0, 90.0)),
        ("BASIN SWEEPER HYDROCYCLONE SEPARATOR WITH MOTORIZED PURGE", (400.0, 500.0)),
    ]
    candidates = extract_cooling_tower_side_stream_separator_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (150.0, 250.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"COOLING TOWER SIDE STREAM SEPARATOR {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_cooling_tower_side_stream_separator_candidates(items, max_cap=12)
    assert len(candidates) == 12


def test_system_validation_summary():
    items = [
        ("COOLING TOWER SIDE STREAM SEPARATOR SKID 25 L/S DN100 WITH MOTORIZED PURGE VALVE AND FILTER BAG", (10.0, 20.0)),
        ("BASIN SWEEPER HYDROCYCLONE SEPARATOR WITH SOLENOID PURGE", (30.0, 40.0)),
        ("CONDENSER WATER MULTIMEDIA SAND FILTER 15 L/S", (50.0, 60.0)),
    ]
    candidates = extract_cooling_tower_side_stream_separator_candidates(items)
    summary = validate_cooling_tower_side_stream_separator_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["auto_purge_count"] == 2
    assert summary["recovery_vessel_count"] == 1
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_chilled_water_service():
    text = "CHILLED WATER SIDE STREAM CENTRIFUGAL SEPARATOR DN65"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["service_designation"] == "CHILLED_WATER"
    assert parsed["nominal_pipe_dn"] == "DN65"


def test_candidate_dataclass_immutability():
    cand = CoolingTowerSideStreamSeparatorCallout(
        raw_text="SAMPLE",
        separator_type="CENTRIFUGAL_HYDROCYCLONE",
        flow_rate_lps=25.0,
        nominal_pipe_dn="DN100",
        purge_mechanism="AUTOMATIC_MOTORIZED_PURGE_VALVE",
        solids_recovery_vessel="RECOVERY_BAG_VESSEL",
        pump_skid_mount="SKID_MOUNTED_PACKAGE",
        service_designation="CONDENSER_WATER",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_cooling_tower_side_stream_separator_candidates([])
    assert len(candidates) == 0
    summary = validate_cooling_tower_side_stream_separator_system([])
    assert summary["total_candidates"] == 0
    assert summary["auto_purge_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_cooling_tower_side_stream_separator_callout("COOLING TOWER STRUCTURAL STEEL BEAM") is None
    assert parse_cooling_tower_side_stream_separator_callout("CONDENSER WATER PUMP BASEPLATE") is None
    assert parse_cooling_tower_side_stream_separator_callout("SEPARATOR PARTITION WALL IN OFFICE") is None


def test_dn150_pipe_detection():
    text = "COOLING TOWER CENTRIFUGAL SEPARATOR DN150 45 L/S"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["nominal_pipe_dn"] == "DN150"
    assert parsed["flow_rate_lps"] == 45.0


def test_decimal_lps_flow_rate():
    text = "HYDROCYCLONE SEPARATOR 12.5 LPS DN80"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["flow_rate_lps"] == 12.5


def test_2_inch_pipe_diameter():
    text = "SIDE-STREAM SEPARATOR 2\" INLET 8 L/S"
    parsed = parse_cooling_tower_side_stream_separator_callout(text)
    assert parsed is not None
    assert parsed["nominal_pipe_dn"] == "DN50"
