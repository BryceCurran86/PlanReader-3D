import pytest
from pb_source_sectional_door_track_shadow import (
    parse_sectional_door_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_sectional_door_track_shadow,
    SNAP_TOLERANCE_PT,
)


def test_sectional_door_callout_parsing():
    c1 = "SECTIONAL OVERHEAD DOOR 4500W x 5000H HIGH-LIFT (1800MM LIFT) 3-INCH TRACK TORSION SPRING"
    p1 = parse_sectional_door_callout(c1)
    assert p1 is not None
    assert p1["lift_type"] == "HIGH_LIFT"
    assert p1["door_width_mm"] == 4500.0
    assert p1["door_height_mm"] == 5000.0
    assert p1["lift_height_mm"] == 1800.0
    assert p1["track_profile"] == "75MM (3-INCH)"
    assert p1["counterweight_type"] == "TORSION_SPRING"

    c2 = "VERTICAL LIFT DOOR 3000 x 3000 WITH COUNTERWEIGHT DRUM BOX"
    p2 = parse_sectional_door_callout(c2)
    assert p2 is not None
    assert p2["lift_type"] == "VERTICAL_LIFT"
    assert p2["door_width_mm"] == 3000.0
    assert p2["door_height_mm"] == 3000.0
    assert p2["counterweight_type"] == "COUNTERWEIGHT_DRUM"

    c3 = "UNRELATED CEILING TILE"
    assert parse_sectional_door_callout(c3) is None


def test_sectional_door_snapping():
    pt = (10.2, 19.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (10.0, 20.0)

    line = [(0.0, 0.0), (0.2, 0.1), (10.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (10.0, 0.0)


def test_sectional_door_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_sectional_door_evaluation_quantities():
    callouts = [
        "OVERHEAD SECTIONAL DOOR 3600W X 4200H STANDARD LIFT",
        "HIGH-LIFT DOOR TRACK 2400W X 3000H LIFT: 1200MM",
    ]
    polylines = [
        [(0.0, 0.0), (100.0, 0.0)],
        [(50.0, 50.0), (50.0, 150.0)],
    ]
    candidates = evaluate_sectional_door_track_shadow("SHT-ARCH-A201", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-ARCH-A201_sdt_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[1].lift_type == "HIGH_LIFT"
    assert candidates[1].lift_height_mm == 1200.0

    d = candidates[0].to_dict()
    assert d["track_length_pt"] == 100.0
