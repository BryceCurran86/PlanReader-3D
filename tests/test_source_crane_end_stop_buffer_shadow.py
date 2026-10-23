import pytest
from pb_source_crane_end_stop_buffer_shadow import (
    parse_crane_end_stop_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_crane_end_stop_shadow,
    SNAP_TOLERANCE_PT,
)


def test_crane_end_stop_callout_parsing():
    c1 = "CRANE RUNWAY END STOP WITH POLYURETHANE BUFFER Ø160MM FOR 20T CRANE 25MM THICK PLATE"
    p1 = parse_crane_end_stop_callout(c1)
    assert p1 is not None
    assert p1["stop_type"] == "RUNWAY_TRAVEL_STOP"
    assert p1["buffer_type"] == "POLYURETHANE_CELLULAR"
    assert p1["crane_capacity_tonnes"] == 20.0
    assert p1["plate_thickness_mm"] == 25.0
    assert p1["buffer_diameter_mm"] == 160.0

    c2 = "WELDED RUNWAY END STOP 20MM THICK END PLATE WITH HYDRAULIC BUFFER FOR 10 TONNE CRANE"
    p2 = parse_crane_end_stop_callout(c2)
    assert p2 is not None
    assert p2["stop_type"] == "WELDED_END_STOP"
    assert p2["buffer_type"] == "HYDRAULIC"
    assert p2["plate_thickness_mm"] == 20.0
    assert p2["crane_capacity_tonnes"] == 10.0

    c3 = "BOLTED TRAVEL STOP WITH SPRING BUFFER"
    p3 = parse_crane_end_stop_callout(c3)
    assert p3 is not None
    assert p3["stop_type"] == "BOLTED_END_STOP"
    assert p3["buffer_type"] == "COIL_SPRING"

    c4 = "STRUCTURAL COLUMN BASE PLATE"
    assert parse_crane_end_stop_callout(c4) is None


def test_crane_end_stop_snapping():
    pt = (12.3, 27.7)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 27.5)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_crane_end_stop_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_crane_end_stop_evaluation_quantities():
    callouts = [
        "CRANE RUNWAY END STOP 25MM PLATE",
        "RUNWAY STOP BRACKET WITH BUFFER",
    ]
    polylines = [
        [(0.0, 0.0), (50.0, 0.0)],
        [(100.0, 100.0)],
    ]
    candidates = evaluate_crane_end_stop_shadow("SHT-STR-S301", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-S301_ces_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].plate_thickness_mm == 25.0
    assert candidates[1].buffer_type == "POLYURETHANE_CELLULAR"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 50.0
