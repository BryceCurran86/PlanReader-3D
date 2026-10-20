"""Unit tests for Source Roof Parapet Capping & Standing Seam Flashing Shadow Authority."""

import pytest
from pb_source_roof_parapet_capping_flashing_shadow import (
    RoofFlashingCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_roof_flashing_callout,
    evaluate_roof_parapet_capping_flashing_shadow,
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


def test_parse_roof_flashing_callout_colorbond_parapet():
    text = "0.55MM COLORBOND PARAPET CAPPING 450MM GIRTH WITH CONTINUOUS CLEAT FALL 3%"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["flashing_type"] == "PARAPET_CAPPING"
    assert parsed["material"] == "COLORBOND_STEEL"
    assert parsed["thickness_mm"] == 0.55
    assert parsed["girth_or_width_mm"] == 450.0
    assert parsed["fall_slope_pct"] == 3.0
    assert parsed["fixing_method"] == "CONTINUOUS_CLEAT"


def test_parse_roof_flashing_callout_standing_seam_zinc():
    text = "0.7MM VMZINC STANDING SEAM FLASHING FALL 1:20"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["flashing_type"] == "STANDING_SEAM_FLASHING"
    assert parsed["material"] == "ZINC"
    assert parsed["thickness_mm"] == 0.7
    assert parsed["fall_slope_pct"] == 5.0


def test_parse_roof_flashing_callout_counter_flashing_copper():
    text = "COPPER COUNTER FLASHING POP RIVETED"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["flashing_type"] == "COUNTER_FLASHING"
    assert parsed["material"] == "COPPER"
    assert parsed["fixing_method"] == "POP_RIVETED"


def test_parse_roof_flashing_callout_apron_aluminum():
    text = "1.2MM ALUMINIUM APRON FLASHING 300MM WIDE"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["flashing_type"] == "APRON_FLASHING"
    assert parsed["material"] == "ALUMINIUM"
    assert parsed["thickness_mm"] == 1.2
    assert parsed["girth_or_width_mm"] == 300.0


def test_parse_roof_flashing_callout_drip_edge():
    text = "STAINLESS STEEL DRIP EDGE FLASHING"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["flashing_type"] == "DRIP_EDGE"
    assert parsed["material"] == "STAINLESS_STEEL"


def test_parse_roof_flashing_callout_unrelated():
    assert parse_roof_flashing_callout("ALUMINUM FRAMED WINDOW W01") is None


def test_evaluate_roof_parapet_capping_flashing_shadow_single():
    callouts = ["0.55MM COLORBOND PARAPET CAPPING 450MM GIRTH"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_roof_parapet_capping_flashing_shadow("A-501", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "A-501_rcf_001"
    assert c.sheet_id == "A-501"
    assert c.flashing_type == "PARAPET_CAPPING"
    assert c.material == "COLORBOND_STEEL"
    assert c.thickness_mm == 0.55
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_roof_parapet_capping_flashing_shadow_dict():
    c = RoofFlashingCandidate(
        candidate_id="A-502_rcf_001",
        sheet_id="A-502",
        flashing_type="STANDING_SEAM_FLASHING",
        material="ZINC",
        thickness_mm=0.7,
        girth_or_width_mm=400.0,
        fall_slope_pct=3.0,
        fixing_method="CONTINUOUS_CLEAT",
        points=[(0.0, 0.0), (50.0, 0.0)],
        length_pt=50.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "A-502_rcf_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["material"] == "ZINC"


def test_evaluate_roof_parapet_capping_flashing_shadow_no_polys():
    callouts = ["PARAPET CAPPING SCREW FIXED"]
    res = evaluate_roof_parapet_capping_flashing_shadow("A-503", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_roof_parapet_capping_flashing_shadow_safety_cap():
    callouts = ["PARAPET CAPPING"] * 10
    res = evaluate_roof_parapet_capping_flashing_shadow("A-504", callouts, max_primitives=3)
    assert len(res) == 3


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_roof_parapet_capping_flashing_shadow("A-505", []) == []


def test_unrelated_callout_filtering():
    callouts = ["TIMBER TRUSS T1", "METAL CAPPING 400MM"]
    res = evaluate_roof_parapet_capping_flashing_shadow("A-506", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "A-506_rcf_002"


def test_rheinzink_material_detection():
    text = "RHEINZINK PARAPET FLASHING"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["material"] == "ZINC"


def test_ratio_slope_detection():
    text = "PARAPET CAPPING FALL 1:10"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["fall_slope_pct"] == 10.0


def test_default_colorbond_values():
    text = "ROOF CAPPING"
    parsed = parse_roof_flashing_callout(text)
    assert parsed is not None
    assert parsed["material"] == "COLORBOND_STEEL"
    assert parsed["thickness_mm"] == 0.55
    assert parsed["girth_or_width_mm"] == 400.0
    assert parsed["fall_slope_pct"] == 3.0


def test_polyline_snapping_precision():
    callouts = ["PARAPET CAPPING"]
    polys = [[(1.2, 1.2), (24.8, 1.2)]]
    res = evaluate_roof_parapet_capping_flashing_shadow("A-507", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (25.0, 0.0)
    assert res[0].length_pt == 25.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0
