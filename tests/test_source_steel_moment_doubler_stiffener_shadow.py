"""Unit tests for Source Structural Steel Moment Connection Web Doubler Plate & Continuity Stiffener Shadow Authority."""

import pytest
from pb_source_steel_moment_doubler_stiffener_shadow import (
    MomentDoublerStiffenerCandidate,
    snap_point,
    parse_moment_doubler_stiffener_callout,
    evaluate_steel_moment_doubler_stiffener_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((12.4, 17.6)) == (12.5, 17.5)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_moment_doubler_stiffener_callout_single_cjp():
    text = "16MM WEB DOUBLER WITH 20MM CONTINUITY STIFFENER CJP WELD"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["doubler_configuration"] == "SINGLE_DOUBLER"
    assert parsed["doubler_thickness_mm"] == 16.0
    assert parsed["continuity_stiffener_thickness_mm"] == 20.0
    assert parsed["weld_type"] == "CJP_GROOVE"
    assert parsed["continuity_stiffener_pairs"] == 2


def test_parse_moment_doubler_stiffener_callout_double_doubler_fillet():
    text = "12MM DOUBLER PLATE BOTH SIDES WITH 16MM STIFFENER PL 8MM CFW"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["doubler_configuration"] == "DOUBLE_DOUBLER"
    assert parsed["doubler_thickness_mm"] == 12.0
    assert parsed["continuity_stiffener_thickness_mm"] == 16.0
    assert parsed["weld_type"] == "FILLET_WELD"
    assert parsed["weld_size_mm"] == 8.0


def test_parse_moment_doubler_stiffener_callout_stiffener_only():
    text = "CONTINUITY STIFFENER 25MM THICK AT TOP & BTM FLANGES 10MM FILLET"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["doubler_configuration"] == "NONE"
    assert parsed["doubler_thickness_mm"] is None
    assert parsed["continuity_stiffener_thickness_mm"] == 25.0
    assert parsed["continuity_stiffener_pairs"] == 2
    assert parsed["weld_type"] == "FILLET_WELD"
    assert parsed["weld_size_mm"] == 10.0


def test_parse_moment_doubler_stiffener_callout_panel_zone_bevel():
    text = "PANEL ZONE DOUBLER 20MM WITH BEVEL GROOVE WELD"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["doubler_configuration"] == "SINGLE_DOUBLER"
    assert parsed["doubler_thickness_mm"] == 20.0
    assert parsed["weld_type"] == "BEVEL_GROOVE"


def test_parse_moment_doubler_stiffener_callout_single_pair():
    text = "MOMENT CONNECTION STIFFENER 16MM 1 PAIR AT TOP FLANGE ONLY"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["continuity_stiffener_pairs"] == 1


def test_parse_moment_doubler_stiffener_callout_unrelated():
    assert parse_moment_doubler_stiffener_callout("CONCRETE SLAB ON GRADE 150MM") is None


def test_evaluate_steel_moment_doubler_stiffener_shadow_single():
    callouts = ["16MM WEB DOUBLER 20MM CONTINUITY STIFFENER CJP"]
    positions = [(150.2, 300.4)]
    res = evaluate_steel_moment_doubler_stiffener_shadow("S-501", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "S-501_mds_001"
    assert c.sheet_id == "S-501"
    assert c.position == (150.0, 300.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_steel_moment_doubler_stiffener_shadow_dict():
    c = MomentDoublerStiffenerCandidate(
        candidate_id="S-502_mds_001",
        sheet_id="S-502",
        doubler_configuration="SINGLE_DOUBLER",
        doubler_thickness_mm=16.0,
        continuity_stiffener_thickness_mm=20.0,
        continuity_stiffener_pairs=2,
        weld_type="CJP_GROOVE",
        weld_size_mm=None,
        position=(100.0, 200.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "S-502_mds_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["doubler_configuration"] == "SINGLE_DOUBLER"


def test_evaluate_steel_moment_doubler_stiffener_shadow_no_positions():
    callouts = ["WEB DOUBLER 16MM"]
    res = evaluate_steel_moment_doubler_stiffener_shadow("S-503", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_steel_moment_doubler_stiffener_shadow_safety_cap():
    callouts = ["WEB DOUBLER 16MM"] * 10
    res = evaluate_steel_moment_doubler_stiffener_shadow("S-504", callouts, max_primitives=3)
    assert len(res) == 3


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_steel_moment_doubler_stiffener_shadow("S-505", []) == []


def test_unrelated_callout_filtering():
    callouts = ["BRICK VENEER WALL", "16MM WEB DOUBLER"]
    res = evaluate_steel_moment_doubler_stiffener_shadow("S-506", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "S-506_mds_002"


def test_full_penetration_trigger():
    text = "WEB DOUBLER FULL PENETRATION WELD"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["weld_type"] == "CJP_GROOVE"


def test_column_stiffener_pl_trigger():
    text = "COLUMN STIFFENER PL 20MM THICK"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["continuity_stiffener_thickness_mm"] == 20.0


def test_default_values():
    text = "MOMENT STIFFENER"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["doubler_configuration"] == "NONE"
    assert parsed["continuity_stiffener_thickness_mm"] == 16.0
    assert parsed["continuity_stiffener_pairs"] == 2
    assert parsed["weld_type"] == "FILLET_WELD"
    assert parsed["weld_size_mm"] == 8.0


def test_snapping_precision():
    callouts = ["WEB DOUBLER 16MM"]
    positions = [(12.1, 14.9)]
    res = evaluate_steel_moment_doubler_stiffener_shadow("S-507", callouts, positions)
    assert res[0].position == (12.5, 15.0)


def test_both_flanges_keyword():
    text = "CONTINUITY STIFFENER AT BOTH FLANGES"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["continuity_stiffener_pairs"] == 2


def test_fw_abbreviation_weld():
    text = "WEB DOUBLER WITH 10MM FW"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["weld_type"] == "FILLET_WELD"
    assert parsed["weld_size_mm"] == 10.0


def test_two_sides_keyword():
    text = "WEB DOUBLER 2 SIDES 12MM"
    parsed = parse_moment_doubler_stiffener_callout(text)
    assert parsed is not None
    assert parsed["doubler_configuration"] == "DOUBLE_DOUBLER"
    assert parsed["doubler_thickness_mm"] == 12.0
