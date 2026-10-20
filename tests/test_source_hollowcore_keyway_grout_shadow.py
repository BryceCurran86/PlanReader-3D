import pytest
from pb_source_hollowcore_keyway_grout_shadow import (
    parse_hollowcore_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_hollowcore_keyway_shadow,
    SNAP_TOLERANCE_PT,
)


def test_hollowcore_callout_parsing():
    c1 = "200MM HOLLOWCORE SLAB WITH 40 MPA GROUTED SHEAR KEYWAYS AND N12 TIES"
    p1 = parse_hollowcore_callout(c1)
    assert p1 is not None
    assert p1["slab_depth_mm"] == 200.0
    assert p1["plank_width_mm"] == 1200.0
    assert p1["grout_strength_mpa"] == 40.0
    assert p1["tie_bar_spec"] == "N12"
    assert p1["has_structural_topping"] is False

    c2 = "1200MM WIDE HOLLOWCORE PLANK 250 THICK WITH 75MM TOPPING"
    p2 = parse_hollowcore_callout(c2)
    assert p2 is not None
    assert p2["slab_depth_mm"] == 250.0
    assert p2["plank_width_mm"] == 1200.0
    assert p2["has_structural_topping"] is True
    assert p2["topping_thickness_mm"] == 75.0

    c3 = "LONGITUDINAL KEYWAY GROUT 50 MPA"
    p3 = parse_hollowcore_callout(c3)
    assert p3 is not None
    assert p3["grout_strength_mpa"] == 50.0

    c4 = "PLASTERBOARD PARTITION WALL"
    assert parse_hollowcore_callout(c4) is None


def test_hollowcore_snapping():
    pt = (12.4, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (40.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (40.0, 0.0)


def test_hollowcore_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_hollowcore_evaluation_quantities():
    callouts = [
        "200MM HOLLOWCORE SLAB",
        "PRECAST SLAB KEYWAY N16 TIE",
    ]
    polylines = [
        [(0.0, 0.0), (300.0, 0.0)],
        [(0.0, 50.0), (300.0, 50.0)],
    ]
    candidates = evaluate_hollowcore_keyway_shadow("SHT-STR-S105", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-S105_hck_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].slab_depth_mm == 200.0
    assert candidates[1].tie_bar_spec == "N16"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 300.0
