import pytest
from pb_source_precast_splice_shoe_sleeve_shadow import (
    parse_wall_splice_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_precast_splice_shoe_sleeve_shadow,
    SNAP_TOLERANCE_PT,
)


def test_wall_splice_callout_parsing():
    c1 = "PRECAST WALL SPLICE SHOE WITH M30 ANCHOR BOLTS 150MM RECESS 80MPA GROUT"
    p1 = parse_wall_splice_callout(c1)
    assert p1 is not None
    assert p1["splice_type"] == "BOLTED_WALL_SHOE"
    assert p1["bolt_diameter"] == "M30"
    assert p1["shoe_recess_mm"] == 150.0
    assert p1["grout_strength_mpa"] == 80.0

    c2 = "NMB GROUTED SPLICE SLEEVE FOR N32 VERTICAL BARS 100 MPA GROUT"
    p2 = parse_wall_splice_callout(c2)
    assert p2 is not None
    assert p2["splice_type"] == "GROUTED_SPLICE_SLEEVE"
    assert p2["bar_size"] == "N32"
    assert p2["grout_strength_mpa"] == 100.0

    c3 = "REBAR SPLICE SLEEVE FOR N28 BAR"
    p3 = parse_wall_splice_callout(c3)
    assert p3 is not None
    assert p3["splice_type"] == "GROUTED_SPLICE_SLEEVE"
    assert p3["bar_size"] == "N28"

    c4 = "PLASTERBOARD PARTITION"
    assert parse_wall_splice_callout(c4) is None


def test_wall_splice_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_wall_splice_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_wall_splice_evaluation_quantities():
    callouts = [
        "SPLICE SHOE M24",
        "NMB SPLICE SLEEVE N36",
    ]
    polylines = [
        [(0.0, 0.0), (50.0, 0.0)],
        [(100.0, 100.0)],
    ]
    candidates = evaluate_precast_splice_shoe_sleeve_shadow("SHT-STR-CW101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-CW101_pss_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].bolt_diameter == "M24"
    assert candidates[1].bar_size == "N36"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 50.0
