import pytest
from pb_source_precast_facade_fin_sunshade_shadow import (
    parse_facade_fin_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_facade_fin_sunshade_shadow,
    SNAP_TOLERANCE_PT,
)


def test_facade_fin_callout_parsing():
    c1 = "PRECAST CONCRETE VERTICAL FEATURE FIN 150W X 450D @ 900 CTS"
    p1 = parse_facade_fin_callout(c1)
    assert p1 is not None
    assert p1["fin_type"] == "VERTICAL_FIN"
    assert p1["material"] == "PRECAST_CONCRETE"
    assert p1["fin_width_mm"] == 150.0
    assert p1["fin_depth_mm"] == 450.0
    assert p1["fin_spacing_mm"] == 900.0

    c2 = "ALUMINIUM SUNSHADE LOUVER 300MM AEROFOIL 45 DEG TILT"
    p2 = parse_facade_fin_callout(c2)
    assert p2 is not None
    assert p2["fin_type"] == "AEROFOIL_LOUVER"
    assert p2["material"] == "EXTRUDED_ALUMINIUM"
    assert p2["fin_depth_mm"] == 300.0
    assert p2["blade_angle_deg"] == 45.0

    c3 = "UHPC HORIZONTAL SUNSHADE BLADE 100 x 600"
    p3 = parse_facade_fin_callout(c3)
    assert p3 is not None
    assert p3["fin_type"] == "HORIZONTAL_SUNSHADE"
    assert p3["material"] == "UHPC"
    assert p3["fin_width_mm"] == 100.0
    assert p3["fin_depth_mm"] == 600.0

    c4 = "PAINT FINISH TO CEILING"
    assert parse_facade_fin_callout(c4) is None


def test_facade_fin_snapping():
    pt = (12.4, 27.6)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 27.5)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_facade_fin_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_facade_fin_evaluation_quantities():
    callouts = [
        "VERTICAL FEATURE FIN 200W X 500D",
        "ARCHITECTURAL FIN 150X300",
    ]
    polylines = [
        [(0.0, 0.0), (0.0, 150.0)],
        [(50.0, 0.0), (50.0, 200.0)],
    ]
    candidates = evaluate_facade_fin_sunshade_shadow("SHT-FAC-F101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-FAC-F101_ffs_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].fin_width_mm == 200.0
    assert candidates[0].fin_depth_mm == 500.0

    d = candidates[0].to_dict()
    assert d["length_pt"] == 150.0
