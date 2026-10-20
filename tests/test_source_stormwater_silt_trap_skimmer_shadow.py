"""Unit tests for Source Hydraulic Stormwater Sump Silt Trap & Floating Oil Skimmer Shadow Authority."""

import pytest
from pb_source_stormwater_silt_trap_skimmer_shadow import (
    StormwaterSiltTrapCandidate,
    snap_point,
    parse_stormwater_silt_trap_callout,
    evaluate_stormwater_silt_trap_skimmer_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((21.4, 34.9)) == (22.5, 35.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_stormwater_silt_trap_callout_coalescing():
    text = "STORMWATER SUMP 1200X1200 WITH COALESCING PLATE SEPARATOR 600MM SILT PIT CLASS D GRATE"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "COALESCING_PLATE_PACK"
    assert parsed["pit_dimensions_description"] == "1200X1200"
    assert parsed["silt_storage_depth_mm"] == 1200.0 or parsed["silt_storage_depth_mm"] == 600.0
    assert parsed["grate_class"] == "CLASS_D"


def test_parse_stormwater_silt_trap_callout_floating_skimmer_trash_screen():
    text = "SEDIMENT TRAP WITH FLOATING OIL SKIMMER AND STAINLESS STEEL TRASH SCREEN"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "FLOATING_WEIR_SKIMMER"
    assert parsed["trash_screen_present"] is True


def test_parse_stormwater_silt_trap_callout_baffle_class_b():
    text = "STORMWATER SILT PIT 900 SQ WITH HYDROCARBON BAFFLE CLASS B GRATE"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "HYDROCARBON_BAFFLE"
    assert parsed["pit_dimensions_description"] == "900x900"
    assert parsed["grate_class"] == "CLASS_B"


def test_parse_stormwater_silt_trap_callout_solid_cover():
    text = "SUMP PIT SILT TRAP WITH SOLID COVER"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["grate_class"] == "SOLID_COVER"


def test_parse_stormwater_silt_trap_callout_unrelated():
    assert parse_stormwater_silt_trap_callout("SANITARY DRAINAGE SEWER PIPE 100 DIA") is None


def test_evaluate_stormwater_silt_trap_skimmer_shadow_single():
    callouts = ["STORMWATER SUMP 900X900 SILT TRAP 450MM CLASS D"]
    positions = [(50.2, 100.4)]
    res = evaluate_stormwater_silt_trap_skimmer_shadow("C-101", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "C-101_sts_001"
    assert c.sheet_id == "C-101"
    assert c.position == (50.0, 100.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_stormwater_silt_trap_skimmer_shadow_dict():
    c = StormwaterSiltTrapCandidate(
        candidate_id="C-102_sts_001",
        sheet_id="C-102",
        separator_type="FLOATING_WEIR_SKIMMER",
        pit_dimensions_description="900x900",
        silt_storage_depth_mm=450.0,
        trash_screen_present=True,
        grate_class="CLASS_D",
        position=(10.0, 20.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "C-102_sts_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["separator_type"] == "FLOATING_WEIR_SKIMMER"


def test_evaluate_stormwater_silt_trap_skimmer_shadow_no_positions():
    callouts = ["SILT TRAP 450MM DEEP"]
    res = evaluate_stormwater_silt_trap_skimmer_shadow("C-103", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_stormwater_silt_trap_skimmer_shadow_safety_cap():
    callouts = ["SILT TRAP"] * 10
    res = evaluate_stormwater_silt_trap_skimmer_shadow("C-104", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_stormwater_silt_trap_skimmer_shadow("C-105", []) == []


def test_unrelated_callout_filtering():
    callouts = ["WATER RETICULATION PIPE", "STORMWATER SUMP SILT TRAP"]
    res = evaluate_stormwater_silt_trap_skimmer_shadow("C-106", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "C-106_sts_002"


def test_litter_basket_trigger():
    text = "SILT TRAP WITH LITTER BASKET"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["trash_screen_present"] is True


def test_leaf_basket_trigger():
    text = "SEDIMENT SUMP WITH LEAF BASKET"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["trash_screen_present"] is True


def test_cps_abbreviation():
    text = "STORMWATER SUMP WITH CPS UNIT"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "COALESCING_PLATE_PACK"


def test_default_values():
    text = "SILT TRAP"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "SEDIMENT_SUMP_ONLY"
    assert parsed["pit_dimensions_description"] == "900x900"
    assert parsed["trash_screen_present"] is False
    assert parsed["grate_class"] == "CLASS_D"


def test_snapping_precision():
    callouts = ["SILT TRAP"]
    positions = [(7.2, 9.8)]
    res = evaluate_stormwater_silt_trap_skimmer_shadow("C-107", callouts, positions)
    assert res[0].position == (7.5, 10.0)


def test_sediment_sump_only_type():
    text = "STORMWATER SILT PIT WITHOUT BAFFLE"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "SEDIMENT_SUMP_ONLY"


def test_deep_silt_trap_regex():
    text = "SILT TRAP 600MM DEEP"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["silt_storage_depth_mm"] == 600.0


def test_no_baffle_phrase():
    text = "STORMWATER SUMP NO BAFFLE"
    parsed = parse_stormwater_silt_trap_callout(text)
    assert parsed is not None
    assert parsed["separator_type"] == "SEDIMENT_SUMP_ONLY"

