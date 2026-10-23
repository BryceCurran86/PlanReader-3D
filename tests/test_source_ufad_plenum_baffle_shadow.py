import pytest
from pb_source_ufad_plenum_baffle_shadow import (
    parse_ufad_baffle_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_ufad_plenum_baffle_shadow,
    SNAP_TOLERANCE_PT,
)


def test_ufad_baffle_callout_parsing():
    c1 = "GALVANIZED STEEL UFAD PLENUM AIR BAFFLE 300H WITH NEOPRENE GASKET 25 PA"
    p1 = parse_ufad_baffle_callout(c1)
    assert p1 is not None
    assert p1["baffle_type"] == "AIR_PRESSURE_BAFFLE"
    assert p1["material"] == "GALVANIZED_SHEET_STEEL"
    assert p1["height_mm"] == 300.0
    assert p1["gasket_seal"] == "NEOPRENE_FOAM"
    assert p1["differential_pressure_pa"] == 25.0

    c2 = "UNDERFLOOR ACOUSTIC PLENUM BARRIER MINERAL FIBRE 450MM HIGH WITH ACOUSTIC SEAL"
    p2 = parse_ufad_baffle_callout(c2)
    assert p2 is not None
    assert p2["baffle_type"] == "ACOUSTIC_PLENUM_BARRIER"
    assert p2["material"] == "MINERAL_FIBRE_BOARD"
    assert p2["height_mm"] == 450.0
    assert p2["gasket_seal"] == "ACOUSTIC_SEALANT"

    c3 = "SUBFLOOR AIR BARRIER FIRE SMOKE STOP CALCIUM SILICATE INTUMESCENT"
    p3 = parse_ufad_baffle_callout(c3)
    assert p3 is not None
    assert p3["baffle_type"] == "FIRE_SMOKE_STOP"
    assert p3["material"] == "CALCIUM_SILICATE"
    assert p3["gasket_seal"] == "INTUMESCENT_MASTIC"

    c4 = "CARPET TILE FINISH"
    assert parse_ufad_baffle_callout(c4) is None


def test_ufad_baffle_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_ufad_baffle_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_ufad_baffle_evaluation_quantities():
    callouts = [
        "UFAD PLENUM BAFFLE 300H",
        "UNDERFLOOR AIR BAFFLE 450H",
    ]
    polylines = [
        [(0.0, 0.0), (150.0, 0.0)],
        [(0.0, 50.0), (200.0, 50.0)],
    ]
    candidates = evaluate_ufad_plenum_baffle_shadow("SHT-MECH-M301", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-MECH-M301_upb_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].height_mm == 300.0
    assert candidates[1].height_mm == 450.0

    d = candidates[0].to_dict()
    assert d["length_pt"] == 150.0
