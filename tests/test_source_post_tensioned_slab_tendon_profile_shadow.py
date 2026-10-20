"""
Unit and adversarial test suite for Source Post-Tensioned Suspended Slab Tendon Profile & Drape Shadow Authority.
"""

import pytest
from pb_source_post_tensioned_slab_tendon_profile_shadow import (
    PtTendonProfileCallout,
    SourcePostTensionedSlabTendonProfileShadowAuthority,
    parse_pt_tendon_profile_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_pt_tendon():
    text = "LEVEL 2 PT SLAB: 4-STRAND TENDON IN FLAT CORRUGATED PLASTIC DUCT, 200MM SLAB, HIGH: 165MM, LOW: 30MM"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["strand_count"] == 4
    assert res["tendon_group_count"] == 1
    assert res["high_point_chair_mm"] == 165.0
    assert res["low_point_chair_mm"] == 30.0
    assert res["slab_thickness_mm"] == 200.0
    assert res["duct_type"] == "FLAT_PLASTIC_CORRUGATED_DUCT"


def test_parse_5_strand_steel_duct():
    text = "POST-TENSIONED BAND BEAM: 5-STRAND TENDON FLAT GALVANIZED STEEL DUCT, 250MM THK, HP 215, LP 35"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["strand_count"] == 5
    assert res["duct_type"] == "FLAT_GALVANIZED_STEEL_DUCT"
    assert res["high_point_chair_mm"] == 215.0
    assert res["low_point_chair_mm"] == 35.0
    assert res["slab_thickness_mm"] == 250.0


def test_parse_multi_tendon_group():
    text = "PT SLAB: 3X 4-STRAND TENDONS, 220MM SLAB"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["strand_count"] == 4
    assert res["tendon_group_count"] == 3
    assert res["slab_thickness_mm"] == 220.0
    assert res["high_point_chair_mm"] == 185.0  # 220 - 35


def test_parse_defaults():
    text = "POST TENSION TENDON"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["strand_count"] == 4
    assert res["slab_thickness_mm"] == 200.0
    assert res["high_point_chair_mm"] == 165.0
    assert res["low_point_chair_mm"] == 30.0


def test_parse_non_pt():
    text = "SUSPENDED GYPROCK CEILING"
    res = parse_pt_tendon_profile_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(62.3, 114.9, snap_tol=2.5)
    assert pt == (62.5, 115.0)


def test_authority_processing_dedup():
    auth = SourcePostTensionedSlabTendonProfileShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("4-STRAND TENDON 200MM SLAB", (10.0, 20.0)),
        ("4-STRAND TENDON 200MM SLAB", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourcePostTensionedSlabTendonProfileShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("4-STRAND TENDON 200MM SLAB", (10.0, 20.0)),
        ("4-STRAND TENDON 200MM SLAB", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourcePostTensionedSlabTendonProfileShadowAuthority()
    oversized = [("4-STRAND TENDON", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourcePostTensionedSlabTendonProfileShadowAuthority()
    res = auth.process_callouts([("4-STRAND TENDON", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_pt_tendon_profile_callout("") is None


def test_round_duct():
    text = "ROUND MULTI-STRAND DUCT TENDON PROFILE"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["duct_type"] == "ROUND_MULTI_STRAND_DUCT"


def test_zero_tolerance_snap():
    pt = snap_point(31.31, 62.62, snap_tol=0.0)
    assert pt == (31.31, 62.62)


def test_frozen_dataclass_immutability():
    callout = PtTendonProfileCallout(
        raw_text="text",
        strand_count=4,
        tendon_group_count=1,
        high_point_chair_mm=165.0,
        low_point_chair_mm=30.0,
        slab_thickness_mm=200.0,
        duct_type="FLAT_PLASTIC",
    )
    with pytest.raises(Exception):
        callout.strand_count = 5  # type: ignore


def test_different_strands_same_point():
    auth = SourcePostTensionedSlabTendonProfileShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("3-STRAND TENDON 200MM SLAB", (10.0, 20.0)),
        ("5-STRAND TENDON 200MM SLAB", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_drape_profile_trigger():
    text = "DRAPE PROFILE HP: 190, LP: 25 IN 230THK SLAB"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["high_point_chair_mm"] == 190.0
    assert res["low_point_chair_mm"] == 25.0
    assert res["slab_thickness_mm"] == 230.0


def test_chair_height_trigger():
    text = "CHAIR HEIGHT HIGH POINT 170MM, LOW POINT 35MM"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["high_point_chair_mm"] == 170.0
    assert res["low_point_chair_mm"] == 35.0


def test_3_strand_tendon():
    text = "3-STRAND TENDON PROFILE"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["strand_count"] == 3


def test_bottom_chair_spelling():
    text = "TENDON PROFILE TOP: 180, BOTTOM: 40"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["high_point_chair_mm"] == 180.0
    assert res["low_point_chair_mm"] == 40.0


def test_high_depth_slab():
    text = "PT SLAB 300MM DEPTH, 5-STRAND TENDON"
    res = parse_pt_tendon_profile_callout(text)
    assert res is not None
    assert res["slab_thickness_mm"] == 300.0
    assert res["high_point_chair_mm"] == 265.0  # 300 - 35
