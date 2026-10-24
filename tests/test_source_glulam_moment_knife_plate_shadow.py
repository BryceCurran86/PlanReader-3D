import pytest
from pb_source_glulam_moment_knife_plate_shadow import (
    parse_glulam_connection_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_glulam_moment_knife_plate_shadow,
    SNAP_TOLERANCE_PT,
)


def test_glulam_connection_callout_parsing():
    c1 = "GLULAM BEAM 200X600 GL18 WITH CONCEALED 16MM KNIFE PLATE AND 12MM DOWEL PINS (8 DOWELS)"
    p1 = parse_glulam_connection_callout(c1)
    assert p1 is not None
    assert p1["connection_type"] == "CONCEALED_KNIFE_PLATE"
    assert p1["timber_grade"] == "GL18"
    assert p1["timber_width_mm"] == 200.0
    assert p1["timber_depth_mm"] == 600.0
    assert p1["knife_plate_thickness_mm"] == 16.0
    assert p1["dowel_diameter_mm"] == 12.0
    assert p1["dowel_count"] == 8

    c2 = "DOUBLE INTERNAL FLITCH PLATE 12MM STEEL PL MOMENT SPLICE GL17"
    p2 = parse_glulam_connection_callout(c2)
    assert p2 is not None
    assert p2["connection_type"] == "DOUBLE_INTERNAL_FLITCH"
    assert p2["knife_plate_thickness_mm"] == 12.0
    assert p2["timber_grade"] == "GL17"

    c3 = "MASS TIMBER PINNED CONNECTION 16MM DOWELS"
    p3 = parse_glulam_connection_callout(c3)
    assert p3 is not None
    assert p3["connection_type"] == "BEAM_TO_COLUMN_PINNED"
    assert p3["dowel_diameter_mm"] == 16.0

    c4 = "PLASTER FINISH WALL"
    assert parse_glulam_connection_callout(c4) is None


def test_glulam_connection_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_glulam_connection_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_glulam_connection_evaluation_quantities():
    callouts = [
        "GLULAM BEAM 200X600 WITH KNIFE PLATE",
        "MOMENT SPLICE 16MM FLITCH PLATE",
    ]
    polylines = [
        [(0.0, 0.0), (250.0, 0.0)],
        [(100.0, 0.0)],
    ]
    candidates = evaluate_glulam_moment_knife_plate_shadow("SHT-TIM-T101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-TIM-T101_gkc_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].timber_width_mm == 200.0
    assert candidates[1].knife_plate_thickness_mm == 16.0

    d = candidates[0].to_dict()
    assert d["length_pt"] == 250.0
