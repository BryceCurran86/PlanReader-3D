"""
Tests for Source Structural Steel Rafter Knee Haunch Stiffener Plate Shadow Authority.
"""

import pytest
from pb_source_steel_knee_haunch_stiffener_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    SteelKneeHaunchStiffenerCallout,
    snap_point,
    parse_steel_knee_haunch_stiffener_callout,
    extract_steel_knee_haunch_stiffener_candidates,
    validate_steel_knee_haunch_stiffener_system,
)


def test_snap_point_regular():
    pt = snap_point(51.3, 98.7, snap_tol=2.5)
    assert pt == (52.5, 97.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(51.3, 98.7, snap_tol=0.0)
    assert pt == (51.3, 98.7)


def test_parse_none_on_irrelevant_text():
    assert parse_steel_knee_haunch_stiffener_callout("GYPROCK CEILING CORNICE") is None
    assert parse_steel_knee_haunch_stiffener_callout("CARPET TILES OVER UNDERLAY") is None
    assert parse_steel_knee_haunch_stiffener_callout("STAINLESS STEEL SINK BASIN") is None


def test_parse_tapered_cut_beam_knee_haunch():
    text = "PORTAL KNEE HAUNCH CUT FROM 530UB82 600MM DEEP 1500MM LONG WITH 16MM STIFFENER PLATE AND 8-M24 8.8/S BOLTS"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["haunch_type"] == "TAPERED_CUT_BEAM_HAUNCH"
    assert parsed["portal_member_section"] == "530UB82"
    assert parsed["haunch_depth_mm"] == 600.0
    assert parsed["haunch_length_mm"] == 1500.0
    assert parsed["stiffener_plate_thickness_mm"] == 16.0
    assert parsed["bolt_specification"] == "8-M248.8/S"


def test_parse_diagonal_knee_stiffener_with_fpbw():
    text = "RAFTER KNEE HAUNCH WITH 20MM THICK DIAGONAL KNEE STIFFENER AND FPBW TO COLUMN FLANGE"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["stiffener_orientation"] == "DIAGONAL_KNEE_STIFFENER"
    assert parsed["stiffener_plate_thickness_mm"] == 20.0
    assert parsed["weld_specification"] == "FPBW"


def test_parse_transverse_column_stiffener():
    text = "EAVES HAUNCH MOMENT CONNECTION WITH TRANSVERSE 12MM STIFFENER PLATE IN 460UB74 COLUMN"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["stiffener_orientation"] == "TRANSVERSE_COLUMN_STIFFENER"
    assert parsed["stiffener_plate_thickness_mm"] == 12.0
    assert parsed["portal_member_section"] == "460UB74"


def test_parse_fabricated_plate_haunch():
    text = "FABRICATED PLATE HAUNCH AT PORTAL KNEE WITH 8MM CFW AND M30 GRADE 8.8 BOLTS"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["haunch_type"] == "FABRICATED_PLATE_HAUNCH"
    assert parsed["weld_specification"] == "8MMCFW"
    assert parsed["bolt_specification"] == "M30GRADE8.8"


def test_parse_flange_doubler_haunch():
    text = "KNEE HAUNCH CONNECTION WITH 12MM FLANGE DOUBLER PLATE AND 10MM FILLET WELD"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["haunch_type"] == "FLANGE_DOUBLER_HAUNCH"
    assert parsed["weld_specification"] == "10MMFILLETWELD"


def test_parse_web_continuity_stiffener():
    text = "PORTAL FRAME HAUNCH WITH WEB CONTINUITY STIFFENER PLATES 16MM THK"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["stiffener_orientation"] == "WEB_CONTINUITY_STIFFENER"
    assert parsed["stiffener_plate_thickness_mm"] == 16.0


def test_parse_lg_haunch_length():
    text = "KNEE HAUNCH 1200 LG HAUNCH 500MM DEEP IN 610UB101"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["haunch_length_mm"] == 1200.0
    assert parsed["haunch_depth_mm"] == 500.0
    assert parsed["portal_member_section"] == "610UB101"


def test_extract_steel_knee_haunch_stiffener_candidates():
    items = [
        ("PORTAL KNEE HAUNCH CUT FROM 530UB82 600MM DEEP", (120.3, 240.7)),
        ("INTERNAL PLASTERBOARD PARTITION", (10.0, 20.0)),
        ("RAFTER HAUNCH STIFFENER PLATE 16MM WITH 8-M24 BOLTS", (500.0, 600.0)),
    ]
    candidates = extract_steel_knee_haunch_stiffener_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (120.0, 240.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"PORTAL KNEE HAUNCH {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_steel_knee_haunch_stiffener_candidates(items, max_cap=15)
    assert len(candidates) == 15


def test_system_validation_summary():
    items = [
        ("PORTAL KNEE HAUNCH CUT FROM 530UB82 600MM DEEP WITH 8-M24 8.8/S BOLTS", (10.0, 20.0)),
        ("RAFTER KNEE HAUNCH WITH 20MM THICK DIAGONAL KNEE STIFFENER AND FPBW", (30.0, 40.0)),
        ("FABRICATED PLATE HAUNCH AT PORTAL KNEE WITH 8MM CFW AND 6-M24 BOLTS", (50.0, 60.0)),
    ]
    candidates = extract_steel_knee_haunch_stiffener_candidates(items)
    summary = validate_steel_knee_haunch_stiffener_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["bolted_connections_count"] == 2
    assert summary["welded_connections_count"] == 2
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_uc_column_section():
    text = "COLUMN KNEE JOINT MOMENT CONNECTION 310UC96 WITH 20MM TRANSVERSE STIFFENER"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["portal_member_section"] == "310UC96"
    assert parsed["stiffener_orientation"] == "TRANSVERSE_COLUMN_STIFFENER"
    assert parsed["stiffener_plate_thickness_mm"] == 20.0


def test_candidate_dataclass_immutability():
    cand = SteelKneeHaunchStiffenerCallout(
        raw_text="SAMPLE",
        haunch_type="TAPERED_CUT_BEAM_HAUNCH",
        stiffener_plate_thickness_mm=16.0,
        haunch_depth_mm=600.0,
        haunch_length_mm=1500.0,
        bolt_specification="8-M248.8/S",
        weld_specification="FPBW",
        stiffener_orientation="DIAGONAL_KNEE_STIFFENER",
        portal_member_section="530UB82",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_steel_knee_haunch_stiffener_candidates([])
    assert len(candidates) == 0
    summary = validate_steel_knee_haunch_stiffener_system([])
    assert summary["total_candidates"] == 0
    assert summary["bolted_connections_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_steel_knee_haunch_stiffener_callout("STEEL LINTEL OVER WINDOW OPENING") is None
    assert parse_steel_knee_haunch_stiffener_callout("MASONRY TIES IN BRICK VENEER") is None
    assert parse_steel_knee_haunch_stiffener_callout("KNEE WALL IN RESIDENTIAL ATTIC") is None


def test_butt_weld_variant():
    text = "HAUNCH CONNECTION WITH BUTT WELD AND 16MM STIFFENER"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["weld_specification"] == "FPBW"
    assert parsed["stiffener_plate_thickness_mm"] == 16.0


def test_single_m24_bolt_with_word_bolt():
    text = "PORTAL KNEE HAUNCH WITH M24 STRUCTURAL BOLTS"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["bolt_specification"] == "M24STRUCTURAL"


def test_gp_weld_variant():
    text = "RAFTER HAUNCH STIFFENER WITH 6MM GP WELD"
    parsed = parse_steel_knee_haunch_stiffener_callout(text)
    assert parsed is not None
    assert parsed["weld_specification"] == "6MMGPWELD"
