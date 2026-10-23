"""
Unit and adversarial test suite for Source Structural Steel Girt Sag Rod & Fly Bracing Shadow Authority.
"""

import pytest
from pb_source_steel_girt_sag_rod_fly_brace_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    SteelGirtSagRodFlyBraceCallout,
    snap_point,
    parse_steel_girt_sag_rod_fly_brace_callout,
    evaluate_steel_girt_sag_rod_fly_brace_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_sag_rod_basic():
    text = "WALL GIRT SAG ROD M12 SINGLE ROW MIDSPAN HOT DIP GALVANISED WITH M12 GRADE 4.6 BOLTS"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["component_category"] == "SAG_ROD_SYSTEM"
    assert parsed["section_profile"] == "M12"
    assert parsed["row_configuration"] == "MIDSPAN_SINGLE_ROW"
    assert parsed["fastener_type"] == "M12_GRADE_4.6"
    assert parsed["finish_coating"] == "HOT_DIP_GALVANISED"


def test_parse_fly_brace_basic():
    text = "RAFTER TO PURLIN BOTTOM FLANGE FLY BRACE 50X50X5 EA WITH GRADE 8.8 BOLTS"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["component_category"] == "FLY_BRACE"
    assert parsed["section_profile"] == "50x50x5 EA"
    assert parsed["fastener_type"] == "M16_GRADE_8.8"


def test_parse_combined_sag_fly():
    text = "STRUCTURAL STEEL PURLIN SAG ROD M16 AND COLUMN FLY BRACING 50X50X6 EA AT THIRD POINTS"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["component_category"] == "COMBINED_SAG_FLY"
    assert "M16" in parsed["section_profile"]
    assert "50x50x6 EA" in parsed["section_profile"]
    assert parsed["row_configuration"] == "THIRD_POINTS_DOUBLE_ROW"


def test_parse_sag_strap():
    text = "PURLIN SAG STRAP 25X3 STRAP WITH TEK SCREWS"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["component_category"] == "SAG_ROD_SYSTEM"
    assert "25x3 FLAT STRAP" in parsed["section_profile"]
    assert parsed["fastener_type"] == "SELF_DRILLING_TEK_SCREWS"


def test_parse_unrelated():
    assert parse_steel_girt_sag_rod_fly_brace_callout("CONCRETE FOUNDATION PAD") is None
    assert parse_steel_girt_sag_rod_fly_brace_callout("ALUMINIUM SLIDING DOOR") is None


def test_evaluate_steel_girt_sag_rod_fly_brace_shadow_single():
    callouts = ["WALL GIRT SAG ROD M12"]
    positions = [(10.1, 20.2)]
    results = evaluate_steel_girt_sag_rod_fly_brace_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_steel_girt_sag_rod_fly_brace_shadow_dict():
    items = [{"text": "FLY BRACE 50X50X5 EA", "position": (5.0, 7.6)}]
    results = evaluate_steel_girt_sag_rod_fly_brace_shadow(items)
    assert len(results) == 1
    assert results[0].component_category == "FLY_BRACE"
    assert results[0].position == (5.0, 7.5)


def test_evaluate_steel_girt_sag_rod_fly_brace_shadow_no_positions():
    results = evaluate_steel_girt_sag_rod_fly_brace_shadow(["SAG SYSTEM"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_steel_girt_sag_rod_fly_brace_shadow_safety_cap():
    huge_input = ["SAG ROD M12"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_steel_girt_sag_rod_fly_brace_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_steel_girt_sag_rod_fly_brace_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "FLY BRACE 50X50X5 EA", "ROOM 101"]
    results = evaluate_steel_girt_sag_rod_fly_brace_shadow(items)
    assert len(results) == 1
    assert results[0].component_category == "FLY_BRACE"


def test_triple_row_quarter_points():
    text = "GIRT SAG ROD THREE ROWS AT QUARTER POINTS"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "QUARTER_POINTS_TRIPLE_ROW"


def test_double_row_keyword():
    text = "SAG ROD TWO ROWS"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "THIRD_POINTS_DOUBLE_ROW"


def test_welded_cleat_fastener():
    text = "FLY BRACING WITH WELDED CLEAT CONNECTION"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["fastener_type"] == "WELDED_CLEAT"


def test_zinc_plated_finish():
    text = "SAG TIE M12 ELECTRO ZINC PLATED"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["finish_coating"] == "ELECTRO_ZINC_PLATED"


def test_painted_finish():
    text = "FLY BRACE WITH EPOXY PRIMER PAINTED"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["finish_coating"] == "EPOXY_PRIMER_PAINTED"


def test_snapping_precision():
    callouts = ["TIE ROD GIRT"]
    positions = [(12.49, 13.76)]
    results = evaluate_steel_girt_sag_rod_fly_brace_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_invalid_item_types():
    results = evaluate_steel_girt_sag_rod_fly_brace_shadow([123, None, object()])
    assert results == []


def test_m20_sag_rod():
    text = "HEAVY GIRT SAG ROD M20"
    parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
    assert parsed is not None
    assert parsed["section_profile"] == "M20"
