"""Unit tests for Source Commercial Kitchen Exhaust Hood Grease Duct Fire Wrap Shadow Authority."""

import pytest
from pb_source_kitchen_hood_grease_duct_wrap_shadow import (
    GreaseDuctWrapCandidate,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    parse_grease_duct_callout,
    evaluate_kitchen_hood_grease_duct_wrap_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((3.4, 6.9)) == (2.5, 7.5)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_snap_polyline_removes_duplicates():
    pts = [(0.0, 0.0), (0.1, 0.1), (30.0, 40.0)]
    snapped = snap_polyline(pts)
    assert len(snapped) == 2
    assert snapped[0] == (0.0, 0.0)
    assert snapped[1] == (30.0, 40.0)


def test_calculate_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    assert calculate_polyline_length(pts) == 50.0


def test_parse_grease_duct_callout_stainless_firemaster():
    text = "KITCHEN EXHAUST DUCT 600X450 1.2MM STAINLESS STEEL 2-HR FIREMASTER WRAP 38MM CLEANOUT ACCESS DOOR SLOPE 2%"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["duct_material"] == "WELDED_STAINLESS_STEEL"
    assert parsed["wrap_material"] == "CERAMIC_FIBER_BLANKET"
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["wrap_thickness_mm"] == 600.0 or parsed["wrap_thickness_mm"] == 38.0
    assert parsed["cleanout_doors"] is True
    assert parsed["slope_pct"] == 2.0


def test_parse_grease_duct_callout_mild_steel_frl():
    text = "GREASE DUCT FRL -/120/120 50MM BIO SOLUBLE WOOL SLOPE 1:50"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["duct_material"] == "WELDED_MILD_STEEL"
    assert parsed["wrap_material"] == "BIO_SOLUBLE_WOOL"
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["wrap_thickness_mm"] == 50.0
    assert parsed["slope_pct"] == 2.0


def test_parse_grease_duct_callout_calcium_silicate():
    text = "GREASE EXHAUST DUCT DIA 500 CALCIUM SILICATE BOARD 3-HR"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["wrap_material"] == "CALCIUM_SILICATE_BOARD"
    assert parsed["fire_rating_hours"] == 3.0
    assert parsed["duct_size_description"] == "DIA_500"


def test_parse_grease_duct_callout_unrelated():
    assert parse_grease_duct_callout("TOILET EXHAUST DUCT 200 DIA") is None


def test_evaluate_kitchen_hood_grease_duct_wrap_shadow_single():
    callouts = ["GREASE DUCT 2-HR FIRE WRAP WITH ACCESS PANEL"]
    polys = [[(0.0, 0.0), (100.0, 0.0)]]
    res = evaluate_kitchen_hood_grease_duct_wrap_shadow("M-201", callouts, polys)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "M-201_gdw_001"
    assert c.sheet_id == "M-201"
    assert c.cleanout_doors is True
    assert c.length_pt == 100.0
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_kitchen_hood_grease_duct_wrap_shadow_dict():
    c = GreaseDuctWrapCandidate(
        candidate_id="M-202_gdw_001",
        sheet_id="M-202",
        duct_material="WELDED_STAINLESS_STEEL",
        wrap_material="CERAMIC_FIBER_BLANKET",
        fire_rating_hours=2.0,
        wrap_thickness_mm=38.0,
        duct_size_description="600X450",
        cleanout_doors=True,
        slope_pct=2.0,
        points=[(0.0, 0.0), (60.0, 0.0)],
        length_pt=60.0,
    )
    d = c.to_dict()
    assert d["candidate_id"] == "M-202_gdw_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["cleanout_doors"] is True


def test_evaluate_kitchen_hood_grease_duct_wrap_shadow_no_polys():
    callouts = ["KITCHEN HOOD DUCT 2-HR"]
    res = evaluate_kitchen_hood_grease_duct_wrap_shadow("M-203", callouts)
    assert len(res) == 1
    assert res[0].points == []
    assert res[0].length_pt == 0.0


def test_evaluate_kitchen_hood_grease_duct_wrap_shadow_safety_cap():
    callouts = ["GREASE DUCT 2-HR"] * 10
    res = evaluate_kitchen_hood_grease_duct_wrap_shadow("M-204", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_kitchen_hood_grease_duct_wrap_shadow("M-205", []) == []


def test_unrelated_callout_filtering():
    callouts = ["SUPPLY AIR DUCT 400X300", "GREASE DUCT FIRE WRAP"]
    res = evaluate_kitchen_hood_grease_duct_wrap_shadow("M-206", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "M-206_gdw_002"


def test_fire_blanket_trigger():
    text = "DUCT FIRE BLANKET AT GREASE HOOD EXHAUST"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["fire_rating_hours"] == 2.0


def test_frl_three_digit():
    text = "GREASE DUCT FRL -/180/180"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["fire_rating_hours"] == 3.0


def test_inspection_hatch_trigger():
    text = "GREASE DUCT WITH INSPECTION HATCH"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["cleanout_doors"] is True


def test_diameter_symbol():
    text = "GREASE EXHAUST Ø450"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["duct_size_description"] == "DIA_450"


def test_default_values():
    text = "GREASE DUCT"
    parsed = parse_grease_duct_callout(text)
    assert parsed is not None
    assert parsed["duct_material"] == "WELDED_MILD_STEEL"
    assert parsed["wrap_material"] == "CERAMIC_FIBER_BLANKET"
    assert parsed["fire_rating_hours"] == 2.0
    assert parsed["cleanout_doors"] is False
    assert parsed["slope_pct"] == 2.0


def test_polyline_snapping_precision():
    callouts = ["GREASE DUCT"]
    polys = [[(1.1, 1.1), (39.9, 1.1)]]
    res = evaluate_kitchen_hood_grease_duct_wrap_shadow("M-207", callouts, polys)
    assert res[0].points[0] == (0.0, 0.0)
    assert res[0].points[1] == (40.0, 0.0)
    assert res[0].length_pt == 40.0


def test_calculate_polyline_length_empty():
    assert calculate_polyline_length([]) == 0.0
