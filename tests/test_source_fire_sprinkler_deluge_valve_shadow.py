import pytest
from pb_source_fire_sprinkler_deluge_valve_shadow import (
    parse_deluge_valve_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_fire_sprinkler_deluge_valve_shadow,
    SNAP_TOLERANCE_PT,
)


def test_deluge_valve_callout_parsing():
    c1 = "DN150 DOUBLE INTERLOCK PRE-ACTION VALVE STATION WITH ELECTRIC SOLENOID RELEASE 1600 KPA"
    p1 = parse_deluge_valve_callout(c1)
    assert p1 is not None
    assert p1["valve_type"] == "DOUBLE_INTERLOCK_PREACTION"
    assert p1["diameter_dn_mm"] == 150.0
    assert p1["release_type"] == "ELECTRIC_SOLENOID"
    assert p1["rated_pressure_kpa"] == 1600.0
    assert p1["has_accelerator"] is False

    c2 = "DN100 DELUGE VALVE WITH PNEUMATIC AIR PILOT TRIM AND QUICK OPENING ACCELERATOR"
    p2 = parse_deluge_valve_callout(c2)
    assert p2 is not None
    assert p2["valve_type"] == "DELUGE_VALVE"
    assert p2["diameter_dn_mm"] == 100.0
    assert p2["release_type"] == "PNEUMATIC_PILOT"
    assert p2["has_accelerator"] is True

    c3 = "SINGLE INTERLOCK PREACTION VALVE DN80"
    p3 = parse_deluge_valve_callout(c3)
    assert p3 is not None
    assert p3["valve_type"] == "SINGLE_INTERLOCK_PREACTION"
    assert p3["diameter_dn_mm"] == 80.0

    c4 = "PLASTER FINISH WALL"
    assert parse_deluge_valve_callout(c4) is None


def test_deluge_valve_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_deluge_valve_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_deluge_valve_evaluation_quantities():
    callouts = [
        "DN150 DOUBLE INTERLOCK PRE-ACTION VALVE",
        "DN100 DELUGE VALVE",
    ]
    polylines = [
        [(0.0, 0.0), (100.0, 0.0)],
        [(50.0, 50.0)],
    ]
    candidates = evaluate_fire_sprinkler_deluge_valve_shadow("SHT-FIRE-FP101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-FIRE-FP101_fdv_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].diameter_dn_mm == 150.0
    assert candidates[1].valve_type == "DELUGE_VALVE"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 100.0
