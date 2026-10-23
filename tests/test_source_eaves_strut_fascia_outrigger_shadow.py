import pytest
from pb_source_eaves_strut_fascia_outrigger_shadow import (
    parse_eaves_strut_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_eaves_strut_outrigger_shadow,
    SNAP_TOLERANCE_PT,
)


def test_eaves_strut_callout_parsing():
    c1 = "EAVES STRUT C20019 CLEATED TO PORTAL RAFTER"
    p1 = parse_eaves_strut_callout(c1)
    assert p1 is not None
    assert p1["member_type"] == "EAVES_STRUT"
    assert p1["section_profile"] == "C20019"
    assert p1["connection_type"] == "CLEATED_TO_RAFTER"

    c2 = "FASCIA GIRT OUTRIGGER BRACKET 600MM PROJECTION @ 1200 CTS BOLTED STUB"
    p2 = parse_eaves_strut_callout(c2)
    assert p2 is not None
    assert p2["member_type"] == "OUTRIGGER_BRACKET"
    assert p2["outrigger_length_mm"] == 600.0
    assert p2["outrigger_spacing_mm"] == 1200.0
    assert p2["connection_type"] == "STUB_OUTRIGGER_BOLTED"

    c3 = "FASCIA GIRT Z15015"
    p3 = parse_eaves_strut_callout(c3)
    assert p3 is not None
    assert p3["member_type"] == "FASCIA_GIRT"
    assert p3["section_profile"] == "Z15015"

    c4 = "PLASTERBOARD CEILING LINING"
    assert parse_eaves_strut_callout(c4) is None


def test_eaves_strut_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (25.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (25.0, 0.0)


def test_eaves_strut_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_eaves_strut_evaluation_quantities():
    callouts = [
        "EAVES STRUT C25024",
        "EAVE GUTTER OUTRIGGER 75x50x4 RHS",
    ]
    polylines = [
        [(0.0, 0.0), (200.0, 0.0)],
        [(10.0, 10.0), (10.0, 60.0)],
    ]
    candidates = evaluate_eaves_strut_outrigger_shadow("SHT-STR-S202", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-S202_eso_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].section_profile == "C25024"
    assert candidates[1].member_type == "OUTRIGGER_BRACKET"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 200.0
