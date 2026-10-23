"""
Tests for Source Cast-in Concrete Wall Anchor Channel Embed Cold-Formed Channel Shadow Authority.
"""

import pytest
from pb_source_cast_in_anchor_channel_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    CastInAnchorChannelCallout,
    snap_point,
    parse_cast_in_anchor_channel_callout,
    extract_cast_in_anchor_channel_candidates,
    validate_cast_in_anchor_channel_system,
)


def test_snap_point_regular():
    pt = snap_point(62.3, 77.7, snap_tol=2.5)
    assert pt == (62.5, 77.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(62.3, 77.7, snap_tol=0.0)
    assert pt == (62.3, 77.7)


def test_parse_none_on_irrelevant_text():
    assert parse_cast_in_anchor_channel_callout("CARPET TILES OVER SCREED") is None
    assert parse_cast_in_anchor_channel_callout("TIMBER SKIRTING BOARD") is None
    assert parse_cast_in_anchor_channel_callout("ACOUSTIC CEILING PANEL") is None


def test_parse_curtain_wall_hac_anchor_channel():
    text = "CAST-IN ANCHOR CHANNEL HAC-50 350MM LONG HDG WITH ROUND HEAD STUD ANCHORS FOR CURTAIN WALL BRACKET"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_series"] == "HAC-50"
    assert parsed["channel_length_mm"] == 350.0
    assert parsed["material_finish"] == "HOT_DIP_GALVANIZED_STEEL"
    assert parsed["anchor_stud_type"] == "ROUND_HEAD_STUD_ANCHOR"
    assert parsed["structural_application"] == "CURTAIN_WALL_BRACKET"


def test_parse_halfen_hot_rolled_elevator_guide():
    text = "HALFEN CHANNEL HTA-52/34 HOT ROLLED L=1050MM STAINLESS STEEL A4 WITH FORGED I-ANCHOR FOR ELEVATOR GUIDE RAIL"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_profile"] == "HOT_ROLLED_ANCHOR_CHANNEL"
    assert parsed["channel_series"] == "HTA-52/34"
    assert parsed["channel_length_mm"] == 1050.0
    assert parsed["material_finish"] == "STAINLESS_STEEL_A4_316"
    assert parsed["anchor_stud_type"] == "I_STUD_FORGED_ANCHOR"
    assert parsed["structural_application"] == "ELEVATOR_GUIDE_RAIL"


def test_parse_toothed_serrated_channel():
    text = "TOOTHED SERRATED ANCHOR CHANNEL HAC-T 250MM LG WITH COMB FOAM FILLER"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_profile"] == "TOOTHED_SERRATED_CHANNEL"
    assert parsed["channel_length_mm"] == 250.0
    assert parsed["filler_type"] == "COMB_FOAM_FILLER"


def test_parse_slab_edge_facia_embed():
    text = "SLAB EDGE FACIA CHANNEL EMBED 300MM ANCHOR CHANNEL WITH CLOSED CELL FOAM STRIP FOR PRECAST CLADDING"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_profile"] == "SLAB_EDGE_FACIA_CHANNEL"
    assert parsed["channel_length_mm"] == 300.0
    assert parsed["filler_type"] == "CLOSED_CELL_FOAM_STRIP"
    assert parsed["structural_application"] == "PRECAST_CLADDING_FACADE"


def test_parse_mep_pipe_support_application():
    text = "EMBEDDED CHANNEL JORDAHL W40/22 200MM LONG WITH END LUG ANCHOR FOR PIPE SUPPORT"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_series"] == "W40/22"
    assert parsed["channel_length_mm"] == 200.0
    assert parsed["anchor_stud_type"] == "END_LUG_ANCHOR"
    assert parsed["structural_application"] == "MEP_PIPE_SUPPORT"


def test_parse_pe_filler_and_mill_finish():
    text = "C-CHANNEL EMBED HTA-40/22 MILL FINISH WITH PE FILLER"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_series"] == "HTA-40/22"
    assert parsed["material_finish"] == "CARBON_STEEL_MILL_FINISH"
    assert parsed["filler_type"] == "PE_PLASTIC_FILLER"


def test_extract_cast_in_anchor_channel_candidates():
    items = [
        ("CAST-IN ANCHOR CHANNEL HAC-50 350MM LONG", (100.1, 200.2)),
        ("VINYL COVE SKIRTING", (30.0, 40.0)),
        ("HALFEN CHANNEL HTA-52/34 1050MM FOR ELEVATOR", (400.0, 500.0)),
    ]
    candidates = extract_cast_in_anchor_channel_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (100.0, 200.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"CAST-IN ANCHOR CHANNEL {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_cast_in_anchor_channel_candidates(items, max_cap=13)
    assert len(candidates) == 13


def test_system_validation_summary():
    items = [
        ("CAST-IN ANCHOR CHANNEL HAC-50 350MM LONG", (10.0, 20.0)),
        ("HALFEN CHANNEL HTA-52/34 1050MM FOR ELEVATOR", (30.0, 40.0)),
        ("TOOTHED SERRATED ANCHOR CHANNEL 250MM", (50.0, 60.0)),
    ]
    candidates = extract_cast_in_anchor_channel_candidates(items)
    summary = validate_cast_in_anchor_channel_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["specified_series_count"] == 2
    assert summary["specified_length_count"] == 3
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = CastInAnchorChannelCallout(
        raw_text="SAMPLE",
        channel_profile="COLD_FORMED_ANCHOR_CHANNEL",
        channel_series="HAC-50",
        channel_length_mm=350.0,
        anchor_stud_type="ROUND_HEAD_STUD_ANCHOR",
        material_finish="HOT_DIP_GALVANIZED_STEEL",
        filler_type="CLOSED_CELL_FOAM_STRIP",
        structural_application="CURTAIN_WALL_BRACKET",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_cast_in_anchor_channel_candidates([])
    assert len(candidates) == 0
    summary = validate_cast_in_anchor_channel_system([])
    assert summary["total_candidates"] == 0
    assert summary["specified_series_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_cast_in_anchor_channel_callout("ALUMINUM WINDOW SUBHEAD CHANNEL") is None
    assert parse_cast_in_anchor_channel_callout("DRYWALL STUD CEILING CHANNEL") is None
    assert parse_cast_in_anchor_channel_callout("CONCRETE CHANNEL DRAIN IN DRIVEWAY") is None


def test_headed_stud_anchor_variant():
    text = "CAST IN CHANNEL WITH HEADED STUD ANCHOR HDG"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["anchor_stud_type"] == "ROUND_HEAD_STUD_ANCHOR"
    assert parsed["material_finish"] == "HOT_DIP_GALVANIZED_STEEL"


def test_rip_cord_filler():
    text = "FACADE ANCHOR CHANNEL WITH RIP CORD FOAM"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["filler_type"] == "COMB_FOAM_FILLER"


def test_cold_formed_explicit():
    text = "COLD-FORMED ANCHOR CHANNEL 150MM LG"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_profile"] == "COLD_FORMED_ANCHOR_CHANNEL"
    assert parsed["channel_length_mm"] == 150.0


def test_ss316_finish():
    text = "HALFEN ANCHOR CHANNEL SS316 200MM LONG"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["material_finish"] == "STAINLESS_STEEL_A4_316"
    assert parsed["channel_length_mm"] == 200.0


def test_cable_tray_mep_application():
    text = "CHANNEL EMBED FOR CABLE TRAY SUPPORT"
    parsed = parse_cast_in_anchor_channel_callout(text)
    assert parsed is not None
    assert parsed["structural_application"] == "MEP_PIPE_SUPPORT"
