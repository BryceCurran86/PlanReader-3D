import pytest
from pb_source_louver_penthouse_acoustic_shadow import (
    parse_louver_penthouse_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_louver_penthouse_shadow,
    SNAP_TOLERANCE_PT,
)


def test_louver_penthouse_callout_parsing():
    c1 = "ARCHITECTURAL LOUVER PENTHOUSE 3000H 50% FREE AREA WITH BIRD MESH CHEVRON BLADES"
    p1 = parse_louver_penthouse_callout(c1)
    assert p1 is not None
    assert p1["enclosure_type"] == "LOUVER_PENTHOUSE"
    assert p1["blade_type"] == "WEATHERPROOF_CHEVRON"
    assert p1["height_mm"] == 3000.0
    assert p1["free_area_pct"] == 50.0
    assert p1["has_bird_mesh"] is True

    c2 = "ROOFTOP ACOUSTIC SCREEN 2400MM HIGH RW 20 SOUND ATTENUATION"
    p2 = parse_louver_penthouse_callout(c2)
    assert p2 is not None
    assert p2["enclosure_type"] == "ACOUSTIC_SCREEN"
    assert p2["height_mm"] == 2400.0
    assert p2["acoustic_rating"] == "RW 20"

    c3 = "ACOUSTIC ATTENUATION SPLITTER 200MM IN DISCHARGE"
    p3 = parse_louver_penthouse_callout(c3)
    assert p3 is not None
    assert p3["enclosure_type"] == "ATTENUATION_SPLITTER"
    assert p3["blade_type"] == "SOUND_ATTENUATION_SPLITTER"

    c4 = "PLASTER CEILING TILE"
    assert parse_louver_penthouse_callout(c4) is None


def test_louver_penthouse_snapping():
    pt = (12.4, 27.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 27.5)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_louver_penthouse_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_louver_penthouse_evaluation_quantities():
    callouts = [
        "LOUVER PENTHOUSE 2700H",
        "ACOUSTIC SCREEN 3000H",
    ]
    polylines = [
        [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)],
        [(0.0, 50.0), (150.0, 50.0)],
    ]
    candidates = evaluate_louver_penthouse_shadow("SHT-ARCH-A501", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-ARCH-A501_lps_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].height_mm == 2700.0
    assert candidates[1].enclosure_type == "ACOUSTIC_SCREEN"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 200.0
