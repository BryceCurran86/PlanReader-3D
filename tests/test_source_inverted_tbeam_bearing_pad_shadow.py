import pytest
from pb_source_inverted_tbeam_bearing_pad_shadow import (
    parse_inverted_tbeam_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_inverted_tbeam_shadow,
    SNAP_TOLERANCE_PT,
)


def test_inverted_tbeam_callout_parsing():
    c1 = "PRECAST INVERTED T-BEAM 600W X 900D WITH 150MM LEDGE CONTINUOUS 10MM ELASTOMERIC BEARING STRIP 60 DUROMETER"
    p1 = parse_inverted_tbeam_callout(c1)
    assert p1 is not None
    assert p1["beam_type"] == "INVERTED_T_BEAM"
    assert p1["web_width_mm"] == 600.0
    assert p1["overall_depth_mm"] == 900.0
    assert p1["ledge_width_mm"] == 150.0
    assert p1["bearing_pad_material"] == "CHLOROPRENE_NEOPRENE"
    assert p1["bearing_pad_thickness_mm"] == 10.0
    assert p1["durometer_hardness"] == 60

    c2 = "L-SHAPED LEDGER BEAM 450W X 750D LEDGE: 200MM WITH PTFE SLIDE PAD"
    p2 = parse_inverted_tbeam_callout(c2)
    assert p2 is not None
    assert p2["beam_type"] == "L_SHAPED_LEDGER_BEAM"
    assert p2["web_width_mm"] == 450.0
    assert p2["overall_depth_mm"] == 750.0
    assert p2["ledge_width_mm"] == 200.0
    assert p2["bearing_pad_material"] == "PTFE_SLIDE_PAD"

    c3 = "REINFORCED ELASTOMERIC BEARING PAD 20MM THICK"
    p3 = parse_inverted_tbeam_callout(c3)
    assert p3 is not None
    assert p3["bearing_pad_material"] == "REINFORCED_ELASTOMERIC"

    c4 = "CURTAIN TRACK FIXING"
    assert parse_inverted_tbeam_callout(c4) is None


def test_inverted_tbeam_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_inverted_tbeam_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_inverted_tbeam_evaluation_quantities():
    callouts = [
        "INVERTED T-BEAM 600X900",
        "LEDGER BEAM 450X750",
    ]
    polylines = [
        [(0.0, 0.0), (250.0, 0.0)],
        [(0.0, 50.0), (250.0, 50.0)],
    ]
    candidates = evaluate_inverted_tbeam_shadow("SHT-STR-S203", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-S203_itb_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].web_width_mm == 600.0
    assert candidates[0].overall_depth_mm == 900.0
    assert candidates[1].beam_type == "L_SHAPED_LEDGER_BEAM"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 250.0
