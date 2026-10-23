"""
Unit and adversarial test suite for Source Precast Concrete Sandwich Panel Lifting Clutch & Tilt Anchor Shadow Authority.
"""

import pytest
from pb_source_precast_lifting_clutch_anchor_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    PrecastLiftingClutchAnchorCallout,
    snap_point,
    parse_precast_lifting_clutch_anchor_callout,
    evaluate_precast_lifting_clutch_anchor_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_precast_lifting_anchor_basic():
    text = "PRECAST PANEL EDGE LIFT ANCHOR 5.0T WITH RUBBER RECESS FORMER AND SHEAR BAR HAIRPIN 150MM EDGE DISTANCE"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["working_load_limit_tonnes"] == 5.0
    assert parsed["anchor_type"] == "EDGE_LIFT_ERECTION"
    assert parsed["recess_former_type"] == "RUBBER_RECESS_FORMER"
    assert parsed["supplementary_reinforcement"] == "SHEAR_BAR_HAIRPIN"
    assert parsed["min_edge_distance_mm"] == 150.0


def test_parse_face_lift_tilt_up():
    text = "TILT ANCHOR 10.0T FACE LIFT TILT UP WITH MAGNETIC FORMER AND BURSTING STIRRUPS 200MM MIN DISTANCE"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["working_load_limit_tonnes"] == 10.0
    assert parsed["anchor_type"] == "FACE_LIFT_TILT_UP"
    assert parsed["recess_former_type"] == "MAGNETIC_FORMER"
    assert parsed["supplementary_reinforcement"] == "PERIMETER_STIRRUPS"
    assert parsed["min_edge_distance_mm"] == 200.0


def test_parse_swift_lift_foot():
    text = "SWIFT LIFT 2.5T SPREAD ANCHOR 120MM EDGE"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["working_load_limit_tonnes"] == 2.5
    assert parsed["anchor_type"] == "SPHERICAL_HEAD_FOOT"
    assert parsed["min_edge_distance_mm"] == 120.0


def test_parse_unrelated():
    assert parse_precast_lifting_clutch_anchor_callout("STANDARD PLASTERBOARD LINING") is None
    assert parse_precast_lifting_clutch_anchor_callout("CARPET TILES FINISH") is None


def test_evaluate_precast_lifting_shadow_single():
    callouts = ["PRECAST CLUTCH 5.0T EDGE LIFT"]
    positions = [(10.1, 20.2)]
    results = evaluate_precast_lifting_clutch_anchor_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_precast_lifting_shadow_dict():
    items = [{"text": "LIFTING ANCHOR 2.5T", "position": (5.0, 7.6)}]
    results = evaluate_precast_lifting_clutch_anchor_shadow(items)
    assert len(results) == 1
    assert results[0].working_load_limit_tonnes == 2.5
    assert results[0].position == (5.0, 7.5)


def test_evaluate_precast_lifting_shadow_no_positions():
    results = evaluate_precast_lifting_clutch_anchor_shadow(["ERECTION ANCHOR"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_precast_lifting_shadow_safety_cap():
    huge_input = ["LIFTING ANCHOR"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_precast_lifting_clutch_anchor_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_precast_lifting_clutch_anchor_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "LIFTING ANCHOR 5T", "ROOM 101"]
    results = evaluate_precast_lifting_clutch_anchor_shadow(items)
    assert len(results) == 1
    assert results[0].working_load_limit_tonnes == 5.0


def test_pintle_anchor_trigger():
    text = "PINTLE ANCHOR 2.5 TONNE"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["working_load_limit_tonnes"] == 2.5


def test_reid_anchor_trigger():
    text = "REID ANCHOR 7.5T"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["working_load_limit_tonnes"] == 7.5


def test_default_values():
    text = "LIFTING CLUTCH"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["working_load_limit_tonnes"] == 5.0
    assert parsed["anchor_type"] == "EDGE_LIFT_ERECTION"
    assert parsed["recess_former_type"] == "RUBBER_RECESS_FORMER"
    assert parsed["supplementary_reinforcement"] == "STANDARD_MESH_ONLY"
    assert parsed["min_edge_distance_mm"] == 150.0


def test_snapping_precision():
    callouts = ["EDGE LIFT ANCHOR"]
    positions = [(12.49, 13.76)]
    results = evaluate_precast_lifting_clutch_anchor_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_steel_former_type():
    text = "LIFTING ANCHOR 5T WITH STEEL FORMER"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["recess_former_type"] == "STEEL_FORMER"


def test_1_3t_small_anchor():
    text = "EDGE LIFT 1.3T"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["working_load_limit_tonnes"] == 1.3


def test_tension_bar_trigger():
    text = "FACE LIFT 5T WITH TENSION BAR"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["supplementary_reinforcement"] == "SHEAR_BAR_HAIRPIN"


def test_invalid_item_types():
    results = evaluate_precast_lifting_clutch_anchor_shadow([123, None, object()])
    assert results == []


def test_u_bar_reinforcement():
    text = "LIFTING ANCHOR WITH U-BAR"
    parsed = parse_precast_lifting_clutch_anchor_callout(text)
    assert parsed is not None
    assert parsed["supplementary_reinforcement"] == "SHEAR_BAR_HAIRPIN"
