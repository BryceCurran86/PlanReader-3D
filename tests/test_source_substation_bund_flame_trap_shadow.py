import pytest
from pb_source_substation_bund_flame_trap_shadow import (
    parse_substation_bund_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_substation_bund_shadow,
    SNAP_TOLERANCE_PT,
)


def test_substation_bund_callout_parsing():
    c1 = "REINFORCED CONCRETE TRANSFORMER OIL BUND 1200H 250MM THICK WALL 40 M3 WITH CRUSHED BASALT FLAME TRAP"
    p1 = parse_substation_bund_callout(c1)
    assert p1 is not None
    assert p1["bund_type"] == "TRANSFORMER_OIL_BUND"
    assert p1["wall_height_mm"] == 1200.0
    assert p1["wall_thickness_mm"] == 250.0
    assert p1["containment_volume_m3"] == 40.0
    assert p1["flame_trap_aggregate"] == "CRUSHED_BASALT"
    assert p1["has_flame_trap"] is True

    c2 = "SUBSTATION OIL-WATER SEPARATOR SUMP WITH FLAME TRAP"
    p2 = parse_substation_bund_callout(c2)
    assert p2 is not None
    assert p2["bund_type"] == "OIL_WATER_SEPARATOR_SUMP"
    assert p2["has_flame_trap"] is True

    c3 = "FLAME TRAP BASIN WITH CRUSHED GRANITE"
    p3 = parse_substation_bund_callout(c3)
    assert p3 is not None
    assert p3["bund_type"] == "FLAME_TRAP_BASIN"
    assert p3["flame_trap_aggregate"] == "CRUSHED_GRANITE"

    c4 = "CARPET FINISH ROOM"
    assert parse_substation_bund_callout(c4) is None


def test_substation_bund_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_substation_bund_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_substation_bund_evaluation_quantities():
    callouts = [
        "TRANSFORMER BUND 1200H",
        "OIL-WATER SEPARATOR SUMP",
    ]
    polylines = [
        [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)],
        [(50.0, 50.0)],
    ]
    candidates = evaluate_substation_bund_shadow("SHT-ELEC-SUB101", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-ELEC-SUB101_sob_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].wall_height_mm == 1200.0
    assert candidates[1].bund_type == "OIL_WATER_SEPARATOR_SUMP"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 200.0
