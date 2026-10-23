import pytest
from pb_source_pt_anchorage_pocket_grout_vent_shadow import (
    parse_pt_anchorage_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_pt_anchorage_pocket_shadow,
    SNAP_TOLERANCE_PT,
)


def test_pt_anchorage_callout_parsing():
    c1 = "4-STRAND LIVE END PT ANCHORAGE IN 100MM RECESSED POCKET 12.7MM STRAND"
    p1 = parse_pt_anchorage_callout(c1)
    assert p1 is not None
    assert p1["anchorage_type"] == "LIVE_END_STRESSING"
    assert p1["strand_count"] == 4
    assert p1["strand_diameter_mm"] == 12.7
    assert p1["pocket_recess_mm"] == 100.0

    c2 = "HIGH-POINT GROUT VENT TUBE TO TOP OF SLAB"
    p2 = parse_pt_anchorage_callout(c2)
    assert p2 is not None
    assert p2["anchorage_type"] == "GROUT_VENT_POINT"
    assert p2["grout_vent_type"] == "HIGH_POINT_VENT"

    c3 = "5-STRAND DEAD END FIXED PT ANCHORAGE 15.2MM"
    p3 = parse_pt_anchorage_callout(c3)
    assert p3 is not None
    assert p3["anchorage_type"] == "DEAD_END_FIXED"
    assert p3["strand_count"] == 5
    assert p3["strand_diameter_mm"] == 15.2

    c4 = "TIMBER STUD WALL"
    assert parse_pt_anchorage_callout(c4) is None


def test_pt_anchorage_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_pt_anchorage_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_pt_anchorage_evaluation_quantities():
    callouts = [
        "4-STRAND PT ANCHORAGE",
        "HIGH-POINT GROUT VENT",
    ]
    polylines = [
        [(0.0, 0.0), (100.0, 0.0)],
        [(50.0, 50.0)],
    ]
    candidates = evaluate_pt_anchorage_pocket_shadow("SHT-STR-PT101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-PT101_ptp_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].strand_count == 4
    assert candidates[1].anchorage_type == "GROUT_VENT_POINT"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 100.0
