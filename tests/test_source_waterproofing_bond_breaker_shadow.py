"""
Unit and adversarial test suite for Source Wet Area Waterproofing Membrane & Bond Breaker Fillet Shadow Authority.
"""

import pytest
from pb_source_waterproofing_bond_breaker_shadow import (
    WaterproofingBondBreakerCallout,
    SourceWaterproofingBondBreakerShadowAuthority,
    parse_waterproofing_bond_breaker_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_waterproofing():
    text = "ENSUITE SHOWER: CLASS III HIGH EXTENSIBILITY LIQUID POLYURETHANE MEMBRANE, 1.2MM DFT, 12X12MM POLYURETHANE COVE FILLET BOND BREAKER, 1800MM UPTURN AT WALL JUNCTIONS, MASONRY HOB WATERPROOFED"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["membrane_class"] == "CLASS_III_HIGH_EXTENSIBILITY_LIQUID"
    assert res["bond_breaker_type"] == "ELASTOMERIC_POLYURETHANE_COVE_FILLET"
    assert res["fillet_size_mm"] == 12.0
    assert res["upturn_height_mm"] == 1800.0
    assert res["dry_film_thickness_dft_mm"] == 1.2
    assert res["hob_detail"] == "MASONRY_HOB_WATERPROOFED"


def test_parse_silicone_fillet():
    text = "BATHROOM PERIMETER: 10MM NEUTRAL CURE SILICONE FILLET BOND BREAKER, 150MM UPTURN, FLUSH RECESS STEPDOWN"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["bond_breaker_type"] == "NEUTRAL_CURE_SILICONE_FILLET"
    assert res["fillet_size_mm"] == 10.0
    assert res["upturn_height_mm"] == 150.0
    assert res["hob_detail"] == "FLUSH_RECESS_STEPDOWN"


def test_parse_sheet_membrane():
    text = "BALCONY WATERPROOFING: PREFORMED PVC SHEET MEMBRANE, 1.5MM DFT, REINFORCING BOND BREAKER TAPE, 300MM UPTURN"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["membrane_class"] == "PREFORMED_SHEET_MEMBRANE"
    assert res["bond_breaker_type"] == "REINFORCING_BOND_BREAKER_TAPE"
    assert res["upturn_height_mm"] == 300.0
    assert res["dry_film_thickness_dft_mm"] == 1.5


def test_parse_defaults():
    text = "WET AREA MEMBRANE"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["membrane_class"] == "CLASS_III_HIGH_EXTENSIBILITY_LIQUID"
    assert res["fillet_size_mm"] == 12.0
    assert res["dry_film_thickness_dft_mm"] == 1.2


def test_parse_non_waterproofing():
    text = "TIMBER SKIRTING BOARD 67X18MM"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(44.9, 88.1, snap_tol=2.5)
    assert pt == (45.0, 87.5)


def test_authority_processing_dedup():
    auth = SourceWaterproofingBondBreakerShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("WATERPROOFING MEMBRANE 12MM FILLET", (10.0, 20.0)),
        ("WATERPROOFING MEMBRANE 12MM FILLET", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceWaterproofingBondBreakerShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("WATERPROOFING MEMBRANE 12MM FILLET", (10.0, 20.0)),
        ("WATERPROOFING MEMBRANE 12MM FILLET", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceWaterproofingBondBreakerShadowAuthority()
    oversized = [("WATERPROOFING", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceWaterproofingBondBreakerShadowAuthority()
    res = auth.process_callouts([("WATERPROOFING MEMBRANE", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_waterproofing_bond_breaker_callout("") is None


def test_zero_tolerance_snap():
    pt = snap_point(21.21, 42.42, snap_tol=0.0)
    assert pt == (21.21, 42.42)


def test_frozen_dataclass_immutability():
    callout = WaterproofingBondBreakerCallout(
        raw_text="text",
        membrane_class="CLASS_III",
        bond_breaker_type="FILLET",
        fillet_size_mm=12.0,
        upturn_height_mm=150.0,
        dry_film_thickness_dft_mm=1.2,
        hob_detail="STEPDOWN",
    )
    with pytest.raises(Exception):
        callout.fillet_size_mm = 20.0  # type: ignore


def test_different_classes_same_point():
    auth = SourceWaterproofingBondBreakerShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("CLASS II WATERPROOFING", (10.0, 20.0)),
        ("CLASS III WATERPROOFING", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_hobless_level_threshold():
    text = "SHOWER WATERPROOFING WITH HOBLESS LEVEL THRESHOLD"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["hob_detail"] == "NO_HOB_LEVEL_THRESHOLD"


def test_class_ii_medium_extensibility():
    text = "CLASS II WATERPROOF MEMBRANE"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["membrane_class"] == "CLASS_II_MEDIUM_EXTENSIBILITY"


def test_cove_fillet_trigger():
    text = "15X15 COVE FILLET AT WALL JUNCTION"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["fillet_size_mm"] == 15.0


def test_membrane_upturn_trigger():
    text = "MEMBRANE UPTURN 200MM ABOVE FINISHED TILE"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["upturn_height_mm"] == 200.0


def test_dft_parsing():
    text = "WATERPROOFING 2.0MM DFT"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["dry_film_thickness_dft_mm"] == 2.0


def test_balcony_waterproofing_trigger():
    text = "BALCONY WATERPROOFING WITH 150MM UPTURN"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["upturn_height_mm"] == 150.0


def test_bond_breaker_tape_keyword():
    text = "WATERPROOFING WITH BOND BREAKER TAPE"
    res = parse_waterproofing_bond_breaker_callout(text)
    assert res is not None
    assert res["bond_breaker_type"] == "REINFORCING_BOND_BREAKER_TAPE"
