"""Unit tests for Source Cast-In Concrete Starter Bar Dowel Box & Pull-Out Rebend Shadow Authority."""

import pytest
from pb_source_starter_bar_rebend_box_shadow import (
    StarterBarRebendCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_starter_bar_rebend_callout,
    evaluate_starter_bar_rebend_box_shadow,
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


def test_parse_starter_bar_rebend_callout_single_n12():
    text = "STARTER BAR BOX N12 @ 150 CTS 100MM WIDE CASING 500MM LAP SLAB TO WALL"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "SINGLE_ROW"
    assert parsed["bar_diameter_mm"] == 12.0
    assert parsed["bar_spacing_mm"] == 150.0
    assert parsed["casing_width_mm"] == 100.0
    assert parsed["pull_out_lap_length_mm"] == 500.0
    assert parsed["joint_location"] == "SLAB_TO_WALL"


def test_parse_starter_bar_rebend_callout_double_n16():
    text = "REBEND BOX DOUBLE ROW N16 @ 200 C/C 170MM CASING 600MM LAP WALL TO SLAB"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "DOUBLE_ROW"
    assert parsed["bar_diameter_mm"] == 16.0
    assert parsed["bar_spacing_mm"] == 200.0
    assert parsed["casing_width_mm"] == 170.0
    assert parsed["pull_out_lap_length_mm"] == 600.0
    assert parsed["joint_location"] == "WALL_TO_SLAB"


def test_parse_starter_bar_rebend_callout_reidbox():
    text = "REIDBOX PULL-OUT BAR N12 @ 200 CTS"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["bar_diameter_mm"] == 12.0
    assert parsed["bar_spacing_mm"] == 200.0


def test_parse_starter_bar_rebend_callout_eazistrip_wall_to_wall():
    text = "EAZISTRIP CONTINUITY STRIP BOX WALL TO WALL"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["joint_location"] == "WALL_TO_WALL"


def test_parse_starter_bar_rebend_callout_unrelated():
    assert parse_starter_bar_rebend_callout("ALUMINUM SKIRTING 100MM") is None


def test_evaluate_starter_bar_rebend_box_shadow_single():
    callouts = ["STARTER BAR BOX N12 @ 150 CTS"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_starter_bar_rebend_box_shadow("S-801", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "S-801_sbb_001"
    assert c.sheet_id == "S-801"
    assert c.bar_diameter_mm == 12.0
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_starter_bar_rebend_box_shadow_dict():
    c = StarterBarRebendCandidate(
        candidate_id="S-802_sbb_001",
        sheet_id="S-802",
        row_configuration="SINGLE_ROW",
        bar_diameter_mm=12.0,
        bar_spacing_mm=150.0,
        casing_width_mm=100.0,
        pull_out_lap_length_mm=500.0,
        joint_location="SLAB_TO_WALL",
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "S-802_sbb_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["bar_diameter_mm"] == 12.0


def test_evaluate_starter_bar_rebend_box_shadow_no_polys():
    callouts = ["STARTER BAR BOX N12"]
    res = evaluate_starter_bar_rebend_box_shadow("S-803", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_starter_bar_rebend_box_shadow_safety_cap():
    callouts = ["STARTER BAR BOX"] * 10
    res = evaluate_starter_bar_rebend_box_shadow("S-804", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_starter_bar_rebend_box_shadow("S-805", []) == []


def test_unrelated_callout_filtering():
    callouts = ["SUSPENDED CEILING GRID", "REBEND BOX N16"]
    res = evaluate_starter_bar_rebend_box_shadow("S-806", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "S-806_sbb_002"


def test_bartec_trigger():
    text = "BARTEC BOX WITH 16MM BAR"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["bar_diameter_mm"] == 16.0


def test_two_row_keyword():
    text = "DOWEL BOX 2-ROW N12"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "DOUBLE_ROW"


def test_default_values():
    text = "STARTER BOX"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "SINGLE_ROW"
    assert parsed["bar_diameter_mm"] == 12.0
    assert parsed["bar_spacing_mm"] == 200.0
    assert parsed["casing_width_mm"] == 100.0
    assert parsed["pull_out_lap_length_mm"] == 500.0


def test_snapping_precision():
    callouts = ["STARTER BAR BOX"]
    polys = [[(1.2, 1.2), (48.8, 1.2)]]
    res = evaluate_starter_bar_rebend_box_shadow("S-807", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (50.0, 0.0)
    assert res[0].length_pt == 50.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0


def test_development_length_keyword():
    text = "PULL OUT BAR 600MM DEVELOPMENT"
    parsed = parse_starter_bar_rebend_callout(text)
    assert parsed is not None
    assert parsed["pull_out_lap_length_mm"] == 600.0
