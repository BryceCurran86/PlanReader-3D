import pytest
from pb_source_steel_cross_bracing_gusset_shadow import (
    parse_steel_gusset_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_steel_cross_bracing_gusset_shadow,
    SNAP_TOLERANCE_PT,
)


def test_steel_gusset_callout_parsing():
    c1 = "20MM THICK STEEL GUSSET PLATE WITH 6XM24 8.8/S BOLTS AND EDGE STIFFENER"
    p1 = parse_steel_gusset_callout(c1)
    assert p1 is not None
    assert p1["gusset_type"] == "CORNER_BEAM_COLUMN_GUSSET"
    assert p1["plate_thickness_mm"] == 20.0
    assert p1["bolt_count"] == 6
    assert p1["bolt_spec"] == "M248.8/S"
    assert p1["has_edge_stiffener"] is True
    assert p1["has_slotted_holes"] is False

    c2 = "TENSION CROSS-BRACING GUSSET 16MM PL WITH SLOTTED HOLES 4XM20"
    p2 = parse_steel_gusset_callout(c2)
    assert p2 is not None
    assert p2["plate_thickness_mm"] == 16.0
    assert p2["has_slotted_holes"] is True
    assert p2["bolt_count"] == 4

    c3 = "CHEVRON V-BRACE GUSSET 25MM PLATE WITH PINNED HOLE"
    p3 = parse_steel_gusset_callout(c3)
    assert p3 is not None
    assert p3["gusset_type"] == "CHEVRON_V_BRACE_GUSSET"
    assert p3["plate_thickness_mm"] == 25.0

    c4 = "PLASTERBOARD PARTITION"
    assert parse_steel_gusset_callout(c4) is None


def test_steel_gusset_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_steel_gusset_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_steel_gusset_evaluation_quantities():
    callouts = [
        "GUSSET PLATE 20MM PL",
        "BRACING GUSSET 16MM PL",
    ]
    polylines = [
        [(0.0, 0.0), (60.0, 0.0), (60.0, 60.0)],
        [(100.0, 100.0)],
    ]
    candidates = evaluate_steel_cross_bracing_gusset_shadow("SHT-STR-S205", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-S205_cbg_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].plate_thickness_mm == 20.0
    assert candidates[1].plate_thickness_mm == 16.0

    d = candidates[0].to_dict()
    assert d["length_pt"] == 120.0
