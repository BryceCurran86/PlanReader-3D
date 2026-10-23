"""
Unit and adversarial test suite for Source Architectural Louver Storm Proof Blade & Sand Trap Shadow Authority.
"""

import pytest
from pb_source_louver_storm_proof_sand_trap_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    LouverStormProofSandTrapCallout,
    snap_point,
    parse_louver_storm_proof_sand_trap_callout,
    evaluate_louver_storm_proof_sand_trap_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_louver_stormproof_chevron():
    text = "EXTERIOR STORMPROOF LOUVRE TWO STAGE CHEVRON 100MM DEEP 75MM PITCH 50% FREE AREA WITH STAINLESS STEEL BIRD MESH POWDER COATED ALUMINIUM"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["blade_profile"] == "TWO_STAGE_CHEVRON"
    assert parsed["frame_depth_mm"] == 100.0
    assert parsed["blade_pitch_mm"] == 75.0
    assert parsed["free_area_percent"] == 50.0
    assert parsed["screen_backing"] == "STAINLESS_STEEL_BIRD_MESH"
    assert parsed["finish_coating"] == "POWDER_COATED_ALUMINIUM"


def test_parse_louver_sand_trap():
    text = "PLANTROOM SAND TRAP LOUVER 150MM FRAME 55% FA INSECT SCREEN ANODISED ALUMINIUM"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["blade_profile"] == "SAND_TRAP_SELF_DRAINING"
    assert parsed["frame_depth_mm"] == 150.0
    assert parsed["free_area_percent"] == 55.0
    assert parsed["screen_backing"] == "ALUMINIUM_INSECT_SCREEN"
    assert parsed["finish_coating"] == "ANODISED_ALUMINIUM"


def test_parse_louver_single_stage():
    text = "WEATHER LOUVER DRAINABLE BLADE 48% FREE AIR GALVANISED STEEL"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["blade_profile"] == "SINGLE_STAGE_DRAINABLE"
    assert parsed["free_area_percent"] == 48.0
    assert parsed["finish_coating"] == "GALVANISED_STEEL"


def test_parse_unrelated():
    assert parse_louver_storm_proof_sand_trap_callout("SOLID TIMBER DOOR") is None
    assert parse_louver_storm_proof_sand_trap_callout("CONCRETE BALCONY HOB") is None


def test_evaluate_louver_shadow_single():
    callouts = ["STORMPROOF LOUVER TWO STAGE"]
    positions = [(10.1, 20.2)]
    results = evaluate_louver_storm_proof_sand_trap_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_louver_shadow_dict():
    items = [{"text": "SAND TRAP LOUVRE", "position": (5.0, 7.6)}]
    results = evaluate_louver_storm_proof_sand_trap_shadow(items)
    assert len(results) == 1
    assert results[0].blade_profile == "SAND_TRAP_SELF_DRAINING"
    assert results[0].position == (5.0, 7.5)


def test_evaluate_louver_shadow_no_positions():
    results = evaluate_louver_storm_proof_sand_trap_shadow(["VENTILATION LOUVER"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_louver_shadow_safety_cap():
    huge_input = ["STORMPROOF LOUVRE"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_louver_storm_proof_sand_trap_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_louver_storm_proof_sand_trap_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "STORMPROOF LOUVER", "ROOM 101"]
    results = evaluate_louver_storm_proof_sand_trap_shadow(items)
    assert len(results) == 1
    assert results[0].raw_text == "STORMPROOF LOUVER"


def test_expanded_mesh_screen():
    text = "VENTILATION LOUVRE WITH EXPANDED MESH"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["screen_backing"] == "EXPANDED_ALUMINIUM_MESH"


def test_dual_stage_keyword():
    text = "DUAL STAGE LOUVRE 100MM"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["blade_profile"] == "TWO_STAGE_CHEVRON"


def test_default_values():
    text = "PLANTROOM LOUVER"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["blade_profile"] == "SINGLE_STAGE_DRAINABLE"
    assert parsed["frame_depth_mm"] == 100.0
    assert parsed["blade_pitch_mm"] == 75.0
    assert parsed["free_area_percent"] == 50.0
    assert parsed["screen_backing"] == "STAINLESS_STEEL_BIRD_MESH"
    assert parsed["finish_coating"] == "POWDER_COATED_ALUMINIUM"


def test_snapping_precision():
    callouts = ["CHEVRON LOUVRE"]
    positions = [(12.49, 13.76)]
    results = evaluate_louver_storm_proof_sand_trap_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_flyscreen_keyword():
    text = "WEATHER LOUVRE WITH FLYSCREEN"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["screen_backing"] == "ALUMINIUM_INSECT_SCREEN"


def test_anodized_spelling():
    text = "STORMPROOF LOUVER ANODIZED"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["finish_coating"] == "ANODISED_ALUMINIUM"


def test_custom_blade_pitch():
    text = "STORMPROOF LOUVER 50MM PITCH"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["blade_pitch_mm"] == 50.0


def test_invalid_item_types():
    results = evaluate_louver_storm_proof_sand_trap_shadow([123, None, object()])
    assert results == []


def test_drainable_blade_trigger():
    text = "DRAINABLE BLADE LOUVER 60% FREE AREA"
    parsed = parse_louver_storm_proof_sand_trap_callout(text)
    assert parsed is not None
    assert parsed["free_area_percent"] == 60.0
