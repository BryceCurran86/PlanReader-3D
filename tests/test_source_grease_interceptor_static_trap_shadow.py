"""
Unit and adversarial test suite for Source Hydraulic Trade Waste Grease Interceptor Static Trap Shadow Authority.
"""

import pytest
from pb_source_grease_interceptor_static_trap_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    GreaseInterceptorStaticTrapCallout,
    snap_point,
    parse_grease_interceptor_static_trap_callout,
    evaluate_grease_interceptor_static_trap_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_grease_interceptor_basic():
    text = "TRADE WASTE GREASE INTERCEPTOR 2000L ROTOMOULDED POLYETHYLENE WITH INTERNAL BAFFLE WALL CLASS D GASTIGHT COVER AND SAMPLING POINT DN100 VENT"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 2000.0
    assert parsed["vessel_material"] == "ROTOMOULDED_POLYETHYLENE"
    assert parsed["baffle_configuration"] == "INTERNAL_BAFFLE_WALL"
    assert parsed["cover_class"] == "CLASS_D_GASTIGHT"
    assert parsed["vent_specification"] == "DN100_VENT_TO_ATMOSPHERE"
    assert parsed["sampling_pit_included"] is True


def test_parse_concrete_large_interceptor():
    text = "PRECAST CONCRETE GREASE ARRESTOR 5000 LITRES SUBMERGED BAFFLE CLASS B GASTIGHT COVER"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 5000.0
    assert parsed["vessel_material"] == "PRECAST_CONCRETE"
    assert parsed["baffle_configuration"] == "SUBMERGED_BAFFLE"
    assert parsed["cover_class"] == "CLASS_B_GASTIGHT"


def test_parse_stainless_steel_compact():
    text = "STATIC GREASE TRAP 1000L STAINLESS STEEL 316 WITH T-PIECE INLET OUTLET DN50 VENT"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 1000.0
    assert parsed["vessel_material"] == "FABRICATED_STAINLESS_STEEL"
    assert parsed["baffle_configuration"] == "T_PIECE_INLET_OUTLET"
    assert parsed["vent_specification"] == "DN50_VENT_TO_ATMOSPHERE"


def test_parse_unrelated():
    assert parse_grease_interceptor_static_trap_callout("HOT WATER STORAGE HEATER") is None
    assert parse_grease_interceptor_static_trap_callout("FIRE SPRINKLER PUMP") is None


def test_evaluate_grease_trap_shadow_single():
    callouts = ["GREASE INTERCEPTOR 1500L"]
    positions = [(10.1, 20.2)]
    results = evaluate_grease_interceptor_static_trap_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_grease_trap_shadow_dict():
    items = [{"text": "PASSIVE GREASE INTERCEPTOR 3000L", "position": (5.0, 7.6)}]
    results = evaluate_grease_interceptor_static_trap_shadow(items)
    assert len(results) == 1
    assert results[0].capacity_litres == 3000.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_grease_trap_shadow_no_positions():
    results = evaluate_grease_interceptor_static_trap_shadow(["GIT IN PIT"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_grease_trap_shadow_safety_cap():
    huge_input = ["GREASE TRAP 1500L"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_grease_interceptor_static_trap_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_grease_interceptor_static_trap_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "GREASE TRAP 1500L", "ROOM 101"]
    results = evaluate_grease_interceptor_static_trap_shadow(items)
    assert len(results) == 1
    assert results[0].capacity_litres == 1500.0


def test_git_trigger():
    text = "G.I.T. 2500 LTR IN CARPARK"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 2500.0
    assert parsed["cover_class"] == "CLASS_D_GASTIGHT"


def test_grease_arrester_spelling():
    text = "GREASE ARRESTER 1500L"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 1500.0


def test_default_values():
    text = "FOOD WASTE GREASE TRAP"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["capacity_litres"] == 1500.0
    assert parsed["vessel_material"] == "ROTOMOULDED_POLYETHYLENE"
    assert parsed["baffle_configuration"] == "INTERNAL_BAFFLE_WALL"
    assert parsed["cover_class"] == "BOLTED_AIRTIGHT"
    assert parsed["vent_specification"] == "DN100_VENT_TO_ATMOSPHERE"
    assert parsed["sampling_pit_included"] is True


def test_snapping_precision():
    callouts = ["GREASE INTERCEPTOR"]
    positions = [(12.49, 13.76)]
    results = evaluate_grease_interceptor_static_trap_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_without_sampling_negation():
    text = "GREASE TRAP 1000L WITHOUT SAMPLING POINT"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["sampling_pit_included"] is False


def test_dn80_vent():
    text = "GREASE INTERCEPTOR DN80 VENT"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["vent_specification"] == "DN80_VENT_TO_ATMOSPHERE"


def test_fibreglass_material():
    text = "GREASE INTERCEPTOR 2000L FIBREGLASS TANK"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["vessel_material"] == "ROTOMOULDED_POLYETHYLENE"


def test_invalid_item_types():
    results = evaluate_grease_interceptor_static_trap_shadow([123, None, object()])
    assert results == []


def test_dip_pipe_baffle():
    text = "GREASE TRAP WITH DIP PIPE INLET"
    parsed = parse_grease_interceptor_static_trap_callout(text)
    assert parsed is not None
    assert parsed["baffle_configuration"] == "T_PIECE_INLET_OUTLET"
