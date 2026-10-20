"""
Unit and adversarial test suite for Source Architectural Expansion Joint Waterstop Floor Floor Shadow Authority.
"""

import pytest
from pb_source_floor_expansion_waterstop_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    FloorExpansionWaterstopCallout,
    snap_point,
    parse_floor_expansion_waterstop_callout,
    evaluate_floor_expansion_waterstop_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_floor_expansion_basic():
    text = "ARCHITECTURAL FLOOR EXPANSION JOINT 50MM GAP FLUSH CENTRAL SANTOPRENE SEAL WITH CONTINUOUS EPDM DRAINAGE TROUGH WATERSTOP +/- 25MM MOVEMENT PEDESTRIAN"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["gap_width_mm"] == 50.0
    assert parsed["surface_cover_profile"] == "FLUSH_CENTRAL_SANTOPRENE_SEAL"
    assert parsed["sub_slab_waterstop_type"] == "CONTINUOUS_EPDM_DRAINAGE_TROUGH"
    assert parsed["movement_capacity_mm"] == 25.0
    assert parsed["traffic_duty_rating"] == "PEDESTRIAN_COMMERCIAL"


def test_parse_seismic_carpark_heavy():
    text = "CARPARK EXPANSION JOINT 100MM GAP SERRATED ALUMINIUM COVER PLATE WITH CENTRAL BULB PVC WATERSTOP +/- 50MM MOVEMENT VEHICULAR"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["gap_width_mm"] == 100.0
    assert parsed["surface_cover_profile"] == "ALUMINIUM_SERRATED_COVER_PLATE"
    assert parsed["sub_slab_waterstop_type"] == "CENTRAL_BULB_PVC_WATERSTOP"
    assert parsed["movement_capacity_mm"] == 50.0
    assert parsed["traffic_duty_rating"] == "HEAVY_DUTY_VEHICULAR"


def test_parse_stainless_pan_system():
    text = "LATHAM FLOOR JOINT 25MM GAP STAINLESS STEEL PAN SYSTEM WITH HYDROPHILIC INJECTION HOSE"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["gap_width_mm"] == 25.0
    assert parsed["surface_cover_profile"] == "STAINLESS_STEEL_PAN_PLATE"
    assert parsed["sub_slab_waterstop_type"] == "HYDROPHILIC_INJECTION_HOSE"


def test_parse_unrelated():
    assert parse_floor_expansion_waterstop_callout("ALUMINIUM WINDOW SILL") is None
    assert parse_floor_expansion_waterstop_callout("GYPSUM BOARD CEILING") is None


def test_evaluate_floor_expansion_shadow_single():
    callouts = ["FLOOR EXPANSION JOINT 50MM"]
    positions = [(10.1, 20.2)]
    results = evaluate_floor_expansion_waterstop_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_floor_expansion_shadow_dict():
    items = [{"text": "SEISMIC FLOOR JOINT 75MM", "position": (5.0, 7.6)}]
    results = evaluate_floor_expansion_waterstop_shadow(items)
    assert len(results) == 1
    assert results[0].gap_width_mm == 75.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_floor_expansion_shadow_no_positions():
    results = evaluate_floor_expansion_waterstop_shadow(["UNIFLEX FLOOR JOINT"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_floor_expansion_shadow_safety_cap():
    huge_input = ["FLOOR EXPANSION JOINT"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_floor_expansion_waterstop_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_floor_expansion_waterstop_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "FLOOR EXPANSION JOINT 50MM", "ROOM 101"]
    results = evaluate_floor_expansion_waterstop_shadow(items)
    assert len(results) == 1
    assert results[0].gap_width_mm == 50.0


def test_podium_expansion_joint_trigger():
    text = "PODIUM EXPANSION JOINT 75MM GAP"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["gap_width_mm"] == 75.0


def test_floor_to_floor_trigger():
    text = "FLOOR-TO-FLOOR EXPANSION 50MM"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["gap_width_mm"] == 50.0


def test_default_values():
    text = "FLOOR MOVEMENT JOINT"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["gap_width_mm"] == 50.0
    assert parsed["surface_cover_profile"] == "FLUSH_CENTRAL_SANTOPRENE_SEAL"
    assert parsed["sub_slab_waterstop_type"] == "CONTINUOUS_EPDM_DRAINAGE_TROUGH"
    assert parsed["movement_capacity_mm"] == 25.0
    assert parsed["traffic_duty_rating"] == "PEDESTRIAN_COMMERCIAL"


def test_snapping_precision():
    callouts = ["WATERPROOF EXPANSION JOINT"]
    positions = [(12.49, 13.76)]
    results = evaluate_floor_expansion_waterstop_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_recessed_pan_profile():
    text = "EXPANSION JOINT WATERSTOP WITH RECESSED PAN"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["surface_cover_profile"] == "STAINLESS_STEEL_PAN_PLATE"


def test_forklift_traffic():
    text = "FLOOR EXPANSION JOINT FORKLIFT TRAFFIC"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["traffic_duty_rating"] == "HEAVY_DUTY_VEHICULAR"


def test_plus_minus_movement():
    text = "EXPANSION JOINT +/- 15MM"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["movement_capacity_mm"] == 15.0


def test_invalid_item_types():
    results = evaluate_floor_expansion_waterstop_shadow([123, None, object()])
    assert results == []


def test_rearguard_waterstop_trigger():
    text = "FLOOR EXPANSION JOINT WITH REARGUARD WATERSTOP"
    parsed = parse_floor_expansion_waterstop_callout(text)
    assert parsed is not None
    assert parsed["sub_slab_waterstop_type"] == "CENTRAL_BULB_PVC_WATERSTOP"
