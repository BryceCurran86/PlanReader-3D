"""Unit tests for Source Commercial Laundry Lint Trap & Hydrodynamic Interceptor Shadow Authority."""

import pytest
from pb_source_laundry_lint_trap_shadow import (
    LaundryLintTrapCandidate,
    snap_point,
    parse_laundry_lint_trap_callout,
    evaluate_laundry_lint_trap_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((12.4, 14.9)) == (12.5, 15.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_laundry_lint_trap_callout_poly_dual_basket():
    text = "COMMERCIAL LAUNDRY TRAP 1000L POLYETHYLENE WITH DUAL STAINLESS STEEL FILTER BASKETS DN100 CLASS B"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["trap_material"] == "ROTOMOULDED_POLYETHYLENE"
    assert parsed["capacity_litres"] == 1000.0
    assert parsed["dual_filter_baskets"] is True
    assert parsed["inlet_outlet_dia_mm"] == 100.0
    assert parsed["cover_class"] == "CLASS_B_GASTIGHT"


def test_parse_laundry_lint_trap_callout_stainless_trafficable():
    text = "LINT TRAP STAINLESS STEEL 316 500 LITRES DN150 WITH CLASS D COVER AND SAMPLING POINT"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["trap_material"] == "STAINLESS_STEEL_316"
    assert parsed["capacity_litres"] == 500.0
    assert parsed["inlet_outlet_dia_mm"] == 150.0
    assert parsed["cover_class"] == "CLASS_D_GASTIGHT"
    assert parsed["sampling_point_present"] is True


def test_parse_laundry_lint_trap_callout_concrete_pit():
    text = "PRECAST CONCRETE LINT PIT 1500L CAPACITY"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["trap_material"] == "PRECAST_CONCRETE"
    assert parsed["capacity_litres"] == 1500.0


def test_parse_laundry_lint_trap_callout_unrelated():
    assert parse_laundry_lint_trap_callout("GREASE ARRESTOR 1000L") is None


def test_evaluate_laundry_lint_trap_shadow_single():
    callouts = ["COMMERCIAL LAUNDRY LINT TRAP 1000L DN100"]
    positions = [(100.2, 200.4)]
    res = evaluate_laundry_lint_trap_shadow("H-501", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "H-501_llt_001"
    assert c.sheet_id == "H-501"
    assert c.position == (100.0, 200.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_laundry_lint_trap_shadow_dict():
    c = LaundryLintTrapCandidate(
        candidate_id="H-502_llt_001",
        sheet_id="H-502",
        trap_material="ROTOMOULDED_POLYETHYLENE",
        capacity_litres=1000.0,
        dual_filter_baskets=True,
        inlet_outlet_dia_mm=100.0,
        cover_class="CLASS_B_GASTIGHT",
        sampling_point_present=True,
        position=(50.0, 50.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "H-502_llt_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["capacity_litres"] == 1000.0


def test_evaluate_laundry_lint_trap_shadow_no_positions():
    callouts = ["LINT TRAP 500L"]
    res = evaluate_laundry_lint_trap_shadow("H-503", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_laundry_lint_trap_shadow_safety_cap():
    callouts = ["LINT TRAP"] * 10
    res = evaluate_laundry_lint_trap_shadow("H-504", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_laundry_lint_trap_shadow("H-505", []) == []


def test_unrelated_callout_filtering():
    callouts = ["POTABLE WATER RETICULATION", "LINT TRAP 500L"]
    res = evaluate_laundry_lint_trap_shadow("H-506", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "H-506_llt_002"


def test_secondary_screen_keyword():
    text = "LINT PIT WITH SECONDARY SCREEN"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["dual_filter_baskets"] is True


def test_two_basket_keyword():
    text = "LAUNDRY INTERCEPTOR TWO BASKET SYSTEM"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["dual_filter_baskets"] is True


def test_default_values():
    text = "LINT TRAP"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["trap_material"] == "ROTOMOULDED_POLYETHYLENE"
    assert parsed["capacity_litres"] == 500.0
    assert parsed["inlet_outlet_dia_mm"] == 100.0
    assert parsed["cover_class"] == "BOLTED_AIRTIGHT"


def test_snapping_precision():
    callouts = ["LINT TRAP"]
    positions = [(4.9, 9.9)]
    res = evaluate_laundry_lint_trap_shadow("H-507", callouts, positions)
    assert res[0].position == (5.0, 10.0)


def test_hydrodynamic_lint_trigger():
    text = "HYDRODYNAMIC LINT INTERCEPTOR"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 500.0


def test_trade_waste_lint_trigger():
    text = "TRADE WASTE LINT PIT 250L"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 250.0


def test_trafficable_keyword():
    text = "LINT TRAP WITH TRAFFICABLE COVER"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["cover_class"] == "CLASS_D_GASTIGHT"


def test_inspection_point_keyword():
    text = "LINT TRAP WITH INSPECTION POINT"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["sampling_point_present"] is True


def test_diameter_symbol():
    text = "LINT TRAP Ø150 PIPE"
    parsed = parse_laundry_lint_trap_callout(text)
    assert parsed is not None
    assert parsed["inlet_outlet_dia_mm"] == 150.0
