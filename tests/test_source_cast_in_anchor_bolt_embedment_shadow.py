"""
Unit and adversarial test suite for Source Structural Steel Cast-In Anchor Bolt & Embedment Shadow Authority.
"""

import pytest
from pb_source_cast_in_anchor_bolt_embedment_shadow import (
    CastInAnchorBoltEmbedmentCallout,
    SourceCastInAnchorBoltEmbedmentShadowAuthority,
    parse_cast_in_anchor_bolt_embedment_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_cast_in_anchor():
    text = "BASE PLATE C1: 4-M24 GRADE 8.8 CAST-IN ANCHOR BOLTS, 500MM EMBEDMENT DEPTH WITH BOTTOM NUT AND SQUARE ANCHOR PLATE WASHER, 120MM PROJECTION"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["bolt_count"] == 4
    assert res["thread_size"] == "M24"
    assert res["bolt_grade"] == "GRADE_8_8_HIGH_TENSILE"
    assert res["embedment_depth_mm"] == 500.0
    assert res["anchor_termination"] == "HEAVY_HEX_NUT_AND_SQUARE_PLATE_WASHER"
    assert res["projection_above_top_of_concrete_mm"] == 120.0


def test_parse_cogged_hook():
    text = "COLUMN BASE: 6-M30 HD BOLTS GRADE 4.6, 600MM EMBED WITH COGGED L-HOOK"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["bolt_count"] == 6
    assert res["thread_size"] == "M30"
    assert res["bolt_grade"] == "GRADE_4_6_COMMERCIAL"
    assert res["embedment_depth_mm"] == 600.0
    assert res["anchor_termination"] == "COGGED_L_HOOK"


def test_parse_j_bolt_hook():
    text = "LIGHT POLE FOOTING: 4xM20 J-BOLT ANCHOR RODS, EMBEDMENT: 400MM"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["bolt_count"] == 4
    assert res["thread_size"] == "M20"
    assert res["anchor_termination"] == "J_BOLT_HOOK"
    assert res["embedment_depth_mm"] == 400.0


def test_parse_defaults():
    text = "CAST-IN ANCHOR BOLTS"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["bolt_count"] == 4
    assert res["thread_size"] == "M24"
    assert res["bolt_grade"] == "GRADE_8_8_HIGH_TENSILE"
    assert res["embedment_depth_mm"] == 450.0


def test_parse_non_anchor():
    text = "SLAB REINFORCING SL82 MESH"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(50.1, 74.9, snap_tol=2.5)
    assert pt == (50.0, 75.0)


def test_authority_processing_dedup():
    auth = SourceCastInAnchorBoltEmbedmentShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("4-M24 HD BOLTS", (10.0, 20.0)),
        ("4-M24 HD BOLTS", (10.5, 20.2)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceCastInAnchorBoltEmbedmentShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("4-M24 HD BOLTS", (10.0, 20.0)),
        ("4-M24 HD BOLTS", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceCastInAnchorBoltEmbedmentShadowAuthority()
    oversized = [("4-M24 HD BOLTS", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceCastInAnchorBoltEmbedmentShadowAuthority()
    res = auth.process_callouts([("4-M24 HD BOLTS", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_m16_small_stud():
    text = "2-M16 HOLD DOWN BOLTS GRADE 4.6"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["bolt_count"] == 2
    assert res["thread_size"] == "M16"
    assert res["bolt_grade"] == "GRADE_4_6_COMMERCIAL"


def test_m36_large_portal_frame():
    text = "PORTAL FRAME BASE: 8-M36 GRADE 8.8 CAST IN ANCHOR BOLTS, 800MM MIN EMBED"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["bolt_count"] == 8
    assert res["thread_size"] == "M36"
    assert res["embedment_depth_mm"] == 800.0


def test_stainless_steel_grade():
    text = "4-M20 316 STAINLESS STEEL ANCHOR BOLTS"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["bolt_grade"] == "STAINLESS_STEEL_A4_70"


def test_empty_string():
    assert parse_cast_in_anchor_bolt_embedment_callout("") is None


def test_frozen_dataclass_immutability():
    callout = CastInAnchorBoltEmbedmentCallout(
        raw_text="text",
        bolt_grade="GRADE_8_8",
        thread_size="M24",
        bolt_count=4,
        embedment_depth_mm=450.0,
        anchor_termination="PLATE",
        projection_above_top_of_concrete_mm=100.0,
    )
    with pytest.raises(Exception):
        callout.bolt_count = 6  # type: ignore


def test_baseplate_bolt_trigger():
    text = "BASE PLATE BOLT M24, 450 EMBED"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["thread_size"] == "M24"
    assert res["embedment_depth_mm"] == 450.0


def test_projection_parsing():
    text = "4-M24 HD BOLTS WITH 150MM PROJECTION"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["projection_above_top_of_concrete_mm"] == 150.0


def test_zero_tolerance_snap():
    pt = snap_point(11.22, 33.44, snap_tol=0.0)
    assert pt == (11.22, 33.44)


def test_different_bolt_counts_same_location():
    auth = SourceCastInAnchorBoltEmbedmentShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("4-M24 HD BOLTS", (10.0, 20.0)),
        ("6-M24 HD BOLTS", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_anchor_rod_keyword():
    text = "ANCHOR ROD M20 GRADE 8.8, 350 EMBED"
    res = parse_cast_in_anchor_bolt_embedment_callout(text)
    assert res is not None
    assert res["thread_size"] == "M20"
    assert res["embedment_depth_mm"] == 350.0
