import pytest
from pb_source_terrazzo_divider_strip_shadow import (
    parse_terrazzo_strip_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_terrazzo_divider_strip_shadow,
    SNAP_TOLERANCE_PT,
)


def test_terrazzo_strip_callout_parsing():
    c1 = "3MM BRASS ANGLE TERRAZZO DIVIDER STRIP 12MM HIGH AT 1200X1200 GRID"
    p1 = parse_terrazzo_strip_callout(c1)
    assert p1 is not None
    assert p1["strip_type"] == "DIVIDER_STRIP"
    assert p1["strip_material"] == "BRASS"
    assert p1["strip_width_mm"] == 3.0
    assert p1["strip_height_mm"] == 12.0
    assert p1["grid_module_mm"] == "1200X1200"

    c2 = "10MM NEOPRENE MOVEMENT JOINT IN TERRAZZO OVER SLAB EXPANSION JOINT"
    p2 = parse_terrazzo_strip_callout(c2)
    assert p2 is not None
    assert p2["strip_type"] == "MOVEMENT_JOINT"
    assert p2["strip_material"] == "NEOPRENE_COMPOSITE"
    assert p2["strip_width_mm"] == 10.0

    c3 = "6MM ZINC STRIP TRANSITION AT DOORWAY"
    p3 = parse_terrazzo_strip_callout(c3)
    assert p3 is not None
    assert p3["strip_type"] == "TRANSITION_STRIP"
    assert p3["strip_material"] == "ZINC"
    assert p3["strip_width_mm"] == 6.0

    c4 = "PLASTER FINISH WALL"
    assert parse_terrazzo_strip_callout(c4) is None


def test_terrazzo_strip_snapping():
    pt = (12.2, 24.9)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_terrazzo_strip_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_terrazzo_strip_evaluation_quantities():
    callouts = [
        "TERRAZZO DIVIDER STRIP 3MM BRASS",
        "10MM TERRAZZO MOVEMENT JOINT",
    ]
    polylines = [
        [(0.0, 0.0), (200.0, 0.0)],
        [(0.0, 50.0), (200.0, 50.0)],
    ]
    candidates = evaluate_terrazzo_divider_strip_shadow("SHT-FIN-F201", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-FIN-F201_tds_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].strip_material == "BRASS"
    assert candidates[1].strip_type == "MOVEMENT_JOINT"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 200.0
