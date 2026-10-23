"""
Unit and adversarial test suite for Source Rainwater Harvesting First Flush Diverter Shadow Authority.
"""

import pytest
from pb_source_first_flush_diverter_shadow import (
    FirstFlushDiverterCallout,
    SourceFirstFlushDiverterShadowAuthority,
    parse_first_flush_diverter_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_first_flush():
    text = "STORMWATER HARVESTING: DN150 IN-GROUND FIRST FLUSH DIVERTER, 120 LITRES, SLOW RELEASE BLEED ORIFICE WITH LEAF EATER SCREEN"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN150"
    assert res["chamber_volume_litres"] == 120.0
    assert res["diverter_type"] == "IN_GROUND_VERTICAL_CHAMBER"
    assert res["drain_bleed_mechanism"] == "SLOW_RELEASE_BLEED_CONTROL_VALVE"
    assert res["filter_mesh_screen_type"] == "STAINLESS_STEEL_LEAF_EATER_SCREEN"


def test_parse_commercial_high_volume():
    text = "COMMERCIAL HIGH VOLUME FIRST FLUSH DIVERTER DN225, 350L, ELECTRONIC TIMER PURGE"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN225"
    assert res["chamber_volume_litres"] == 350.0
    assert res["diverter_type"] == "COMMERCIAL_HIGH_VOLUME"
    assert res["drain_bleed_mechanism"] == "ELECTRONIC_TIMER_PURGE"


def test_parse_downpipe_wall_mounted():
    text = "DOWNPIPE FIRST-FLUSH DIVERTER DN100, 45 LITRES, MANUAL BALL VALVE"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["chamber_volume_litres"] == 45.0
    assert res["diverter_type"] == "WALL_MOUNTED_POST_DOWNPIPE"
    assert res["drain_bleed_mechanism"] == "MANUAL_DRAIN_VALVE"


def test_parse_defaults():
    text = "ROOF FLUSH DIVERTER"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["chamber_volume_litres"] == 50.0
    assert res["diverter_type"] == "WALL_MOUNTED_POST_DOWNPIPE"


def test_parse_non_first_flush():
    text = "SEWER INSPECTION SHAFT DN100"
    res = parse_first_flush_diverter_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(22.3, 37.8, snap_tol=2.5)
    assert pt == (22.5, 37.5)


def test_authority_processing_dedup():
    auth = SourceFirstFlushDiverterShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("FIRST FLUSH DIVERTER DN100, 50L", (10.0, 20.0)),
        ("FIRST FLUSH DIVERTER DN100, 50L", (10.5, 20.2)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceFirstFlushDiverterShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("FIRST FLUSH DIVERTER DN100, 50L", (10.0, 20.0)),
        ("FIRST FLUSH DIVERTER DN100, 50L", (70.0, 80.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceFirstFlushDiverterShadowAuthority()
    oversized = [("FIRST FLUSH DIVERTER DN100", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceFirstFlushDiverterShadowAuthority()
    res = auth.process_callouts([("FIRST FLUSH DIVERTER DN100", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_mesh_cage_filter():
    text = "FIRST FLUSH DIVERTER DN90, PRIMARY MESH CAGE"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["filter_mesh_screen_type"] == "PRIMARY_MESH_CAGE"


def test_ball_float_filter():
    text = "RAINWATER DIVERTER DN100 WITH SEALING BALL FLOAT"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["filter_mesh_screen_type"] == "INTEGRAL_BALL_FLOAT"


def test_dn90_small_pipe():
    text = "RESIDENTIAL DOWNPIPE DIVERTER DN90, 30L"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN90"
    assert res["chamber_volume_litres"] == 30.0


def test_dn300_large_commercial():
    text = "COMMERCIAL FIRST FLUSH DIVERTER DN300, 600 LITRES"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN300"
    assert res["chamber_volume_litres"] == 600.0


def test_empty_string():
    assert parse_first_flush_diverter_callout("") is None


def test_solenoid_purge():
    text = "ROOF FLUSH DIVERTER DN150 WITH SOLENOID DRAIN PURGE"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["drain_bleed_mechanism"] == "ELECTRONIC_TIMER_PURGE"


def test_drip_orifice():
    text = "RAINWATER DIVERTER DN100 DRIP ORIFICE"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["drain_bleed_mechanism"] == "SLOW_RELEASE_BLEED_CONTROL_VALVE"


def test_frozen_dataclass():
    c = FirstFlushDiverterCallout(
        raw_text="t",
        pipe_diameter_dn="DN100",
        chamber_volume_litres=50.0,
        diverter_type="WALL",
        drain_bleed_mechanism="SLOW",
        filter_mesh_screen_type="SCREEN",
    )
    with pytest.raises(Exception):
        c.chamber_volume_litres = 100.0  # type: ignore


def test_inground_pit():
    text = "IN-GROUND FIRST FLUSH PIT DN225, 250 LITRES"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["diverter_type"] == "IN_GROUND_VERTICAL_CHAMBER"


def test_post_mount():
    text = "POST MOUNTED RAINWATER DIVERTER DN100"
    res = parse_first_flush_diverter_callout(text)
    assert res is not None
    assert res["diverter_type"] == "WALL_MOUNTED_POST_DOWNPIPE"


def test_zero_snap():
    pt = snap_point(12.34, 56.78, snap_tol=0.0)
    assert pt == (12.34, 56.78)
