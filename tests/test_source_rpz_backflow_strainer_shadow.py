"""
Unit and adversarial test suite for Source Cold Water RPZ Backflow Prevention Device Strainer Shadow Authority.
"""

import pytest
from pb_source_rpz_backflow_strainer_shadow import (
    RpzBackflowStrainerCallout,
    SourceRpzBackflowStrainerShadowAuthority,
    parse_rpz_backflow_strainer_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_rpz_complete():
    text = "BACKFLOW PREVENTION: DN50 RPZ DEVICE (HIGH HAZARD), UPSTREAM Y-STRAINER, LOCKABLE FULL BORE BALL VALVES, TUNDISH DRAIN"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["device_type"] == "REDUCED_PRESSURE_ZONE_RPZ"
    assert res["hazard_rating"] == "HIGH_HAZARD"
    assert res["nominal_size_dn"] == "DN50"
    assert res["strainer_type"] == "Y_TYPE_STRAINER_BLOWDOWN"
    assert res["isolation_valves"] == "FULL_BORE_BALL_VALVES_LOCKABLE"
    assert res["relief_drain_air_gap_tundish"] == "TUNDISH_AIR_GAP_DRAIN"


def test_parse_double_check_valve():
    text = "BACKFLOW PREVENTER: DN80 DOUBLE CHECK VALVE (MEDIUM HAZARD), OS&Y RESILIENT SEAT GATE VALVES, BASKET STRAINER"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["device_type"] == "DOUBLE_CHECK_VALVE_DCV"
    assert res["hazard_rating"] == "MEDIUM_HAZARD"
    assert res["nominal_size_dn"] == "DN80"
    assert res["strainer_type"] == "BASKET_STRAINER"
    assert res["isolation_valves"] == "RESILIENT_SEAT_GATE_VALVES_OSY"


def test_parse_vacuum_breaker():
    text = "ATMOSPHERIC VACUUM BREAKER DN25 (LOW HAZARD)"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["device_type"] == "VACUUM_BREAKER"
    assert res["hazard_rating"] == "LOW_HAZARD"
    assert res["nominal_size_dn"] == "DN25"


def test_parse_defaults():
    text = "RPZ DEVICE"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["device_type"] == "REDUCED_PRESSURE_ZONE_RPZ"
    assert res["hazard_rating"] == "HIGH_HAZARD"
    assert res["nominal_size_dn"] == "DN50"
    assert res["strainer_type"] == "Y_TYPE_STRAINER_BLOWDOWN"
    assert res["isolation_valves"] == "FULL_BORE_BALL_VALVES_LOCKABLE"
    assert res["relief_drain_air_gap_tundish"] == "TUNDISH_AIR_GAP_DRAIN"


def test_parse_unrelated_text_returns_none():
    assert parse_rpz_backflow_strainer_callout("ALUMINUM SKIRTING BOARD") is None
    assert parse_rpz_backflow_strainer_callout("CARPET TILES OVER UNDERLAY") is None


def test_snap_point_regular():
    pt = snap_point(25.3, 37.8, snap_tol=2.5)
    assert pt == (25.0, 37.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(25.34, 37.87, snap_tol=0.0)
    assert pt == (25.34, 37.87)


def test_authority_processing_batch():
    auth = SourceRpzBackflowStrainerShadowAuthority()
    candidates = [
        ("RPZ DEVICE DN40", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("DCV BACKFLOW PREVENTER DN65", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].nominal_size_dn == "DN65"


def test_safety_primitive_cap():
    auth = SourceRpzBackflowStrainerShadowAuthority()
    large_list = [("RPZ DEVICE", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = RpzBackflowStrainerCallout(
        raw_text="SAMPLE",
        device_type="REDUCED_PRESSURE_ZONE_RPZ",
        hazard_rating="HIGH_HAZARD",
        nominal_size_dn="DN50",
        strainer_type="Y_TYPE_STRAINER_BLOWDOWN",
        isolation_valves="FULL_BORE_BALL_VALVES_LOCKABLE",
        relief_drain_air_gap_tundish="TUNDISH_AIR_GAP_DRAIN",
    )
    with pytest.raises(Exception):
        callout.nominal_size_dn = "DN80"  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   rpzd backflow preventer: dn32, high hazard, y-strainer   "
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["nominal_size_dn"] == "DN32"
    assert res["device_type"] == "REDUCED_PRESSURE_ZONE_RPZ"


def test_no_strainer_negation():
    text = "RPZ DEVICE WITHOUT STRAINER"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["strainer_type"] == "NONE"


def test_direct_drain_runout():
    text = "RPZ VALVE WITH DIRECT RUNOUT DRAIN"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["relief_drain_air_gap_tundish"] == "DIRECT_DRAIN_RUNOUT"


def test_butterfly_isolation_valves():
    text = "DN100 RPZ BACKFLOW WITH GEAR OPERATED BUTTERFLY VALVES"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["isolation_valves"] == "BUTTERFLY_VALVES_GEAR_OPERATED"
    assert res["nominal_size_dn"] == "DN100"


def test_custom_snap_tolerance():
    auth = SourceRpzBackflowStrainerShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("RPZ DEVICE", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceRpzBackflowStrainerShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_dual_check_valve():
    text = "DUAL CHECK BACKFLOW PREVENTER DN20"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["device_type"] == "DUAL_CHECK_VALVE"
    assert res["nominal_size_dn"] == "DN20"


def test_integral_strainer():
    text = "RPZD WITH INTEGRAL STRAINER"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["strainer_type"] == "INTEGRAL_STRAINER"


def test_mm_diameter_notation():
    text = "40MM RPZ BACKFLOW VALVE"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["nominal_size_dn"] == "DN40"


def test_adversarial_special_characters():
    text = "RPZ @@@ [HIGH HAZARD] +++ (DN50) // Y-STRAINER *** TUNDISH ###"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["device_type"] == "REDUCED_PRESSURE_ZONE_RPZ"
    assert res["nominal_size_dn"] == "DN50"
    assert res["strainer_type"] == "Y_TYPE_STRAINER_BLOWDOWN"
    assert res["relief_drain_air_gap_tundish"] == "TUNDISH_AIR_GAP_DRAIN"


def test_dcv_acronym_trigger():
    text = "DCV WITH TEST COCKS AND BALL VALVES"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["device_type"] == "DOUBLE_CHECK_VALVE_DCV"


def test_rpzd_with_air_gap_funnel():
    text = "RPZD WITH AIR GAP FUNNEL TUNDISH"
    res = parse_rpz_backflow_strainer_callout(text)
    assert res is not None
    assert res["relief_drain_air_gap_tundish"] == "TUNDISH_AIR_GAP_DRAIN"

