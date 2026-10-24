import pytest
from pb_source_syphonic_roof_drainage_shadow import (
    parse_syphonic_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_syphonic_drainage_shadow,
    SNAP_TOLERANCE_PT,
)


def test_syphonic_callout_parsing():
    c1 = "SYPHONIC ROOF OUTLET BOWL DN75 WITH ANTI-VORTEX AIR BAFFLE AND DOME GRATE"
    p1 = parse_syphonic_callout(c1)
    assert p1 is not None
    assert p1["component_type"] == "ROOF_OUTLET_BOWL"
    assert p1["diameter_dn_mm"] == 75.0
    assert p1["has_air_baffle"] is True
    assert p1["leaf_guard_type"] == "DOME_GRATE"
    assert p1["pipe_material"] == "HDPE"

    c2 = "HDPE SYPHONIC TAILPIPE DN110 TO HORIZONTAL COLLECTOR"
    p2 = parse_syphonic_callout(c2)
    assert p2 is not None
    assert p2["component_type"] == "TAILPIPE"
    assert p2["diameter_dn_mm"] == 110.0
    assert p2["pipe_material"] == "HDPE"

    c3 = "SYPHONIC OVERFLOW OUTLET DN160 STAINLESS STEEL FLAT GRATE"
    p3 = parse_syphonic_callout(c3)
    assert p3 is not None
    assert p3["component_type"] == "OVERFLOW_OUTLET"
    assert p3["diameter_dn_mm"] == 160.0
    assert p3["pipe_material"] == "STAINLESS_STEEL"
    assert p3["leaf_guard_type"] == "FLAT_GRATE"

    c4 = "TIMBER SKIRTING BOARD"
    assert parse_syphonic_callout(c4) is None


def test_syphonic_snapping():
    pt = (15.2, 30.1)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (15.0, 30.0)

    line = [(0.0, 0.0), (0.1, 0.2), (50.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (50.0, 0.0)


def test_syphonic_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_syphonic_evaluation_quantities():
    callouts = [
        "SYPHONIC BOWL DN75",
        "HDPE COLLECTOR PIPE DN160",
    ]
    polylines = [
        [(10.0, 10.0)],
        [(0.0, 0.0), (300.0, 0.0)],
    ]
    candidates = evaluate_syphonic_drainage_shadow("SHT-HYD-H101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-HYD-H101_srd_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].diameter_dn_mm == 75.0
    assert candidates[1].component_type == "HORIZONTAL_COLLECTOR"

    d = candidates[1].to_dict()
    assert d["length_pt"] == 300.0
