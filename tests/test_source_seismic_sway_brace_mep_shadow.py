"""
Unit and adversarial test suite for Source Seismic Restraint Cable Sway Brace MEP Suspended Services Shadow Authority.
"""

import pytest
from pb_source_seismic_sway_brace_mep_shadow import (
    SeismicSwayBraceMepCallout,
    SourceSeismicSwayBraceMepShadowAuthority,
    parse_seismic_sway_brace_mep_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_transverse_cable_brace_pipe_complete():
    text = "SEISMIC RESTRAINT: TRANSVERSE CABLE SWAY BRACE FOR SUSPENDED CHW PIPE, 4.8MM AIRCRAFT CABLE AT 45 DEGREE ANGLE, 0.35G ACCELERATION, CONCRETE EXPANSION ANCHORS"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["brace_type"] == "TRANSVERSE_CABLE_SWAY_BRACE"
    assert res["service_type"] == "SUSPENDED_CHW_PIPE"
    assert res["cable_diameter_mm"] == 4.8
    assert res["brace_angle_degrees"] == 45.0
    assert res["seismic_design_acceleration_g"] == 0.35
    assert res["anchor_type"] == "CONCRETE_EXPANSION_ANCHOR"


def test_parse_longitudinal_brace_sprinkler():
    text = "SWAY BRACE: LONGITUDINAL CABLE BRACE ON FIRE SPRINKLER MAIN, 6.4MM CABLE @ 60°, STEEL BEAM CLAMP ATTACHMENT"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["brace_type"] == "LONGITUDINAL_CABLE_SWAY_BRACE"
    assert res["service_type"] == "FIRE_SPRINKLER_MAIN"
    assert res["cable_diameter_mm"] == 6.4
    assert res["brace_angle_degrees"] == 60.0
    assert res["anchor_type"] == "STEEL_BEAM_CLAMP"


def test_parse_4_way_rigid_strut_duct():
    text = "MEP SEISMIC: 4-WAY RIGID STRUT BRACE FOR RECTANGULAR HVAC SUPPLY AIR DUCT"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["brace_type"] == "4_WAY_RIGID_STRUT_BRACE"
    assert res["service_type"] == "RECTANGULAR_HVAC_DUCT"


def test_parse_cable_tray_seismic():
    text = "SEISMIC BRACE FOR ELECTRICAL CABLE TRAY WITH DROP-IN ANCHOR"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["service_type"] == "ELECTRICAL_CABLE_TRAY"
    assert res["anchor_type"] == "DROP_IN_ANCHOR"


def test_parse_defaults():
    text = "SEISMIC BRACE"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["brace_type"] == "TRANSVERSE_CABLE_SWAY_BRACE"
    assert res["cable_diameter_mm"] == 4.8
    assert res["brace_angle_degrees"] == 45.0
    assert res["service_type"] == "SUSPENDED_CHW_PIPE"
    assert res["seismic_design_acceleration_g"] == 0.25
    assert res["anchor_type"] == "CONCRETE_EXPANSION_ANCHOR"


def test_parse_unrelated_text_returns_none():
    assert parse_seismic_sway_brace_mep_callout("ALUMINUM SKIRTING 150MM") is None
    assert parse_seismic_sway_brace_mep_callout("SUSPENDED CEILING 600X600 TILE") is None


def test_snap_point_regular():
    pt = snap_point(23.3, 35.8, snap_tol=2.5)
    assert pt == (22.5, 35.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(23.34, 35.87, snap_tol=0.0)
    assert pt == (23.34, 35.87)


def test_authority_processing_batch():
    auth = SourceSeismicSwayBraceMepShadowAuthority()
    candidates = [
        ("SEISMIC BRACE 4.8MM CABLE", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("LONGITUDINAL BRACE SPRINKLER", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].brace_type == "LONGITUDINAL_CABLE_SWAY_BRACE"


def test_safety_primitive_cap():
    auth = SourceSeismicSwayBraceMepShadowAuthority()
    large_list = [("SEISMIC BRACE", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = SeismicSwayBraceMepCallout(
        raw_text="SAMPLE",
        brace_type="TRANSVERSE_CABLE_SWAY_BRACE",
        cable_diameter_mm=4.8,
        brace_angle_degrees=45.0,
        service_type="SUSPENDED_CHW_PIPE",
        seismic_design_acceleration_g=0.25,
        anchor_type="CONCRETE_EXPANSION_ANCHOR",
    )
    with pytest.raises(Exception):
        callout.brace_angle_degrees = 60.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   seismic restraint: transverse brace, 3.2mm cable at 30 deg   "
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["cable_diameter_mm"] == 3.2
    assert res["brace_angle_degrees"] == 30.0


def test_fractional_inch_cable_size():
    text = "SWAY BRACE: 1/8\" AIRCRAFT CABLE RESTRAINT"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["cable_diameter_mm"] == 3.2


def test_through_bolt_deck_anchor():
    text = "SEISMIC BRACE WITH THROUGH BOLT DECK FIXING"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["anchor_type"] == "THROUGH_BOLT_DECK"


def test_custom_snap_tolerance():
    auth = SourceSeismicSwayBraceMepShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("SEISMIC BRACE", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceSeismicSwayBraceMepShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_high_seismic_acceleration():
    text = "SEISMIC RESTRAINT DESIGNED FOR 0.45G HORIZONTAL LOAD"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["seismic_design_acceleration_g"] == 0.45


def test_tension_only_cable():
    text = "TENSION ONLY AIRCRAFT CABLE SWAY BRACE"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["brace_type"] == "TENSION_ONLY_AIRCRAFT_CABLE"


def test_seismic_cable_trigger():
    text = "SEISMIC CABLE TO HYDRONIC CONDENSER WATER LINE"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["service_type"] == "SUSPENDED_CHW_PIPE"


def test_adversarial_special_characters():
    text = "SEISMIC BRACE @@@ [TRANSVERSE] +++ (4.8MM) // @ 45° *** 0.25G ###"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["brace_type"] == "TRANSVERSE_CABLE_SWAY_BRACE"
    assert res["cable_diameter_mm"] == 4.8
    assert res["brace_angle_degrees"] == 45.0
    assert res["seismic_design_acceleration_g"] == 0.25


def test_wedge_anchor_trigger():
    text = "SWAY BRACE SECURED BY M12 WEDGE ANCHOR IN SOFFIT"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["anchor_type"] == "CONCRETE_EXPANSION_ANCHOR"


def test_quarter_inch_cable():
    text = "SEISMIC RESTRAINT WITH 1/4\" CABLE"
    res = parse_seismic_sway_brace_mep_callout(text)
    assert res is not None
    assert res["cable_diameter_mm"] == 6.4

