"""
Unit and adversarial test suite for Source Roof Parapet Overflow Scupper & Chute Shadow Authority.
"""

import pytest
from pb_source_parapet_overflow_scupper_shadow import (
    ParapetOverflowScupperCallout,
    SourceParapetOverflowScupperShadowAuthority,
    parse_parapet_overflow_scupper_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_scupper():
    text = "ROOF PARAPET DETAIL: 400X150MM OVERFLOW SCUPPER CHUTE, 50MM ABOVE SOLE, 8.0 L/S CAPACITY, COLORBOND STEEL LINING"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["scupper_type"] == "PARAPET_WALL_OPEN_CHUTE_SCUPPER"
    assert res["width_mm"] == 400.0
    assert res["height_mm"] == 150.0
    assert res["invert_elevation_above_sole_mm"] == 50.0
    assert res["overflow_capacity_lps"] == 8.0
    assert res["sheet_metal_material"] == "COLORBOND_STEEL"


def test_parse_stainless_steel_sleeve():
    text = "THROUGH WALL OVERFLOW SLEEVE 250X100, 75MM INVERT, 316 STAINLESS STEEL"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["scupper_type"] == "THROUGH_WALL_OVERFLOW_SLEEVE"
    assert res["width_mm"] == 250.0
    assert res["height_mm"] == 100.0
    assert res["invert_elevation_above_sole_mm"] == 75.0
    assert res["sheet_metal_material"] == "STAINLESS_STEEL_316"


def test_parse_copper_weir_box():
    text = "CONCEALED OVERFLOW WEIR BOX 500X200MM COPPER SHEET"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["scupper_type"] == "CONCEALED_OVERFLOW_WEIR_BOX"
    assert res["width_mm"] == 500.0
    assert res["height_mm"] == 200.0
    assert res["sheet_metal_material"] == "COPPER_SHEET"


def test_parse_defaults():
    text = "BOX GUTTER OVERFLOW"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["width_mm"] == 300.0
    assert res["height_mm"] == 150.0
    assert res["invert_elevation_above_sole_mm"] == 50.0
    assert res["overflow_capacity_lps"] == 6.0  # 300/1000 * 20.0


def test_parse_non_scupper():
    text = "INTERNAL STAIRCASE TREAD"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(52.4, 98.7, snap_tol=2.5)
    assert pt == (52.5, 97.5)


def test_authority_processing_dedup():
    auth = SourceParapetOverflowScupperShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("OVERFLOW SCUPPER 300X150", (10.0, 20.0)),
        ("OVERFLOW SCUPPER 300X150", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceParapetOverflowScupperShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("OVERFLOW SCUPPER 300X150", (10.0, 20.0)),
        ("OVERFLOW SCUPPER 300X150", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceParapetOverflowScupperShadowAuthority()
    oversized = [("OVERFLOW SCUPPER", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceParapetOverflowScupperShadowAuthority()
    res = auth.process_callouts([("OVERFLOW SCUPPER", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_parapet_overflow_scupper_callout("") is None


def test_zero_tolerance_snap():
    pt = snap_point(17.17, 34.34, snap_tol=0.0)
    assert pt == (17.17, 34.34)


def test_frozen_dataclass_immutability():
    callout = ParapetOverflowScupperCallout(
        raw_text="text",
        scupper_type="CHUTE",
        width_mm=300.0,
        height_mm=150.0,
        invert_elevation_above_sole_mm=50.0,
        overflow_capacity_lps=6.0,
        sheet_metal_material="COLORBOND",
    )
    with pytest.raises(Exception):
        callout.width_mm = 500.0  # type: ignore


def test_different_widths_same_point():
    auth = SourceParapetOverflowScupperShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("OVERFLOW SCUPPER 300X150", (10.0, 20.0)),
        ("OVERFLOW SCUPPER 600X150", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_emergency_overflow_trigger():
    text = "EMERGENCY OVERFLOW 450X150MM"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["width_mm"] == 450.0
    assert res["height_mm"] == 150.0


def test_gutter_overflow_trigger():
    text = "GUTTER OVERFLOW WITH 12 LPS CAPACITY"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["overflow_capacity_lps"] == 12.0


def test_parapet_scupper_trigger():
    text = "PARAPET SCUPPER 600X200MM, 100MM INVERT"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["width_mm"] == 600.0
    assert res["height_mm"] == 200.0
    assert res["invert_elevation_above_sole_mm"] == 100.0


def test_colourbond_spelling():
    text = "ROOF SCUPPER COLOURBOND STEEL"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["sheet_metal_material"] == "COLORBOND_STEEL"


def test_scupper_chute_trigger():
    text = "SCUPPER CHUTE 200X100MM"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["width_mm"] == 200.0
    assert res["height_mm"] == 100.0


def test_overflow_chute_trigger():
    text = "OVERFLOW CHUTE 350X150MM"
    res = parse_parapet_overflow_scupper_callout(text)
    assert res is not None
    assert res["width_mm"] == 350.0
