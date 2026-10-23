"""
Tests for Source Acoustic Floating Wall Resilient Base Angle Isolator Shadow Authority.
"""

import pytest
from pb_source_acoustic_wall_resilient_base_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    AcousticWallResilientBaseCallout,
    snap_point,
    parse_acoustic_wall_resilient_base_callout,
    extract_acoustic_wall_resilient_base_candidates,
    validate_acoustic_wall_resilient_base_system,
)


def test_snap_point_regular():
    pt = snap_point(10.2, 14.8, snap_tol=2.5)
    assert pt == (10.0, 15.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(10.2, 14.8, snap_tol=0.0)
    assert pt == (10.2, 14.8)


def test_parse_none_on_irrelevant_text():
    assert parse_acoustic_wall_resilient_base_callout("CONCRETE STAIR TREAD NOSING") is None
    assert parse_acoustic_wall_resilient_base_callout("ALUMINUM WINDOW FLASHING") is None
    assert parse_acoustic_wall_resilient_base_callout("CEILING ACCESS PANEL 600X600") is None


def test_parse_continuous_sylomer_base_strip():
    text = "CONTINUOUS 25MM SYLOMER BASE STRIP UNDER BOTTOM TRACK WITH DUAL BEAD ACOUSTIC CAULKING - STC 55"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "CONTINUOUS_ELASTOMERIC_STRIP"
    assert parsed["elastomer_material"] == "SYLOMER"
    assert parsed["thickness_mm"] == 25.0
    assert parsed["acoustic_sealant"] == "DUAL_BEAD_ACOUSTIC_CAULKING"
    assert parsed["acoustic_rating"] == "STC55"
    assert parsed["wall_subtype"] == "DRYWALL_STUD_TRACK"


def test_parse_resilient_base_angle_bracket():
    text = "RESILIENT BASE ANGLE ISOLATOR BRACKET AT 600MM C/C WITH NEOPRENE BUSHING AND WASHER TO ANCHOR BOLTS"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "RESILIENT_BASE_ANGLE_BRACKET"
    assert parsed["elastomer_material"] == "NEOPRENE"
    assert parsed["spacing_mm"] == "600MM C/C"
    assert parsed["fastener_decoupling"] == "NEOPRENE_BUSHING_WASHER"


def test_parse_cinema_acoustic_double_stud_wall():
    text = "CINEMA BARRIER DOUBLE STUD ACOUSTIC WALL BASE WITH 50MM REGUPOL ELASTOMER STRIP, 8 HZ NATURAL FREQUENCY, 5MM DEFLECTION"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["wall_subtype"] == "CINEMA_BARRIER"
    assert parsed["elastomer_material"] == "REGUPOL"
    assert parsed["thickness_mm"] == 50.0
    assert parsed["natural_frequency_hz"] == 8.0
    assert parsed["deflection_mm"] == 5.0


def test_parse_masonry_block_acoustic_base():
    text = "ACOUSTIC WALL BASE ISOLATION UNDER CMU MASONRY BLOCKWORK WALL WITH CONTINUOUS ELASTOMERIC STRIP"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["wall_subtype"] == "MASONRY_BLOCK_BASE"
    assert parsed["isolator_type"] == "CONTINUOUS_ELASTOMERIC_STRIP"


def test_parse_sway_brace_base_channel():
    text = "FLOATING WALL BASE DEFLECTION CHANNEL WITH ACOUSTIC SLEEVE FASTENERS AND NON-HARDENING ACOUSTIC MASTIC"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "SWAY_BRACE_BASE_CHANNEL"
    assert parsed["fastener_decoupling"] == "ACOUSTIC_SLEEVE"
    assert parsed["acoustic_sealant"] == "NON_HARDENING_MASTIC"


def test_parse_discrete_mount_block():
    text = "DISCRETE SYLOMER MOUNT BLOCKS AT 400MM CTS UNDER DECOUPLED SOLE PLATE"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "DISCRETE_MOUNT_BLOCK"
    assert parsed["elastomer_material"] == "SYLOMER"
    assert parsed["spacing_mm"] == "400MM C/C"


def test_parse_rw_ctr_rating():
    text = "STUD TRACK ISOLATOR WITH ACOUSTIC SEALANT - RW + CTR 52"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["acoustic_rating"] == "RW+CTR52"
    assert parsed["acoustic_sealant"] == "SINGLE_BEAD_ACOUSTIC_SEALANT"


def test_parse_polyurethane_pur():
    text = "WALL BASE ISOLATOR PUR ELASTOMER 15MM THICK 10 HZ"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["elastomer_material"] == "POLYURETHANE"
    assert parsed["thickness_mm"] == 15.0
    assert parsed["natural_frequency_hz"] == 10.0


def test_parse_natural_rubber_isolated_anchor():
    text = "PERIMETER ISOLATION STRIP NATURAL RUBBER WITH ISOLATED ANCHOR BOLTS"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["elastomer_material"] == "NATURAL_RUBBER"
    assert parsed["fastener_decoupling"] == "ISOLATED_ANCHOR_BOLT"


def test_extract_acoustic_wall_resilient_base_candidates():
    items = [
        ("CONTINUOUS 25MM SYLOMER BASE STRIP UNDER BOTTOM TRACK - STC 58", (100.1, 200.4)),
        ("ROOF FLASHING DETAIL", (50.0, 50.0)),
        ("RESILIENT BASE ANGLE ISOLATOR BRACKET AT 600MM C/C", (300.0, 400.0)),
    ]
    candidates = extract_acoustic_wall_resilient_base_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (100.0, 200.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"CONTINUOUS SYLOMER BASE STRIP {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_acoustic_wall_resilient_base_candidates(items, max_cap=10)
    assert len(candidates) == 10


def test_system_validation_summary():
    items = [
        ("CONTINUOUS 25MM SYLOMER BASE STRIP UNDER BOTTOM TRACK WITH DUAL BEAD ACOUSTIC CAULKING", (10.0, 20.0)),
        ("RESILIENT BASE ANGLE BRACKET WITH NEOPRENE BUSHING AND WASHER", (30.0, 40.0)),
        ("DISCRETE MOUNT BLOCK CMU MASONRY WALL BASE", (50.0, 60.0)),
    ]
    candidates = extract_acoustic_wall_resilient_base_candidates(items)
    summary = validate_acoustic_wall_resilient_base_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["isolated_fasteners_count"] == 1
    assert summary["sealed_bases_count"] == 1
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_epdm_material_detection():
    text = "ACOUSTIC SOLE PLATE EPDM ISOLATOR STRIP 12.5MM"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["elastomer_material"] == "EPDM"
    assert parsed["thickness_mm"] == 12.5


def test_continuous_spacing_flag():
    text = "WALL PERIMETER ISOLATION STRIP CONTINUOUS WITH ACOUSTIC CAULK"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["spacing_mm"] == "CONTINUOUS"
    assert parsed["acoustic_sealant"] == "SINGLE_BEAD_ACOUSTIC_SEALANT"


def test_candidate_dataclass_immutability():
    cand = AcousticWallResilientBaseCallout(
        raw_text="SAMPLE",
        isolator_type="CONTINUOUS_ELASTOMERIC_STRIP",
        elastomer_material="SYLOMER",
        thickness_mm=25.0,
        natural_frequency_hz=8.0,
        deflection_mm=3.0,
        spacing_mm="CONTINUOUS",
        fastener_decoupling="NEOPRENE_BUSHING_WASHER",
        acoustic_sealant="DUAL_BEAD_ACOUSTIC_CAULKING",
        wall_subtype="DRYWALL_STUD_TRACK",
        acoustic_rating="STC55",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"  # Frozen dataclass


def test_empty_input_handling():
    candidates = extract_acoustic_wall_resilient_base_candidates([])
    assert len(candidates) == 0
    summary = validate_acoustic_wall_resilient_base_system([])
    assert summary["total_candidates"] == 0
    assert summary["isolated_fasteners_count"] == 0


def test_adversarial_partial_substrings():
    # Make sure text mentioning baseline or wall without acoustic isolation trigger returns None
    assert parse_acoustic_wall_resilient_base_callout("CONCRETE SLAB BASEMENT WALL") is None
    assert parse_acoustic_wall_resilient_base_callout("STANDARD TIMBER STUD WALL") is None
    assert parse_acoustic_wall_resilient_base_callout("WALL BASEBOARD SKIRTING TILES") is None


def test_double_bead_acoustic_caulking():
    text = "DECOUPLED SOLE PLATE WITH DOUBLE BEAD ACOUSTIC SEALANT"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["acoustic_sealant"] == "DUAL_BEAD_ACOUSTIC_CAULKING"


def test_natural_frequency_decimal():
    text = "RESILIENT BASE ANGLE ISOLATOR 6.5 HZ NATURAL FREQUENCY"
    parsed = parse_acoustic_wall_resilient_base_callout(text)
    assert parsed is not None
    assert parsed["natural_frequency_hz"] == 6.5
