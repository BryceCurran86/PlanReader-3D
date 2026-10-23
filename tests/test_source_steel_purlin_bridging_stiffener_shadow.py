"""
Unit and adversarial test suite for Source Structural Steel Purlin Bridging Hook Bolt & C-Section Stiffener Shadow Authority.
"""

import pytest
from pb_source_steel_purlin_bridging_stiffener_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    SteelPurlinBridgingStiffenerCallout,
    snap_point,
    parse_steel_purlin_bridging_stiffener_callout,
    evaluate_steel_purlin_bridging_stiffener_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_purlin_bridging_basic():
    text = "ROOF PURLIN BRIDGING CHANNEL WITH M12 BRIDGING HOOK BOLT FOR Z200 PURLINS 1 ROW MIDSPAN GALVABOND Z275"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["bridging_system"] == "HOOK_BOLT_CHANNEL_BRIDGING"
    assert parsed["hook_bolt_size"] == "M12"
    assert parsed["purlin_series"] == "Z200"
    assert parsed["row_configuration"] == "1_ROW_MIDSPAN"
    assert parsed["web_stiffener_required"] is False
    assert parsed["finish_coating"] == "GALVABOND_Z275"


def test_parse_solid_strut_with_stiffeners():
    text = "GIRT BRIDGING SOLID STRUT M16 HOOK BOLTS FOR C250 WITH WEB STIFFENER 2 ROWS THIRD POINTS HOT DIP GALVANISED"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["bridging_system"] == "SOLID_STRUT_BRIDGING"
    assert parsed["hook_bolt_size"] == "M16"
    assert parsed["purlin_series"] == "C250"
    assert parsed["row_configuration"] == "2_ROWS_THIRD_POINTS"
    assert parsed["web_stiffener_required"] is True
    assert parsed["finish_coating"] == "HOT_DIP_GALVANISED"


def test_parse_expansion_bridging():
    text = "CONTINUOUS BRIDGING EXPANSION BRIDGING M10 BOLTS FOR Z150"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["bridging_system"] == "EXPANSION_BRIDGING"
    assert parsed["hook_bolt_size"] == "M10"
    assert parsed["purlin_series"] == "Z150"


def test_parse_unrelated():
    assert parse_steel_purlin_bridging_stiffener_callout("ALUMINIUM WINDOW FRAME") is None
    assert parse_steel_purlin_bridging_stiffener_callout("CONCRETE STAIR TREAD") is None


def test_evaluate_purlin_bridging_shadow_single():
    callouts = ["PURLIN BRIDGING Z200"]
    positions = [(10.1, 20.2)]
    results = evaluate_steel_purlin_bridging_stiffener_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_purlin_bridging_shadow_dict():
    items = [{"text": "BRIDGING SYSTEM Z250", "position": (5.0, 7.6)}]
    results = evaluate_steel_purlin_bridging_stiffener_shadow(items)
    assert len(results) == 1
    assert results[0].purlin_series == "Z250"
    assert results[0].position == (5.0, 7.5)


def test_evaluate_purlin_bridging_shadow_no_positions():
    results = evaluate_steel_purlin_bridging_stiffener_shadow(["FASCIA BRIDGING"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_purlin_bridging_shadow_safety_cap():
    huge_input = ["PURLIN BRIDGING"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_steel_purlin_bridging_stiffener_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_steel_purlin_bridging_stiffener_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "PURLIN BRIDGING", "ROOM 101"]
    results = evaluate_steel_purlin_bridging_stiffener_shadow(items)
    assert len(results) == 1
    assert results[0].purlin_series == "Z200"


def test_triple_row_quarter_points():
    text = "PURLIN BRIDGING 3 ROWS AT QUARTER POINTS"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "3_ROWS_QUARTER_POINTS"


def test_without_stiffener_negation():
    text = "PURLIN STRUT WITH WITHOUT STIFFENER"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["web_stiffener_required"] is False


def test_default_values():
    text = "BRIDGING CHANNEL"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["bridging_system"] == "HOOK_BOLT_CHANNEL_BRIDGING"
    assert parsed["hook_bolt_size"] == "M12"
    assert parsed["purlin_series"] == "Z200"
    assert parsed["row_configuration"] == "1_ROW_MIDSPAN"
    assert parsed["web_stiffener_required"] is False
    assert parsed["finish_coating"] == "GALVABOND_Z275"


def test_snapping_precision():
    callouts = ["BRIDGING HOOK BOLT"]
    positions = [(12.49, 13.76)]
    results = evaluate_steel_purlin_bridging_stiffener_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_zinc_plated_finish():
    text = "PURLIN BRIDGING ZINC PLATED"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["finish_coating"] == "ELECTRO_ZINC_PLATED"


def test_z300_deep_purlin():
    text = "PURLIN BRIDGING Z300"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["purlin_series"] == "Z300"


def test_c150_channel_purlin():
    text = "GIRT BRIDGING C150"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["purlin_series"] == "C150"


def test_invalid_item_types():
    results = evaluate_steel_purlin_bridging_stiffener_shadow([123, None, object()])
    assert results == []


def test_roof_bridging_trigger():
    text = "ROOF BRIDGING 2 ROWS"
    parsed = parse_steel_purlin_bridging_stiffener_callout(text)
    assert parsed is not None
    assert parsed["row_configuration"] == "2_ROWS_THIRD_POINTS"
