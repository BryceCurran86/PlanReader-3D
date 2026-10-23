"""Unit tests for Source Acoustic Floating Timber Floor Battens & Cradle Shadow Authority."""

import pytest
from pb_source_acoustic_cradle_batten_floor_shadow import (
    AcousticCradleFloorCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_acoustic_cradle_floor_callout,
    evaluate_acoustic_cradle_batten_floor_shadow,
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


def test_parse_acoustic_cradle_floor_callout_standard_rubber():
    text = "ACOUSTIC CRADLE FLOOR 45X45 BATTEN @ 400 CTS 50MM VOID 25MM MINERAL WOOL 22MM T&G 10MM FLANKING"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["cradle_material"] == "RECYCLED_CRUMB_RUBBER"
    assert parsed["batten_profile_description"] == "45x45"
    assert parsed["batten_spacing_mm"] == 400.0
    assert parsed["cradle_void_height_mm"] == 45.0 or parsed["cradle_void_height_mm"] == 50.0
    assert parsed["insulation_infill_thickness_mm"] == 25.0
    assert parsed["decking_thickness_mm"] == 22.0
    assert parsed["perimeter_flanking_band_thickness_mm"] == 10.0


def test_parse_acoustic_cradle_floor_callout_sprung_sports_floor():
    text = "SPRUNG TIMBER FLOOR 45X70 BATTEN @ 450 CTS ELASTOMER CRADLE 75MM CAVITY 50MM INSULATION"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["cradle_material"] == "ELASTOMERIC_NEOPRENE"
    assert parsed["batten_profile_description"] == "45x70"
    assert parsed["batten_spacing_mm"] == 450.0
    assert parsed["insulation_infill_thickness_mm"] == 50.0


def test_parse_acoustic_cradle_floor_callout_adjustable_pedestal():
    text = "ACOUSTIC BATTEN WITH ADJUSTABLE SCREWJACK PEDESTAL CRADLE 100MM VOID 18MM PLYWOOD"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["cradle_material"] == "POLYPROPYLENE_ADJUSTABLE"
    assert parsed["decking_thickness_mm"] == 18.0


def test_parse_acoustic_cradle_floor_callout_flanking_strip():
    text = "CRADLE AND BATTEN SYSTEM 15MM FLANKING STRIP"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["perimeter_flanking_band_thickness_mm"] == 15.0


def test_parse_acoustic_cradle_floor_callout_unrelated():
    assert parse_acoustic_cradle_floor_callout("VINYL SHEET FLOORING 2MM") is None


def test_evaluate_acoustic_cradle_batten_floor_shadow_single():
    callouts = ["ACOUSTIC CRADLE FLOOR 45X45 BATTEN"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_acoustic_cradle_batten_floor_shadow("A-1001", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "A-1001_cbf_001"
    assert c.sheet_id == "A-1001"
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_acoustic_cradle_batten_floor_shadow_dict():
    c = AcousticCradleFloorCandidate(
        candidate_id="A-1002_cbf_001",
        sheet_id="A-1002",
        cradle_material="RECYCLED_CRUMB_RUBBER",
        batten_profile_description="45x45",
        batten_spacing_mm=400.0,
        cradle_void_height_mm=50.0,
        insulation_infill_thickness_mm=25.0,
        decking_thickness_mm=22.0,
        perimeter_flanking_band_thickness_mm=10.0,
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "A-1002_cbf_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["cradle_material"] == "RECYCLED_CRUMB_RUBBER"


def test_evaluate_acoustic_cradle_batten_floor_shadow_no_polys():
    callouts = ["ACOUSTIC CRADLE FLOOR"]
    res = evaluate_acoustic_cradle_batten_floor_shadow("A-1003", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_acoustic_cradle_batten_floor_shadow_safety_cap():
    callouts = ["ACOUSTIC CRADLE FLOOR"] * 10
    res = evaluate_acoustic_cradle_batten_floor_shadow("A-1004", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_acoustic_cradle_batten_floor_shadow("A-1005", []) == []


def test_unrelated_callout_filtering():
    callouts = ["CERAMIC TILES", "ACOUSTIC CRADLE FLOOR"]
    res = evaluate_acoustic_cradle_batten_floor_shadow("A-1006", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "A-1006_cbf_002"


def test_neoprene_cradle():
    text = "FLOATING BATTEN NEOPRENE CRADLE"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["cradle_material"] == "ELASTOMERIC_NEOPRENE"


def test_polyester_quilt():
    text = "ACOUSTIC BATTEN 50MM POLYESTER QUILT"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["insulation_infill_thickness_mm"] == 50.0


def test_default_values():
    text = "CRADLE FLOOR"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["cradle_material"] == "RECYCLED_CRUMB_RUBBER"
    assert parsed["batten_profile_description"] == "45x45"
    assert parsed["batten_spacing_mm"] == 400.0
    assert parsed["decking_thickness_mm"] == 22.0
    assert parsed["perimeter_flanking_band_thickness_mm"] == 10.0


def test_snapping_precision():
    callouts = ["ACOUSTIC CRADLE FLOOR"]
    polys = [[(1.2, 1.2), (48.8, 1.2)]]
    res = evaluate_acoustic_cradle_batten_floor_shadow("A-1007", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (50.0, 0.0)
    assert res[0].length_pt == 50.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0


def test_c_slash_c_spacing():
    text = "ACOUSTIC BATTEN @ 600MM C/C"
    parsed = parse_acoustic_cradle_floor_callout(text)
    assert parsed is not None
    assert parsed["batten_spacing_mm"] == 600.0
