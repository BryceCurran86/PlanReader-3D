"""
Unit and adversarial test suite for Source Cavity Masonry Movement Control Joint & Debonded Tie Shadow Authority.
"""

import pytest
from pb_source_masonry_control_joint_tie_shadow import (
    MasonryControlJointTieCallout,
    SourceMasonryControlJointTieShadowAuthority,
    parse_masonry_control_joint_tie_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_control_joint():
    text = "BRICKWORK ELEVATION: 15MM VERTICAL CONTROL JOINT (MCJ), DEBONDED SLIP TIE WITH SLEEVE AT 400MM CTS, 20MM BACKING ROD WITH POLYURETHANE SEALANT"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["joint_width_mm"] == 15.0
    assert res["tie_type"] == "DEBONDED_SLIP_TIE_WITH_SLEEVE"
    assert res["tie_vertical_spacing_mm"] == 400.0
    assert res["backing_rod_diameter_mm"] == 20.0
    assert res["sealant_type"] == "POLYURETHANE_ELASTOMERIC_SEALANT"


def test_parse_silicone_articulation():
    text = "10MM ARTICULATION JOINT AJ, LOW MODULUS SILICONE SEALANT, STAINLESS STEEL EXPANSION TIE @ 600MM C/C"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["joint_width_mm"] == 10.0
    assert res["tie_type"] == "EXPANSION_TIE_STAINLESS_STEEL"
    assert res["sealant_type"] == "LOW_MODULUS_SILICONE"
    assert res["tie_vertical_spacing_mm"] == 600.0


def test_parse_dovetail_anchor():
    text = "CONCRETE COLUMN TO MASONRY: 20MM MOVEMENT JOINT WITH DOVETAIL DEBONDED ANCHOR"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["joint_width_mm"] == 20.0
    assert res["tie_type"] == "DOVETAIL_DEBONDED_ANCHOR"


def test_parse_defaults():
    text = "MASONRY CONTROL JOINT"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["joint_width_mm"] == 10.0
    assert res["tie_type"] == "DEBONDED_SLIP_TIE_WITH_SLEEVE"
    assert res["tie_vertical_spacing_mm"] == 400.0


def test_parse_non_masonry():
    text = "SUSPENDED PLASTERBOARD CEILING"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(42.3, 99.8, snap_tol=2.5)
    assert pt == (42.5, 100.0)


def test_authority_processing_dedup():
    auth = SourceMasonryControlJointTieShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("10MM CONTROL JOINT", (10.0, 20.0)),
        ("10MM CONTROL JOINT", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceMasonryControlJointTieShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("10MM CONTROL JOINT", (10.0, 20.0)),
        ("10MM CONTROL JOINT", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceMasonryControlJointTieShadowAuthority()
    oversized = [("10MM CONTROL JOINT", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceMasonryControlJointTieShadowAuthority()
    res = auth.process_callouts([("10MM CONTROL JOINT", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_masonry_control_joint_tie_callout("") is None


def test_hybrid_polymer_sealant():
    text = "15MM MCJ WITH HYBRID MS POLYMER SEALANT"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["sealant_type"] == "HYBRID_POLYMER"


def test_zero_tolerance_snap():
    pt = snap_point(8.12, 14.16, snap_tol=0.0)
    assert pt == (8.12, 14.16)


def test_frozen_dataclass_immutability():
    callout = MasonryControlJointTieCallout(
        raw_text="text",
        joint_width_mm=10.0,
        tie_type="SLIP",
        tie_vertical_spacing_mm=400.0,
        sealant_type="PU",
        backing_rod_diameter_mm=13.0,
    )
    with pytest.raises(Exception):
        callout.joint_width_mm = 20.0  # type: ignore


def test_backing_rod_calculated():
    text = "16MM EXPANSION JOINT"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["backing_rod_diameter_mm"] == 20.0  # 16 * 1.25


def test_different_widths_same_point():
    auth = SourceMasonryControlJointTieShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("10MM CONTROL JOINT", (10.0, 20.0)),
        ("20MM CONTROL JOINT", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_spacing_centres():
    text = "MASONRY ARTICULATION JOINT WITH TIES AT 300MM CENTRES"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["tie_vertical_spacing_mm"] == 300.0


def test_pu_mastic():
    text = "10MM MOVEMENT JOINT WITH PU MASTIC"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["sealant_type"] == "POLYURETHANE_ELASTOMERIC_SEALANT"


def test_slip_tie_keyword():
    text = "SLIP TIE ACROSS 15MM GAP"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["joint_width_mm"] == 15.0
    assert res["tie_type"] == "DEBONDED_SLIP_TIE_WITH_SLEEVE"


def test_aj_abbreviation():
    text = "VERTICAL AJ AT 6M MAX SPACING, 10MM WIDE"
    res = parse_masonry_control_joint_tie_callout(text)
    assert res is not None
    assert res["joint_width_mm"] == 10.0
