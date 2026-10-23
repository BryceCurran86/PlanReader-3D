import pytest
from pb_source_operable_wall_stacking_pocket_shadow import (
    parse_operable_wall_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_operable_wall_shadow,
    SNAP_TOLERANCE_PT,
)


def test_operable_wall_callout_parsing():
    c1 = "ACOUSTIC OPERABLE WALL RW 50 3200H OVERHEAD HEAVY-DUTY TRACK WITH PARALLEL STACKING POCKET"
    p1 = parse_operable_wall_callout(c1)
    assert p1 is not None
    assert p1["partition_type"] == "ACOUSTIC_OPERABLE_WALL"
    assert p1["acoustic_rating_rw"] == "RW 50"
    assert p1["height_mm"] == 3200.0
    assert p1["stacking_type"] == "PARALLEL_STACKING_POCKET"
    assert p1["seal_type"] == "EXPANDING_MECHANICAL_SEAL"

    c2 = "GLASS MOVABLE WALL 2700MM HIGH WITH REMOTE STACKING BAY"
    p2 = parse_operable_wall_callout(c2)
    assert p2 is not None
    assert p2["partition_type"] == "GLASS_MOVABLE_WALL"
    assert p2["height_mm"] == 2700.0
    assert p2["stacking_type"] == "REMOTE_STACKING_BAY"

    c3 = "OPERABLE PARTITION WITH PERPENDICULAR STACKING AND SWEEP SEALS"
    p3 = parse_operable_wall_callout(c3)
    assert p3 is not None
    assert p3["stacking_type"] == "PERPENDICULAR_STACKING"
    assert p3["seal_type"] == "SWEEP_SEALS"

    c4 = "PLASTERBOARD STUD WALL"
    assert parse_operable_wall_callout(c4) is None


def test_operable_wall_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_operable_wall_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_operable_wall_evaluation_quantities():
    callouts = [
        "OPERABLE WALL 3000H",
        "MOVABLE PARTITION RW 45",
    ]
    polylines = [
        [(0.0, 0.0), (200.0, 0.0)],
        [(0.0, 50.0), (150.0, 50.0)],
    ]
    candidates = evaluate_operable_wall_shadow("SHT-ARCH-A205", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-ARCH-A205_opw_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].height_mm == 3000.0
    assert candidates[1].acoustic_rating_rw == "RW 45"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 200.0
