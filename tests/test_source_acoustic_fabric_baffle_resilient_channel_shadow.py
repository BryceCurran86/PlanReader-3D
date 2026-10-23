"""Unit tests for Source Acoustic Wall Fabric Baffle & Resilient Channel Shadow Authority."""

import pytest
from pb_source_acoustic_fabric_baffle_resilient_channel_shadow import (
    AcousticWallBaffleCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_acoustic_wall_baffle_callout,
    evaluate_acoustic_fabric_baffle_resilient_channel_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((2.6, 5.1)) == (2.5, 5.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_snap_polyline_removes_duplicates():
    pts = [(0.0, 0.0), (0.2, 0.3), (50.0, 50.0)]
    snapped = snap_polyline(pts)
    assert len(snapped) == 2
    assert snapped[0] == (0.0, 0.0)
    assert snapped[1] == (50.0, 50.0)


def test_calculate_polyline_length():
    pts = [(0.0, 0.0), (0.0, 100.0)]
    assert calculate_polyline_length(pts) == 100.0


def test_parse_acoustic_wall_baffle_callout_fiberglass_rc1():
    text = "ACOUSTIC WALL PANEL 50MM FIBERGLASS CORE NRC 0.95 ON RC-1 CHANNEL @ 600 CTS FABRIC WRAPPED"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["panel_core_material"] == "FIBERGLASS_CORE"
    assert parsed["panel_thickness_mm"] == 50.0
    assert parsed["nrc_rating"] == 0.95
    assert parsed["resilient_channel_type"] == "RC_1_SINGLE_LEG"
    assert parsed["channel_spacing_mm"] == 600.0
    assert parsed["fabric_finish"] == "ACOUSTIC_TEXTILE"


def test_parse_acoustic_wall_baffle_callout_polyester_rc2():
    text = "FABRIC BAFFLE 25MM POLYESTER FIBRE NRC 0.85 RC-2 CHANNEL @ 400MM CTS"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["panel_core_material"] == "POLYESTER_FIBRE"
    assert parsed["panel_thickness_mm"] == 25.0
    assert parsed["nrc_rating"] == 0.85
    assert parsed["resilient_channel_type"] == "RC_2_DOUBLE_LEG"
    assert parsed["channel_spacing_mm"] == 400.0


def test_parse_acoustic_wall_baffle_callout_melamine_foam_clip():
    text = "SOUND ABSORBING PANEL ACOUSTIC FOAM NRC 1.00 WITH ISOLATION CLIP"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["panel_core_material"] == "ACOUSTIC_FOAM"
    assert parsed["nrc_rating"] == 1.00
    assert parsed["resilient_channel_type"] == "RESILIENT_CLIP"


def test_parse_acoustic_wall_baffle_callout_timber_slat():
    text = "TIMBER SLAT ACOUSTIC WALL LINING PERFORATED VINYL FINISH"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["panel_core_material"] == "TIMBER_ACOUSTIC_SLAT"
    assert parsed["fabric_finish"] == "PERFORATED_VINYL"


def test_parse_acoustic_wall_baffle_callout_unrelated():
    assert parse_acoustic_wall_baffle_callout("CERAMIC WALL TILES 300X600") is None


def test_evaluate_acoustic_fabric_baffle_resilient_channel_shadow_single():
    callouts = ["ACOUSTIC WALL PANEL 50MM NRC 0.90"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_acoustic_fabric_baffle_resilient_channel_shadow("A-701", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "A-701_awb_001"
    assert c.sheet_id == "A-701"
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_acoustic_fabric_baffle_resilient_channel_shadow_dict():
    c = AcousticWallBaffleCandidate(
        candidate_id="A-702_awb_001",
        sheet_id="A-702",
        panel_core_material="FIBERGLASS_CORE",
        panel_thickness_mm=50.0,
        nrc_rating=0.95,
        resilient_channel_type="RC_1_SINGLE_LEG",
        channel_spacing_mm=600.0,
        fabric_finish="ACOUSTIC_TEXTILE",
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "A-702_awb_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["nrc_rating"] == 0.95


def test_evaluate_acoustic_fabric_baffle_resilient_channel_shadow_no_polys():
    callouts = ["ACOUSTIC BAFFLE 50MM"]
    res = evaluate_acoustic_fabric_baffle_resilient_channel_shadow("A-703", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_acoustic_fabric_baffle_resilient_channel_shadow_safety_cap():
    callouts = ["ACOUSTIC WALL PANEL"] * 10
    res = evaluate_acoustic_fabric_baffle_resilient_channel_shadow("A-704", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_acoustic_fabric_baffle_resilient_channel_shadow("A-705", []) == []


def test_unrelated_callout_filtering():
    callouts = ["PLASTERBOARD WALL 13MM", "ACOUSTIC WALL PANEL 50MM"]
    res = evaluate_acoustic_fabric_baffle_resilient_channel_shadow("A-706", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "A-706_awb_002"


def test_fabric_wrapped_panel_trigger():
    text = "FABRIC WRAPPED PANEL 25MM"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["panel_thickness_mm"] == 25.0
    assert parsed["fabric_finish"] == "ACOUSTIC_TEXTILE"


def test_double_leg_keyword():
    text = "RESILIENT CHANNEL DOUBLE LEG MOUNT"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["resilient_channel_type"] == "RC_2_DOUBLE_LEG"


def test_default_values():
    text = "ACOUSTIC WALL PANEL"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["panel_core_material"] == "FIBERGLASS_CORE"
    assert parsed["panel_thickness_mm"] == 50.0
    assert parsed["nrc_rating"] == 0.85
    assert parsed["resilient_channel_type"] == "DIRECT_ADHESIVE"


def test_snapping_precision():
    callouts = ["ACOUSTIC WALL PANEL"]
    polys = [[(1.2, 1.2), (48.8, 1.2)]]
    res = evaluate_acoustic_fabric_baffle_resilient_channel_shadow("A-707", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (50.0, 0.0)
    assert res[0].length_pt == 50.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0


def test_resilient_clip_spacing():
    text = "ACOUSTIC WALL PANEL WITH RESILIENT CLIP"
    parsed = parse_acoustic_wall_baffle_callout(text)
    assert parsed is not None
    assert parsed["channel_spacing_mm"] == 600.0
