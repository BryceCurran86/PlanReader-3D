"""Unit tests for Source Geotechnical Screw Pier & Helical Anchor Shadow Authority."""

import pytest
from pb_source_screw_pier_helical_anchor_shadow import (
    ScrewPierCandidate,
    snap_point,
    parse_screw_pier_callout,
    evaluate_screw_pier_helical_anchor_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((12.4, 14.9)) == (12.5, 15.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_screw_pier_callout_double_helix_pipe():
    text = "SCREW PIER 89MM CHS 250/300 DOUBLE HELIX 150 KN CAPACITY MIN 6.0M DEPTH 15 KNM TORQUE"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["shaft_type"] == "PIPE_SHAFT_CHS"
    assert parsed["shaft_diameter_mm"] == 89.0
    assert parsed["helix_configuration"] == "DOUBLE_HELIX"
    assert parsed["helix_diameters_mm"] == [250.0, 300.0]
    assert parsed["working_capacity_kn"] == 150.0
    assert parsed["minimum_depth_m"] == 6.0
    assert parsed["target_torque_knm"] == 15.0


def test_parse_screw_pier_callout_triple_helix_square():
    text = "HELICAL PILE 45MM SOLID SQUARE SHAFT 250/300/350 HELIX 250KN"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["shaft_type"] == "SOLID_SQUARE_SHAFT"
    assert parsed["shaft_diameter_mm"] == 45.0
    assert parsed["helix_configuration"] == "TRIPLE_HELIX"
    assert parsed["helix_diameters_mm"] == [250.0, 300.0, 350.0]
    assert parsed["working_capacity_kn"] == 250.0


def test_parse_screw_pier_callout_single_helix():
    text = "GROUND SCREW 76MM SHAFT 300MM SINGLE HELIX 100 KN"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["helix_configuration"] == "SINGLE_HELIX"
    assert parsed["helix_diameters_mm"] == [300.0]
    assert parsed["working_capacity_kn"] == 100.0


def test_parse_screw_pier_callout_chance_pile():
    text = "CHANCE PILE 114MM CHS 300KN"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["shaft_diameter_mm"] == 114.0
    assert parsed["working_capacity_kn"] == 300.0


def test_parse_screw_pier_callout_unrelated():
    assert parse_screw_pier_callout("STRIP FOOTING 600X300") is None


def test_evaluate_screw_pier_helical_anchor_shadow_single():
    callouts = ["SCREW PIER 89MM CHS 150KN"]
    positions = [(100.2, 200.4)]
    res = evaluate_screw_pier_helical_anchor_shadow("S-901", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "S-901_shp_001"
    assert c.sheet_id == "S-901"
    assert c.position == (100.0, 200.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_screw_pier_helical_anchor_shadow_dict():
    c = ScrewPierCandidate(
        candidate_id="S-902_shp_001",
        sheet_id="S-902",
        shaft_type="PIPE_SHAFT_CHS",
        shaft_diameter_mm=89.0,
        helix_configuration="DOUBLE_HELIX",
        helix_diameters_mm=[250.0, 300.0],
        working_capacity_kn=150.0,
        minimum_depth_m=6.0,
        target_torque_knm=15.0,
        position=(50.0, 50.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "S-902_shp_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["shaft_type"] == "PIPE_SHAFT_CHS"


def test_evaluate_screw_pier_helical_anchor_shadow_no_positions():
    callouts = ["SCREW PIER 89MM"]
    res = evaluate_screw_pier_helical_anchor_shadow("S-903", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_screw_pier_helical_anchor_shadow_safety_cap():
    callouts = ["SCREW PIER"] * 10
    res = evaluate_screw_pier_helical_anchor_shadow("S-904", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_screw_pier_helical_anchor_shadow("S-905", []) == []


def test_unrelated_callout_filtering():
    callouts = ["CONCRETE SLAB 150MM", "SCREW PIER 89MM"]
    res = evaluate_screw_pier_helical_anchor_shadow("S-906", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "S-906_shp_002"


def test_torque_pier_trigger():
    text = "TORQUE PIER 18 KNM TORQUE"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["target_torque_knm"] == 18.0


def test_helical_anchor_trigger():
    text = "HELICAL ANCHOR 200 KN"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["working_capacity_kn"] == 200.0


def test_default_values():
    text = "SCREW PILE"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["shaft_type"] == "PIPE_SHAFT_CHS"
    assert parsed["shaft_diameter_mm"] == 89.0
    assert parsed["helix_configuration"] == "DOUBLE_HELIX"
    assert parsed["working_capacity_kn"] == 150.0


def test_snapping_precision():
    callouts = ["SCREW PIER"]
    positions = [(4.9, 9.9)]
    res = evaluate_screw_pier_helical_anchor_shadow("S-907", callouts, positions)
    assert res[0].position == (5.0, 10.0)


def test_diameter_symbol():
    text = "SCREW PIER Ø89 150KN"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["shaft_diameter_mm"] == 89.0


def test_embedment_keyword():
    text = "SCREW PIER 5.5M EMBEDMENT"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["minimum_depth_m"] == 5.5


def test_kn_dot_m_torque():
    text = "SCREW PIER 16 KN.M"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["target_torque_knm"] == 16.0


def test_solid_square_rcs():
    text = "SCREW PIER 40MM RCS SOLID"
    parsed = parse_screw_pier_callout(text)
    assert parsed is not None
    assert parsed["shaft_type"] == "SOLID_SQUARE_SHAFT"
    assert parsed["shaft_diameter_mm"] == 40.0
