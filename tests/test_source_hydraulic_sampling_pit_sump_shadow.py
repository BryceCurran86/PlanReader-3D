import pytest
from pb_source_hydraulic_sampling_pit_sump_shadow import (
    parse_hydraulic_pit_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_hydraulic_pit_shadow,
    SNAP_TOLERANCE_PT,
)


def test_hydraulic_pit_callout_parsing():
    c1 = "PRECAST CONCRETE TRADE WASTE SAMPLING PIT 600X600 WITH GAS-TIGHT COVER 900 DEEP"
    p1 = parse_hydraulic_pit_callout(c1)
    assert p1 is not None
    assert p1["pit_type"] == "SAMPLING_PIT"
    assert p1["pit_dimensions_mm"] == "600X600"
    assert p1["depth_mm"] == 900.0
    assert p1["cover_type"] == "GAS_TIGHT_CLASS_B"
    assert p1["pump_configuration"] == "NONE_GRAVITY_PIT"

    c2 = "DUPLEX SUBMERSIBLE SUMP PUMP PIT 1200 DIA X 1800 DEEP HEAVY DUTY CLASS D COVER"
    p2 = parse_hydraulic_pit_callout(c2)
    assert p2 is not None
    assert p2["pit_type"] == "SUMP_PUMP_PIT"
    assert p2["pit_dimensions_mm"] == "1200 DIA"
    assert p2["depth_mm"] == 1800.0
    assert p2["pump_configuration"] == "DUPLEX_DUTY_STANDBY"
    assert p2["cover_type"] == "HEAVY_DUTY_CLASS_D"

    c3 = "NO SAMPLING PIT REQUIRED AT THIS LOCATION"
    assert parse_hydraulic_pit_callout(c3) is None

    c4 = "PLASTERBOARD CEILING"
    assert parse_hydraulic_pit_callout(c4) is None


def test_hydraulic_pit_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_hydraulic_pit_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_hydraulic_pit_evaluation_quantities():
    callouts = [
        "TRADE WASTE SAMPLING PIT 600X600",
        "SUMP PUMP PIT 900X900",
    ]
    polylines = [
        [(0.0, 0.0), (50.0, 0.0)],
        [(100.0, 100.0)],
    ]
    candidates = evaluate_hydraulic_pit_shadow("SHT-HYD-TW101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-HYD-TW101_hps_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].pit_dimensions_mm == "600X600"
    assert candidates[1].pit_type == "SUMP_PUMP_PIT"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 50.0
