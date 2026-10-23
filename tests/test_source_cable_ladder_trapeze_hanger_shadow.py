"""Unit tests for Source Electrical Cable Ladder Unistrut Trapeze Hanger Shadow Authority."""

import pytest
from pb_source_cable_ladder_trapeze_hanger_shadow import (
    CableLadderCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_cable_ladder_callout,
    evaluate_cable_ladder_trapeze_hanger_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((2.6, 5.1)) == (2.5, 5.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_snap_polyline_removes_duplicates():
    pts = [(0.0, 0.0), (0.2, 0.3), (50.0, 50.0)]
    snapped = snap_polyline(pts)
    assert len(snapped) == 2
    assert snapped[0] == (0.0, 0.0)
    assert snapped[1] == (50.0, 50.0)


def test_calculate_polyline_length():
    pts = [(0.0, 0.0), (0.0, 100.0)]
    assert calculate_polyline_length(pts) == 100.0


def test_parse_cable_ladder_callout_standard_hdg():
    text = "600MM CABLE LADDER 100MM SIDE RAIL HDG WITH P1000 UNISTRUT TRAPEZE HANGER M12 ROD @ 1.5M CTS"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["material_finish"] == "HOT_DIP_GALVANIZED"
    assert parsed["ladder_width_mm"] == 600.0
    assert parsed["side_rail_height_mm"] == 100.0
    assert parsed["channel_profile"] == "P1000"
    assert parsed["threaded_rod_dia_mm"] == 12.0
    assert parsed["hanger_spacing_mm"] == 1500.0


def test_parse_cable_ladder_callout_stainless_seismic():
    text = "300W CABLE LADDER STAINLESS 316 WITH SWAY BRACE SEISMIC M16 ROD"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["material_finish"] == "STAINLESS_STEEL_316"
    assert parsed["ladder_width_mm"] == 300.0
    assert parsed["seismic_braced"] is True
    assert parsed["threaded_rod_dia_mm"] == 16.0


def test_parse_cable_ladder_callout_asnzs_fire_rated():
    text = "CABLE LADDER AS/NZS 3013 2-HR FIRE RATED P1001 CHANNEL @ 1200MM CTS"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["fire_rated"] is True
    assert parsed["channel_profile"] == "P1001"
    assert parsed["hanger_spacing_mm"] == 1200.0


def test_parse_cable_ladder_callout_aluminum_p2000():
    text = "ALUMINIUM CABLE LADDER 450MM WIDE P2000 TRAPEZE HANGER M10"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["material_finish"] == "ALUMINIUM"
    assert parsed["ladder_width_mm"] == 450.0
    assert parsed["channel_profile"] == "P2000"
    assert parsed["threaded_rod_dia_mm"] == 10.0


def test_parse_cable_ladder_callout_unrelated():
    assert parse_cable_ladder_callout("HOT WATER COPPER PIPE 25MM") is None


def test_evaluate_cable_ladder_trapeze_hanger_shadow_single():
    callouts = ["600MM CABLE LADDER HDG P1000 TRAPEZE @ 1.5M CTS"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_cable_ladder_trapeze_hanger_shadow("E-301", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "E-301_clt_001"
    assert c.sheet_id == "E-301"
    assert c.ladder_width_mm == 600.0
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_cable_ladder_trapeze_hanger_shadow_dict():
    c = CableLadderCandidate(
        candidate_id="E-302_clt_001",
        sheet_id="E-302",
        material_finish="HOT_DIP_GALVANIZED",
        ladder_width_mm=450.0,
        side_rail_height_mm=100.0,
        channel_profile="P1000",
        threaded_rod_dia_mm=12.0,
        hanger_spacing_mm=1500.0,
        fire_rated=False,
        seismic_braced=False,
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "E-302_clt_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["material_finish"] == "HOT_DIP_GALVANIZED"


def test_evaluate_cable_ladder_trapeze_hanger_shadow_no_polys():
    callouts = ["CABLE LADDER P1000 HANGER"]
    res = evaluate_cable_ladder_trapeze_hanger_shadow("E-303", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_cable_ladder_trapeze_hanger_shadow_safety_cap():
    callouts = ["CABLE LADDER"] * 10
    res = evaluate_cable_ladder_trapeze_hanger_shadow("E-304", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_cable_ladder_trapeze_hanger_shadow("E-305", []) == []


def test_unrelated_callout_filtering():
    callouts = ["CONDUIT 25MM PVC", "CABLE LADDER 450MM"]
    res = evaluate_cable_ladder_trapeze_hanger_shadow("E-306", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "E-306_clt_002"


def test_pre_gal_material():
    text = "PRE-GAL CABLE LADDER"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["material_finish"] == "PRE_GALVANIZED"


def test_sway_strut_keyword():
    text = "CABLE LADDER WITH SWAY STRUT"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["seismic_braced"] is True


def test_default_values():
    text = "CABLE LADDER"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["material_finish"] == "HOT_DIP_GALVANIZED"
    assert parsed["ladder_width_mm"] == 450.0
    assert parsed["side_rail_height_mm"] == 100.0
    assert parsed["channel_profile"] == "P1000"
    assert parsed["threaded_rod_dia_mm"] == 12.0
    assert parsed["hanger_spacing_mm"] == 1500.0
    assert parsed["fire_rated"] is False
    assert parsed["seismic_braced"] is False


def test_snapping_precision():
    callouts = ["CABLE LADDER"]
    polys = [[(1.2, 1.2), (48.8, 1.2)]]
    res = evaluate_cable_ladder_trapeze_hanger_shadow("E-307", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (50.0, 0.0)
    assert res[0].length_pt == 50.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0


def test_side_rail_depth_keyword():
    text = "CABLE LADDER 150MM DEPTH"
    parsed = parse_cable_ladder_callout(text)
    assert parsed is not None
    assert parsed["side_rail_height_mm"] == 150.0
