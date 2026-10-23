"""
Tests for Source Fire Sprinkler Dry Pipe Accelerator Quick Opening Device Shadow Authority.
"""

import pytest
from pb_source_sprinkler_dry_pipe_accelerator_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    SprinklerDryPipeAcceleratorCallout,
    snap_point,
    parse_sprinkler_dry_pipe_accelerator_callout,
    extract_sprinkler_dry_pipe_accelerator_candidates,
    validate_sprinkler_dry_pipe_accelerator_system,
)


def test_snap_point_regular():
    pt = snap_point(31.2, 46.4, snap_tol=2.5)
    assert pt == (30.0, 47.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(31.2, 46.4, snap_tol=0.0)
    assert pt == (31.2, 46.4)


def test_parse_none_on_irrelevant_text():
    assert parse_sprinkler_dry_pipe_accelerator_callout("ALUMINUM LOUVER SCREEN") is None
    assert parse_sprinkler_dry_pipe_accelerator_callout("CARPET TILES IN RECEPTION") is None
    assert parse_sprinkler_dry_pipe_accelerator_callout("ACOUSTIC CEILING BAFFLE") is None


def test_parse_dry_pipe_accelerator_with_integral_antiflood():
    text = "DRY PIPE ACCELERATOR WITH INTEGRAL ANTI-FLOODING DEVICE DN20 TRIM TO DN150 DRY PIPE VALVE 1200 KPA"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["device_type"] == "DRY_PIPE_ACCELERATOR"
    assert parsed["anti_flooding_device"] == "INTEGRAL_ANTI_FLOODING_DEVICE"
    assert parsed["valve_connection_dn"] == "DN20"
    assert parsed["dry_valve_size_dn"] == "DN150"
    assert parsed["rated_operating_pressure_kpa"] == 1200.0


def test_parse_quick_opening_device_car_park():
    text = "QUICK OPENING DEVICE (QOD) FOR DN100 DRY VALVE WITH AIR/WATER DUAL PRESSURE GAUGE - CAR PARK ZONE"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["device_type"] == "QUICK_OPENING_DEVICE"
    assert parsed["dry_valve_size_dn"] == "DN100"
    assert parsed["trim_pressure_gauges"] == "AIR_WATER_DUAL_PRESSURE_GAUGE"
    assert parsed["service_hazard"] == "CAR_PARK"


def test_parse_system_exhauster_refrigerated_warehouse():
    text = "SYSTEM EXHAUSTER QUICK-OPENING DEVICE FOR REFRIGERATED WAREHOUSE COLD STORAGE 175 PSI"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["device_type"] == "SYSTEM_EXHAUSTER"
    assert parsed["service_hazard"] == "REFRIGERATED_WAREHOUSE"
    assert parsed["rated_operating_pressure_kpa"] == round(175.0 * 6.89476, 1)


def test_parse_inch_trim_and_valve_size():
    text = "DRY VALVE ACCELERATOR 1/2\" NPT CONNECTION TO 6\" DRY PIPE VALVE WITH AIR PRESSURE GAUGE"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["valve_connection_dn"] == "DN15"
    assert parsed["dry_valve_size_dn"] == "DN150"
    assert parsed["trim_pressure_gauges"] == "AIR_PRESSURE_GAUGE"


def test_parse_freezing_exposure_loading_dock():
    text = "SPRINKLER ACCELERATOR ON UNHEATED LOADING DOCK DRY SYSTEM WITH SEPARATE ANTI-FLOOD BALL VALVE"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["service_hazard"] == "FREEZING_EXPOSURE"
    assert parsed["anti_flooding_device"] == "SEPARATE_ANTI_FLOOD_BALL_VALVE"


def test_parse_attic_space_hazard():
    text = "DIFFERENTIAL ACCELERATOR FOR ROOF ATTIC SPACE DRY SPRINKLER RISER DN80"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["service_hazard"] == "ATTIC_PROTECTION"
    assert parsed["dry_valve_size_dn"] == "DN80"


def test_parse_air_restriction_orifice():
    text = "DRY PIPE ACCELERATOR TRIM WITH AIR RESTRICTION ORIFICE AND 1400 KPA PRESSURE GAUGE"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["anti_flooding_device"] == "AIR_RESTRICTION_ORIFICE"
    assert parsed["rated_operating_pressure_kpa"] == 1400.0


def test_extract_sprinkler_dry_pipe_accelerator_candidates():
    items = [
        ("DRY PIPE ACCELERATOR WITH INTEGRAL ANTI-FLOODING DEVICE DN150", (150.3, 250.7)),
        ("TIMBER BASEBOARD SKIRTING", (20.0, 30.0)),
        ("QUICK OPENING DEVICE FOR CAR PARK DRY VALVE DN100", (400.0, 500.0)),
    ]
    candidates = extract_sprinkler_dry_pipe_accelerator_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (150.0, 250.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"DRY PIPE ACCELERATOR {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_sprinkler_dry_pipe_accelerator_candidates(items, max_cap=12)
    assert len(candidates) == 12


def test_system_validation_summary():
    items = [
        ("DRY PIPE ACCELERATOR WITH INTEGRAL ANTI-FLOODING DEVICE DN150", (10.0, 20.0)),
        ("QUICK OPENING DEVICE FOR CAR PARK DRY VALVE DN100", (30.0, 40.0)),
        ("SYSTEM EXHAUSTER FOR COLD STORAGE DRY SYSTEM", (50.0, 60.0)),
    ]
    candidates = extract_sprinkler_dry_pipe_accelerator_candidates(items)
    summary = validate_sprinkler_dry_pipe_accelerator_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["anti_flood_count"] == 1
    assert summary["sized_dry_valve_count"] == 2
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = SprinklerDryPipeAcceleratorCallout(
        raw_text="SAMPLE",
        device_type="DRY_PIPE_ACCELERATOR",
        valve_connection_dn="DN20",
        dry_valve_size_dn="DN150",
        anti_flooding_device="INTEGRAL_ANTI_FLOODING_DEVICE",
        trim_pressure_gauges="AIR_WATER_DUAL_PRESSURE_GAUGE",
        rated_operating_pressure_kpa=1200.0,
        service_hazard="FREEZING_EXPOSURE",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_sprinkler_dry_pipe_accelerator_candidates([])
    assert len(candidates) == 0
    summary = validate_sprinkler_dry_pipe_accelerator_system([])
    assert summary["total_candidates"] == 0
    assert summary["anti_flood_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_sprinkler_dry_pipe_accelerator_callout("WET PIPE SPRINKLER VALVE DN150") is None
    assert parse_sprinkler_dry_pipe_accelerator_callout("DELUGE VALVE WATER SPRAY SYSTEM") is None
    assert parse_sprinkler_dry_pipe_accelerator_callout("GAS PEDAL ACCELERATOR PEDAL FOR FORKLIFT") is None


def test_dn25_trim_connection():
    text = "DRY PIPE ACCELERATOR DN25 TRIM"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["valve_connection_dn"] == "DN25"


def test_dn200_dry_valve():
    text = "ACCELERATOR TRIM FOR DN200 DRY VALVE RISER"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["dry_valve_size_dn"] == "DN200"


def test_3_quarter_inch_trim():
    text = "DRY VALVE ACCELERATOR 3/4\" CONNECTION"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["valve_connection_dn"] == "DN20"


def test_8_inch_dry_valve():
    text = "QUICK-OPENING DEVICE FOR 8\" DRY VALVE"
    parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
    assert parsed is not None
    assert parsed["dry_valve_size_dn"] == "DN200"
