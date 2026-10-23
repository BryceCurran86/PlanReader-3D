"""
Tests for Source Architectural Expansion Joint Fire Barrier Blanket Shadow Authority.
"""

import pytest
from pb_source_expansion_joint_fire_barrier_blanket_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    ExpansionJointFireBarrierBlanketCallout,
    snap_point,
    parse_expansion_joint_fire_barrier_blanket_callout,
    extract_expansion_joint_fire_barrier_blanket_candidates,
    validate_expansion_joint_fire_barrier_blanket_system,
)


def test_snap_point_regular():
    pt = snap_point(44.8, 67.3, snap_tol=2.5)
    assert pt == (45.0, 67.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(44.8, 67.3, snap_tol=0.0)
    assert pt == (44.8, 67.3)


def test_parse_none_on_irrelevant_text():
    assert parse_expansion_joint_fire_barrier_blanket_callout("ALUMINUM DOOR FRAME") is None
    assert parse_expansion_joint_fire_barrier_blanket_callout("CARPET TILES OVER SCREED") is None
    assert parse_expansion_joint_fire_barrier_blanket_callout("ACOUSTIC CEILING BAFFLE") is None


def test_parse_ceramic_fiber_foil_blanket():
    text = "EXPANSION JOINT FIRE BARRIER CERAMIC FIBER FOIL BLANKET 100MM JOINT WIDTH +/-50% MOVEMENT 2 HR FIRE RATING WITH GALVANIZED RETAINING ANGLES"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["barrier_type"] == "CERAMIC_FIBER_FOIL_BLANKET"
    assert parsed["nominal_joint_width_mm"] == 100.0
    assert parsed["movement_capacity_percent"] == "+/-50%"
    assert parsed["fire_rating_hours"] == "2HR"
    assert parsed["retaining_flange_brackets"] == "GALVANIZED_RETAINING_ANGLES"


def test_parse_multi_layer_intumescent_blanket_wall():
    text = "WALL EXPANSION JOINT FIRE BARRIER MULTI-LAYER INTUMESCENT BLANKET 150MM GAP +/-25% 3 HOUR WITH DUAL SMOKE SEAL"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["barrier_type"] == "MULTI_LAYER_INTUMESCENT_BLANKET"
    assert parsed["nominal_joint_width_mm"] == 150.0
    assert parsed["movement_capacity_percent"] == "+/-25%"
    assert parsed["fire_rating_hours"] == "3HR"
    assert parsed["smoke_barrier_layer"] == "DUAL_SMOKE_SEAL"
    assert parsed["joint_orientation"] == "WALL_EXPANSION_JOINT"


def test_parse_mineral_wool_elastomeric_seal():
    text = "SEISMIC JOINT FIRE BARRIER PRE-COMPRESSED MINERAL WOOL WITH ELASTOMERIC SMOKE COATING 50MM NOMINAL JOINT FRL -/120/120"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["barrier_type"] == "MINERAL_WOOL_ELASTOMERIC_SEAL"
    assert parsed["nominal_joint_width_mm"] == 50.0
    assert parsed["smoke_barrier_layer"] == "ELASTOMERIC_SMOKE_COATING"
    assert parsed["fire_rating_hours"] == "FRL-/120/120"


def test_parse_modular_fireline_system():
    text = "FIRELINE MODULAR EXPANSION JOINT FIRE BARRIER SYSTEM 200MM WITH STAINLESS STEEL SPRING CLIPS"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["barrier_type"] == "MODULAR_FIRE_BARRIER_SYSTEM"
    assert parsed["nominal_joint_width_mm"] == 200.0
    assert parsed["retaining_flange_brackets"] == "STAINLESS_STEEL_SPRING_CLIPS"


def test_parse_floor_slab_vapor_membrane():
    text = "FLOOR SLAB EXPANSION JOINT FIRE BLANKET 75MM WITH INTEGRAL VAPOR MEMBRANE 4 HR"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_orientation"] == "FLOOR_EXPANSION_JOINT"
    assert parsed["nominal_joint_width_mm"] == 75.0
    assert parsed["smoke_barrier_layer"] == "INTEGRAL_VAPOR_SMOKE_MEMBRANE"
    assert parsed["fire_rating_hours"] == "4HR"


def test_parse_soffit_ceiling_joint():
    text = "SOFFIT EXPANSION JOINT FIRE BARRIER BLANKET 1 HR WITH PINNED COLLAR"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_orientation"] == "SOFFIT_EXPANSION_JOINT"
    assert parsed["fire_rating_hours"] == "1HR"
    assert parsed["retaining_flange_brackets"] == "FASTENER_PINNED_COLLAR"


def test_extract_expansion_joint_fire_barrier_blanket_candidates():
    items = [
        ("EXPANSION JOINT FIRE BARRIER CERAMIC FIBER 100MM", (120.2, 240.3)),
        ("VINYL COVE SKIRTING", (50.0, 50.0)),
        ("WALL EXPANSION JOINT FIRE BARRIER 150MM 2 HR", (300.0, 400.0)),
    ]
    candidates = extract_expansion_joint_fire_barrier_blanket_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (120.0, 240.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"EXPANSION JOINT FIRE BARRIER {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_expansion_joint_fire_barrier_blanket_candidates(items, max_cap=14)
    assert len(candidates) == 14


def test_system_validation_summary():
    items = [
        ("EXPANSION JOINT FIRE BARRIER CERAMIC FIBER 100MM 2 HR", (10.0, 20.0)),
        ("WALL EXPANSION JOINT FIRE BARRIER 150MM 3 HR", (30.0, 40.0)),
        ("SEISMIC JOINT FIRE BARRIER 50MM", (50.0, 60.0)),
    ]
    candidates = extract_expansion_joint_fire_barrier_blanket_candidates(items)
    summary = validate_expansion_joint_fire_barrier_blanket_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["rated_barrier_count"] == 2
    assert summary["specified_width_count"] == 3
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = ExpansionJointFireBarrierBlanketCallout(
        raw_text="SAMPLE",
        barrier_type="CERAMIC_FIBER_FOIL_BLANKET",
        nominal_joint_width_mm=100.0,
        movement_capacity_percent="+/-50%",
        fire_rating_hours="2HR",
        retaining_flange_brackets="GALVANIZED_RETAINING_ANGLES",
        smoke_barrier_layer="INTEGRAL_VAPOR_SMOKE_MEMBRANE",
        joint_orientation="FLOOR_EXPANSION_JOINT",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_expansion_joint_fire_barrier_blanket_candidates([])
    assert len(candidates) == 0
    summary = validate_expansion_joint_fire_barrier_blanket_system([])
    assert summary["total_candidates"] == 0
    assert summary["rated_barrier_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_expansion_joint_fire_barrier_blanket_callout("ALUMINUM EXPANSION JOINT COVER PLATE ONLY") is None
    assert parse_expansion_joint_fire_barrier_blanket_callout("CONCRETE CONTROL JOINT SAWCUT") is None
    assert parse_expansion_joint_fire_barrier_blanket_callout("FIRE BLANKET IN KITCHEN CABINET") is None


def test_roof_expansion_joint_orientation():
    text = "ROOF EXPANSION JOINT FIRE BARRIER 100MM 2 HR"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["joint_orientation"] == "ROOF_EXPANSION_JOINT"
    assert parsed["fire_rating_hours"] == "2HR"


def test_reflex_brand():
    text = "REFLEX SEISMIC JOINT FIRE BARRIER 250MM +/-100%"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["barrier_type"] == "MODULAR_FIRE_BARRIER_SYSTEM"
    assert parsed["nominal_joint_width_mm"] == 250.0
    assert parsed["movement_capacity_percent"] == "+/-100%"


def test_quilted_ceramic_blanket():
    text = "QUILTED CERAMIC FIBER FIRE BARRIER BLANKET 3 HR"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["barrier_type"] == "CERAMIC_FIBER_FOIL_BLANKET"
    assert parsed["fire_rating_hours"] == "3HR"


def test_vapour_barrier_variant():
    text = "EXPANSION JOINT FIRE BARRIER WITH VAPOUR BARRIER MEMBRANE"
    parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
    assert parsed is not None
    assert parsed["smoke_barrier_layer"] == "INTEGRAL_VAPOR_SMOKE_MEMBRANE"
