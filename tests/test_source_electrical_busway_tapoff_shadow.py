import pytest
from pb_source_electrical_busway_tapoff_shadow import (
    parse_busway_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_electrical_busway_shadow,
    SNAP_TOLERANCE_PT,
)


def test_busway_callout_parsing():
    c1 = "1600A COPPER SANDWICH BUSWAY TRUNKING 4P IP65"
    p1 = parse_busway_callout(c1)
    assert p1 is not None
    assert p1["system_type"] == "PLUG_IN_BUSWAY"
    assert p1["rating_amperes"] == 1600.0
    assert p1["conductor_material"] == "COPPER"
    assert p1["poles_count"] == "4P"
    assert p1["enclosure_ip_rating"] == "IP65"

    c2 = "250A 4P PLUG-IN TAP-OFF UNIT WITH MCCB"
    p2 = parse_busway_callout(c2)
    assert p2 is not None
    assert p2["system_type"] == "TAP_OFF_UNIT"
    assert p2["rating_amperes"] == 250.0

    c3 = "2500A FEEDER BUSDUCT ALUMINIUM 3P IP54"
    p3 = parse_busway_callout(c3)
    assert p3 is not None
    assert p3["system_type"] == "FEEDER_BUSWAY"
    assert p3["rating_amperes"] == 2500.0
    assert p3["conductor_material"] == "ALUMINIUM"
    assert p3["poles_count"] == "3P"

    c4 = "STRUCTURAL EXPANSION JOINT IN SLAB"
    assert parse_busway_callout(c4) is None


def test_busway_snapping():
    pt = (14.8, 29.9)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (15.0, 30.0)

    line = [(0.0, 0.0), (0.2, 0.1), (40.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (40.0, 0.0)


def test_busway_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_busway_evaluation_quantities():
    callouts = [
        "1000A BUSWAY RUN",
        "TAP-OFF UNIT 400A",
    ]
    polylines = [
        [(0.0, 0.0), (250.0, 0.0)],
        [(100.0, 0.0)],
    ]
    candidates = evaluate_electrical_busway_shadow("SHT-ELEC-E201", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-ELEC-E201_ebt_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].rating_amperes == 1000.0
    assert candidates[1].system_type == "TAP_OFF_UNIT"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 250.0
