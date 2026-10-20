"""
Unit and adversarial test suite for Source Structural Steel Purlin Apex Tie & Ridge Cleat Shadow Authority.
"""

import pytest
from pb_source_steel_purlin_apex_tie_shadow import (
    SteelPurlinApexTieCallout,
    SourceSteelPurlinApexTieShadowAuthority,
    parse_steel_purlin_apex_tie_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_apex_strap_tie_complete():
    text = "ROOF RIDGE: APEX TIE STRAP TO C20015 PURLINS, 4.0MM RIDGE CLEAT, 2-M12 4.6/S BOLTS, 10 DEG PITCH, GALVABOND Z450"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["purlin_section"] == "C20015"
    assert res["apex_tie_type"] == "STRAP_APEX_TIE"
    assert res["ridge_cleat_gauge_mm"] == 4.0
    assert "M12" in res["bolt_specification"]
    assert res["pitch_degrees"] == 10.0
    assert res["coating_finish"] == "GALVABOND_Z450"


def test_parse_angle_apex_strut_hdg():
    text = "PURLIN APEX: ANGLE APEX STRUT FOR Z20020 PURLINS, 6MM CLEAT, M16 GR8.8 BOLTS, 5° ROOF PITCH, HDG"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["purlin_section"] == "Z20020"
    assert res["apex_tie_type"] == "ANGLE_APEX_STRUT"
    assert res["ridge_cleat_gauge_mm"] == 6.0
    assert "M16" in res["bolt_specification"]
    assert res["pitch_degrees"] == 5.0
    assert res["coating_finish"] == "HOT_DIP_GALVANIZED"


def test_parse_solid_rod_apex_tie():
    text = "RIDGE PURLIN DETAIL: SOLID ROUND BAR APEX TIE WITH 3MM CLEAT PLATE"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["apex_tie_type"] == "SOLID_ROD_APEX_TIE"
    assert res["ridge_cleat_gauge_mm"] == 3.0


def test_parse_channel_ridge_brace():
    text = "APEX BRACKET: CHANNEL RIDGE BRACE TO C15015 PURLINS, 15 DEGREE PITCH"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["apex_tie_type"] == "CHANNEL_RIDGE_BRACE"
    assert res["purlin_section"] == "C15015"
    assert res["pitch_degrees"] == 15.0


def test_parse_defaults():
    text = "APEX TIE TO RIDGE PURLIN"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["purlin_section"] == "C20015"
    assert res["apex_tie_type"] == "STRAP_APEX_TIE"
    assert res["ridge_cleat_gauge_mm"] == 3.0
    assert res["bolt_specification"] == "M12 GR4.6"
    assert res["pitch_degrees"] == 5.0
    assert res["coating_finish"] == "GALVABOND_Z450"


def test_parse_unrelated_text_returns_none():
    assert parse_steel_purlin_apex_tie_callout("CARPET TILE FINISH ON UNDERLAY") is None
    assert parse_steel_purlin_apex_tie_callout("ALUMINUM DOOR FRAME D02") is None


def test_snap_point_regular():
    pt = snap_point(31.2, 42.8, snap_tol=2.5)
    assert pt == (30.0, 42.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(31.24, 42.87, snap_tol=0.0)
    assert pt == (31.24, 42.87)


def test_authority_processing_batch():
    auth = SourceSteelPurlinApexTieShadowAuthority()
    candidates = [
        ("APEX TIE STRAP TO C20015", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("RIDGE CLEAT 5MM PLATE", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].ridge_cleat_gauge_mm == 5.0


def test_safety_primitive_cap():
    auth = SourceSteelPurlinApexTieShadowAuthority()
    large_list = [("APEX TIE STRAP", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = SteelPurlinApexTieCallout(
        raw_text="SAMPLE",
        purlin_section="C20015",
        apex_tie_type="STRAP_APEX_TIE",
        ridge_cleat_gauge_mm=3.0,
        bolt_specification="M12 GR4.6",
        pitch_degrees=5.0,
        coating_finish="GALVABOND_Z450",
    )
    with pytest.raises(Exception):
        callout.pitch_degrees = 10.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   ridge cleat: 5mm bracket to c25020 purlins at 7.5 deg pitch   "
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["ridge_cleat_gauge_mm"] == 5.0
    assert res["pitch_degrees"] == 7.5


def test_zincalume_finish():
    text = "RIDGE PURLIN APEX TIE IN ZINCALUME FINISH"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["coating_finish"] == "ZINCALUME"


def test_custom_snap_tolerance():
    auth = SourceSteelPurlinApexTieShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("APEX TIE", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceSteelPurlinApexTieShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_ridge_strap_trigger():
    text = "RIDGE STRAP BRACING TO Z25020 PURLINS"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["purlin_section"] == "Z25020"
    assert res["apex_tie_type"] == "STRAP_APEX_TIE"


def test_alt_purlin_section_format():
    text = "APEX TIE TO 200Z15 PURLIN WITH 4MM CLEAT"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["purlin_section"] == "200Z15"
    assert res["ridge_cleat_gauge_mm"] == 4.0


def test_sag_rod_trigger():
    text = "RIDGE PURLIN WITH SAG ROD APEX BRACE"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["apex_tie_type"] == "SOLID_ROD_APEX_TIE"


def test_hot_dip_galv_spelling():
    text = "APEX BRACKET: HOT-DIP GALVANIZED FINISH"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["coating_finish"] == "HOT_DIP_GALVANIZED"


def test_steep_pitch_degrees():
    text = "ROOF APEX: 22.5 DEG PITCH TO RIDGE CLEAT"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["pitch_degrees"] == 22.5


def test_adversarial_special_characters():
    text = "ROOF APEX @@@ [RIDGE CLEAT] +++ (C20015) // 5° *** 3MM ###"
    res = parse_steel_purlin_apex_tie_callout(text)
    assert res is not None
    assert res["purlin_section"] == "C20015"
    assert res["pitch_degrees"] == 5.0
    assert res["ridge_cleat_gauge_mm"] == 3.0
