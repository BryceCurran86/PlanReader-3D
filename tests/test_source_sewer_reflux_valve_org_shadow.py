"""
Unit and adversarial test suite for Source Sanitary Sewer Reflux Valve & Overflow Relief Gully Shadow Authority.
"""

import pytest
from pb_source_sewer_reflux_valve_org_shadow import (
    SewerRefluxValveOrgCallout,
    SourceSewerRefluxValveOrgShadowAuthority,
    parse_sewer_reflux_valve_org_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_combined_org_reflux():
    text = "SANITARY DRAINAGE: DN100 COMBINED OVERFLOW RELIEF GULLY (ORG) WITH SEWER REFLUX VALVE, LOOSE POP-UP PVC GRATE, SWING FLAPPER, 150MM FREEBOARD"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["fixture_type"] == "COMBINED_ORG_WITH_REFLUX_VALVE"
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["grate_type"] == "LOOSE_POP_UP_PLASTIC_GRATE"
    assert res["valve_mechanism"] == "SWING_FLAPPER_NON_RETURN"
    assert res["min_freeboard_clearance_mm"] == 150.0


def test_parse_reflux_valve_alone():
    text = "SEWER BOUNDARY TRAP: DN150 SEWER REFLUX BACKWATER VALVE WITH CAST IRON ACCESS"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["fixture_type"] == "SEWER_REFLUX_BACKWATER_VALVE"
    assert res["pipe_diameter_dn"] == "DN150"
    assert res["valve_mechanism"] == "SWING_FLAPPER_NON_RETURN"


def test_parse_org_alone():
    text = "EXTERNAL O.R.G. DN100, 75MM CLEARANCE ABOVE GROUND"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["fixture_type"] == "OVERFLOW_RELIEF_GULLY_ORG"
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["min_freeboard_clearance_mm"] == 75.0


def test_parse_defaults():
    text = "OVERFLOW RELIEF GULLY"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["fixture_type"] == "OVERFLOW_RELIEF_GULLY_ORG"
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["grate_type"] == "LOOSE_POP_UP_PLASTIC_GRATE"


def test_parse_non_org():
    text = "STORMWATER DOWNPIPE DP-01"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(33.1, 71.9, snap_tol=2.5)
    assert pt == (32.5, 72.5)


def test_authority_processing_dedup():
    auth = SourceSewerRefluxValveOrgShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("DN100 ORG", (10.0, 20.0)),
        ("DN100 ORG", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceSewerRefluxValveOrgShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("DN100 ORG", (10.0, 20.0)),
        ("DN100 ORG", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceSewerRefluxValveOrgShadowAuthority()
    oversized = [("DN100 ORG", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceSewerRefluxValveOrgShadowAuthority()
    res = auth.process_callouts([("DN100 ORG", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_sewer_reflux_valve_org_callout("") is None


def test_brass_grate():
    text = "ORG WITH BRASS SURCHARGE GRATE DN100"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["grate_type"] == "BRASS_LOCKABLE_SURCHARGE_GRATE"


def test_dual_ball_float():
    text = "BACKWATER VALVE WITH DUAL BALL FLOAT MECHANISM DN100"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["valve_mechanism"] == "DUAL_BALL_FLOAT_BACKWATER"


def test_zero_tolerance_snap():
    pt = snap_point(5.55, 6.66, snap_tol=0.0)
    assert pt == (5.55, 6.66)


def test_frozen_dataclass_immutability():
    callout = SewerRefluxValveOrgCallout(
        raw_text="text",
        fixture_type="ORG",
        pipe_diameter_dn="DN100",
        grate_type="PVC",
        valve_mechanism="NONE",
        min_freeboard_clearance_mm=75.0,
    )
    with pytest.raises(Exception):
        callout.min_freeboard_clearance_mm = 150.0  # type: ignore


def test_different_fixtures_same_point():
    auth = SourceSewerRefluxValveOrgShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("OVERFLOW RELIEF GULLY DN100", (10.0, 20.0)),
        ("SEWER REFLUX VALVE DN100", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_dn150_large_org():
    text = "DN150 OVERFLOW RELIEF GULLY"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN150"


def test_surcharge_gully_trigger():
    text = "SEWER SURCHARGE GULLY DN100"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["fixture_type"] == "OVERFLOW_RELIEF_GULLY_ORG"


def test_cast_iron_grate():
    text = "ORG DN100 WITH CAST IRON HINGED GRATE"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["grate_type"] == "CAST_IRON_HINGED_GRATE"


def test_backwater_valve_trigger():
    text = "SANITARY BACKWATER VALVE DN100 WITH SWING FLAPPER"
    res = parse_sewer_reflux_valve_org_callout(text)
    assert res is not None
    assert res["fixture_type"] == "SEWER_REFLUX_BACKWATER_VALVE"
