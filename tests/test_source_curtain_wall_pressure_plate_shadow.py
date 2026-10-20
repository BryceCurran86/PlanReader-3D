"""Unit tests for Source Glazed Aluminium Curtain Wall Pressure Plate & Thermal Break Shadow Authority."""

import pytest
from pb_source_curtain_wall_pressure_plate_shadow import (
    CurtainWallPressurePlateCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_curtain_wall_pressure_plate_callout,
    evaluate_curtain_wall_pressure_plate_shadow,
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


def test_parse_curtain_wall_pressure_plate_callout_box_cap():
    text = "CURTAIN WALL PRESSURE PLATE WITH POLYAMIDE STRUT THERMAL BREAK 175MM MULLION 50MM SIGHTLINE 28MM IGU 50MM CAP @ 250 CTS"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["thermal_isolator_type"] == "POLYAMIDE_STRUT"
    assert parsed["exterior_cap_profile"] == "RECTANGULAR_BOX_CAP"
    assert parsed["mullion_depth_mm"] == 175.0
    assert parsed["mullion_sightline_width_mm"] == 50.0
    assert parsed["glazing_pocket_mm"] == 28.0
    assert parsed["cap_projection_depth_mm"] == 50.0
    assert parsed["pressure_screw_pitch_mm"] == 250.0


def test_parse_curtain_wall_pressure_plate_callout_aerofoil():
    text = "THERMALLY BROKEN MULLION 200MM WITH 100MM AEROFOIL FEATURE CAP 32MM DGU"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["exterior_cap_profile"] == "AEROFOIL_FEATURE_CAP"
    assert parsed["mullion_depth_mm"] == 200.0
    assert parsed["cap_projection_depth_mm"] == 100.0
    assert parsed["glazing_pocket_mm"] == 32.0


def test_parse_curtain_wall_pressure_plate_callout_bullnose_pvc():
    text = "PRESSURE PLATE WITH RIGID PVC ISOLATOR 65MM BULLNOSE CAP"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["thermal_isolator_type"] == "RIGID_PVC_ISOLATOR"
    assert parsed["exterior_cap_profile"] == "BULLNOSE_CAP"


def test_parse_curtain_wall_pressure_plate_callout_flush_epdm():
    text = "CURTAIN WALL MULLION EPDM GASKET STRUCTURAL GLAZED FLUSH SEAL"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["thermal_isolator_type"] == "EPDM_ISOLATOR_GASKET"
    assert parsed["exterior_cap_profile"] == "FLUSH_SEAL_NO_CAP"
    assert parsed["cap_projection_depth_mm"] == 0.0


def test_parse_curtain_wall_pressure_plate_callout_unrelated():
    assert parse_curtain_wall_pressure_plate_callout("TIMBER SKIRTING 65X18") is None


def test_evaluate_curtain_wall_pressure_plate_shadow_single():
    callouts = ["CURTAIN WALL PRESSURE PLATE 175MM MULLION"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_curtain_wall_pressure_plate_shadow("A-901", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "A-901_cwp_001"
    assert c.sheet_id == "A-901"
    assert c.mullion_depth_mm == 175.0
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_curtain_wall_pressure_plate_shadow_dict():
    c = CurtainWallPressurePlateCandidate(
        candidate_id="A-902_cwp_001",
        sheet_id="A-902",
        thermal_isolator_type="POLYAMIDE_STRUT",
        exterior_cap_profile="RECTANGULAR_BOX_CAP",
        mullion_depth_mm=175.0,
        mullion_sightline_width_mm=50.0,
        glazing_pocket_mm=28.0,
        cap_projection_depth_mm=20.0,
        pressure_screw_pitch_mm=250.0,
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "A-902_cwp_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["thermal_isolator_type"] == "POLYAMIDE_STRUT"


def test_evaluate_curtain_wall_pressure_plate_shadow_no_polys():
    callouts = ["PRESSURE PLATE 175MM MULLION"]
    res = evaluate_curtain_wall_pressure_plate_shadow("A-903", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_curtain_wall_pressure_plate_shadow_safety_cap():
    callouts = ["CURTAIN WALL PRESSURE PLATE"] * 10
    res = evaluate_curtain_wall_pressure_plate_shadow("A-904", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_curtain_wall_pressure_plate_shadow("A-905", []) == []


def test_unrelated_callout_filtering():
    callouts = ["CONCRETE BEAM 400X600", "CURTAIN WALL PRESSURE PLATE"]
    res = evaluate_curtain_wall_pressure_plate_shadow("A-906", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "A-906_cwp_002"


def test_beauty_cap_trigger():
    text = "BEAUTY CAP SNAP ON 50MM"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["exterior_cap_profile"] == "RECTANGULAR_BOX_CAP"


def test_facade_pressure_bar_trigger():
    text = "FACADE PRESSURE BAR WITH 36MM POCKET"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["glazing_pocket_mm"] == 36.0


def test_default_values():
    text = "CURTAIN WALL PRESSURE PLATE"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["thermal_isolator_type"] == "POLYAMIDE_STRUT"
    assert parsed["mullion_depth_mm"] == 175.0
    assert parsed["mullion_sightline_width_mm"] == 50.0
    assert parsed["glazing_pocket_mm"] == 28.0
    assert parsed["pressure_screw_pitch_mm"] == 250.0


def test_snapping_precision():
    callouts = ["PRESSURE PLATE"]
    polys = [[(1.2, 1.2), (48.8, 1.2)]]
    res = evaluate_curtain_wall_pressure_plate_shadow("A-907", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (50.0, 0.0)
    assert res[0].length_pt == 50.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0


def test_triple_glazing_pocket():
    text = "PRESSURE PLATE 42MM TRIPLE GLAZED"
    parsed = parse_curtain_wall_pressure_plate_callout(text)
    assert parsed is not None
    assert parsed["glazing_pocket_mm"] == 42.0
