"""
Unit and adversarial test suite for Source Concrete Slab Dowelled Contraction Joint Flanged Plate Dowel Shadow Authority.
"""

import pytest
from pb_source_flanged_plate_dowel_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    FlangedPlateDowelCallout,
    snap_point,
    parse_flanged_plate_dowel_callout,
    evaluate_flanged_plate_dowel_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_diamond_dowel_basic():
    text = "SLAB CONTRACTION JOINT DIAMOND DOWEL 10MM THK 150X150 AT 450MM CTS WITH PLASTIC SLEEVE GRADE 300 STEEL"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["dowel_geometry"] == "DIAMOND_PLATE"
    assert parsed["plate_thickness_mm"] == 10.0
    assert parsed["plate_width_mm"] == 150.0
    assert parsed["plate_length_mm"] == 150.0
    assert parsed["joint_spacing_cts_mm"] == 450.0
    assert parsed["sleeve_type"] == "PLASTIC_EXPANSION_SLEEVE"
    assert parsed["steel_grade"] == "GRADE_300_STEEL"


def test_parse_rectangular_plate_foam():
    text = "EXPANSION DOWEL PLATE 6MM 100X100 AT 600MM CTS WITH LATERAL FOAM SLEEVE GALVANISED STEEL"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["dowel_geometry"] == "RECTANGULAR_PLATE"
    assert parsed["plate_thickness_mm"] == 6.0
    assert parsed["plate_width_mm"] == 100.0
    assert parsed["plate_length_mm"] == 100.0
    assert parsed["joint_spacing_cts_mm"] == 600.0
    assert parsed["sleeve_type"] == "COMPRESSIBLE_FOAM_SLEEVE"
    assert parsed["steel_grade"] == "GALVANISED_STEEL"


def test_parse_round_dowel_bar():
    text = "SAWCUT DOWEL R20 ROUND BAR AT 450 CTS"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["dowel_geometry"] == "ROUND_DOWEL_SLEEVE"


def test_parse_unrelated():
    assert parse_flanged_plate_dowel_callout("ALUMINIUM SKIRTING") is None
    assert parse_flanged_plate_dowel_callout("GYPSUM CORNICE") is None


def test_evaluate_plate_dowel_shadow_single():
    callouts = ["DIAMOND DOWEL 10MM"]
    positions = [(10.1, 20.2)]
    results = evaluate_flanged_plate_dowel_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_plate_dowel_shadow_dict():
    items = [{"text": "PLATE DOWEL 6MM", "position": (5.0, 7.6)}]
    results = evaluate_flanged_plate_dowel_shadow(items)
    assert len(results) == 1
    assert results[0].plate_thickness_mm == 6.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_plate_dowel_shadow_no_positions():
    results = evaluate_flanged_plate_dowel_shadow(["DOWEL CRADLE"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_plate_dowel_shadow_safety_cap():
    huge_input = ["DIAMOND DOWEL"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_flanged_plate_dowel_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_flanged_plate_dowel_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "DIAMOND DOWEL 10MM", "ROOM 101"]
    results = evaluate_flanged_plate_dowel_shadow(items)
    assert len(results) == 1
    assert results[0].dowel_geometry == "DIAMOND_PLATE"


def test_armor_edge_trigger():
    text = "ARMOR EDGE DOWEL 8MM AT 500MM CENTERS"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["plate_thickness_mm"] == 8.0
    assert parsed["joint_spacing_cts_mm"] == 500.0


def test_stainless_steel_grade():
    text = "PLATE DOWEL 10MM STAINLESS STEEL 316"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["steel_grade"] == "STAINLESS_STEEL_316"


def test_default_values():
    text = "JOINT DOWEL"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["dowel_geometry"] == "RECTANGULAR_PLATE"
    assert parsed["plate_thickness_mm"] == 6.0
    assert parsed["plate_width_mm"] == 100.0
    assert parsed["plate_length_mm"] == 100.0
    assert parsed["joint_spacing_cts_mm"] == 450.0
    assert parsed["sleeve_type"] == "PLASTIC_EXPANSION_SLEEVE"
    assert parsed["steel_grade"] == "GRADE_300_STEEL"


def test_snapping_precision():
    callouts = ["FLANGED DOWEL"]
    positions = [(12.49, 13.76)]
    results = evaluate_flanged_plate_dowel_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_unsleeved_debonded():
    text = "DOWEL CRADLE WITHOUT SLEEVE"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["sleeve_type"] == "UNSLEEVED_DEBONDED"


def test_12mm_heavy_plate():
    text = "DIAMOND DOWEL 12MM"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["plate_thickness_mm"] == 12.0


def test_custom_dimensions_110x110():
    text = "DIAMOND DOWEL 110X110"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["plate_width_mm"] == 110.0
    assert parsed["plate_length_mm"] == 110.0


def test_invalid_item_types():
    results = evaluate_flanged_plate_dowel_shadow([123, None, object()])
    assert results == []


def test_slab_dowel_sleeve_trigger():
    text = "SLAB DOWEL SLEEVE 6MM THK"
    parsed = parse_flanged_plate_dowel_callout(text)
    assert parsed is not None
    assert parsed["plate_thickness_mm"] == 6.0
