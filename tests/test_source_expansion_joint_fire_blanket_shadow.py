"""Unit tests for Source Architectural Expansion Joint Fire Barrier Blanket Shadow Authority."""

import pytest
from pb_source_expansion_joint_fire_blanket_shadow import (
    FireBlanketCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_fire_blanket_callout,
    evaluate_expansion_joint_fire_blanket_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((2.4, 4.9)) == (2.5, 5.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_snap_polyline_removes_consecutive_duplicates():
    pts = [(0.0, 0.0), (0.5, 0.5), (10.0, 10.0)]
    snapped = snap_polyline(pts, snap_tol=2.5)
    # (0, 0) and (0.5, 0.5) both snap to (0, 0)
    assert len(snapped) == 2
    assert snapped[0] == (0.0, 0.0)
    assert snapped[1] == (10.0, 10.0)


def test_snap_polyline_empty():
    assert snap_polyline([]) == []


def test_calculate_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    assert calculate_polyline_length(pts) == 50.0


def test_calculate_polyline_length_single_point():
    assert calculate_polyline_length([(10.0, 20.0)]) == 0.0


def test_parse_fire_blanket_callout_floor_standard():
    text = "100MM EXPANSION JOINT FIRE BARRIER BLANKET 2-HR +/- 50% MOVEMENT"
    parsed = parse_fire_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_type"] == "FLOOR_EXPANSION_JOINT"
    assert parsed["joint_width_mm"] == 100.0
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["barrier_material"] == "CERAMIC_FIBRE_BLANKET"
    assert parsed["movement_capacity_pct"] == 50.0


def test_parse_fire_blanket_callout_wall_intumescent():
    text = "50MM WALL EXPANSION JOINT FIRE BLANKET INTUMESCENT 1-HR"
    parsed = parse_fire_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_type"] == "WALL_EXPANSION_JOINT"
    assert parsed["joint_width_mm"] == 50.0
    assert parsed["fire_rating_hours"] == 1.0
    assert parsed["barrier_material"] == "INTUMESCENT_FABRIC"


def test_parse_fire_blanket_callout_ceiling_mineral():
    text = "CEILING EXPANSION JOINT FIRE BARRIER BLANKET MINERAL WOOL FRL -/120/120"
    parsed = parse_fire_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_type"] == "CEILING_EXPANSION_JOINT"
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["barrier_material"] == "MINERAL_WOOL_MAT"


def test_parse_fire_blanket_callout_roof_graphite():
    text = "ROOF EXPANSION JOINT FIRE BARRIER GRAPHITE COMPOSITE 3-HR ± 25%"
    parsed = parse_fire_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_type"] == "ROOF_EXPANSION_JOINT"
    assert parsed["fire_rating_hours"] == 3.0
    assert parsed["barrier_material"] == "GRAPHITE_COMPOSITE"
    assert parsed["movement_capacity_pct"] == 25.0


def test_parse_fire_blanket_callout_unrelated():
    assert parse_fire_blanket_callout("ALUMINUM SKIRTING 100MM") is None


def test_evaluate_expansion_joint_fire_blanket_shadow_single():
    callouts = ["100MM EXPANSION JOINT FIRE BARRIER BLANKET 2-HR"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_expansion_joint_fire_blanket_shadow("A-101", callouts, polys)
    assert len(res) == 1
    cand = res[0]
    assert cand.candidate_id == "A-101_fbb_001"
    assert cand.sheet_id == "A-101"
    assert cand.joint_type == "FLOOR_EXPANSION_JOINT"
    assert cand.fire_rating_hours == 2.0
    assert cand.joint_width_mm == 100.0
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False
    assert cand.length_pt == 100.0


def test_evaluate_expansion_joint_fire_blanket_shadow_dict_serialization():
    cand = FireBlanketCandidate(
        candidate_id="TEST_001",
        sheet_id="A-101",
        joint_type="FLOOR_EXPANSION_JOINT",
        fire_rating_hours=2.0,
        joint_width_mm=100.0,
        barrier_material="CERAMIC_FIBRE_BLANKET",
        movement_capacity_pct=50.0,
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = cand.to_dict()
    assert d["candidate_id"] == "TEST_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["barrier_material"] == "CERAMIC_FIBRE_BLANKET"


def test_evaluate_expansion_joint_fire_blanket_shadow_no_polylines():
    callouts = ["150MM SEISMIC JOINT FIRE BARRIER BLANKET 2-HR"]
    res = evaluate_expansion_joint_fire_blanket_shadow("A-102", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_expansion_joint_fire_blanket_shadow_safety_cap():
    callouts = ["EXPANSION JOINT FIRE BLANKET 2-HR"] * 10
    res = evaluate_expansion_joint_fire_blanket_shadow("A-103", callouts, max_primitives=3)
    assert len(res) == 3


def test_parse_fire_blanket_callout_frl_three_digit():
    text = "EXPANSION JOINT FIRE BARRIER FRL -/180/180"
    parsed = parse_fire_blanket_callout(text)
    assert parsed is not None
    assert parsed["fire_rating_hours"] == 3.0


def test_parse_fire_blanket_callout_default_values():
    text = "JOINT FIRE BARRIER"
    parsed = parse_fire_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_type"] == "FLOOR_EXPANSION_JOINT"
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["joint_width_mm"] is None
    assert parsed["movement_capacity_pct"] == 50.0
    assert parsed["barrier_material"] == "CERAMIC_FIBRE_BLANKET"


def test_parse_fire_blanket_callout_ceramic_fiber_trigger():
    text = "CERAMIC FIBER FIRE BLANKET AT EXPANSION GAP"
    parsed = parse_fire_blanket_callout(text)
    assert parsed is not None
    assert parsed["barrier_material"] == "CERAMIC_FIBRE_BLANKET"


def test_snap_tolerance_constant():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    res = evaluate_expansion_joint_fire_blanket_shadow("A-104", [])
    assert res == []


def test_unmatched_callouts_filtered():
    callouts = ["STANDARD GYPROCK WALL", "100MM EXPANSION JOINT FIRE BLANKET"]
    res = evaluate_expansion_joint_fire_blanket_shadow("A-105", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "A-105_fbb_002"


def test_polyline_snapping_integration():
    callouts = ["100MM EXPANSION JOINT FIRE BARRIER BLANKET"]
    polys = [[(0.4, 0.4), (20.1, 0.2)]]
    res = evaluate_expansion_joint_fire_blanket_shadow("A-106", callouts, polys)
    assert len(res) == 1
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (20.0, 0.0)
    assert res[0].length_pt == 20.0
