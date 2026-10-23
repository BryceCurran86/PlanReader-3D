"""
Unit and adversarial test suite for Source Acoustic Floating Floor Sylomer Isolation Bearing Pad Shadow Authority.
"""

import pytest
from pb_source_acoustic_sylomer_bearing_pad_shadow import (
    AcousticSylomerBearingPadCallout,
    SourceAcousticSylomerBearingPadShadowAuthority,
    parse_acoustic_sylomer_bearing_pad_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_sylomer_sr55_complete():
    text = "FLOATING SLAB: SYLOMER SR 55 BEARING PADS (100X100MM), 25MM THICK PAD, 8.0 HZ NATURAL FREQUENCY, 50MM AIR CAVITY, PERIMETER ISOLATION STRIP"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR55"
    assert res["static_range_n_per_mm2"] == 0.055
    assert res["pad_thickness_mm"] == 25.0
    assert res["pad_dimensions_mm"] == (100.0, 100.0)
    assert res["natural_frequency_hz"] == 8.0
    assert res["air_cavity_depth_mm"] == 50.0
    assert res["perimeter_isolation"] == "PERIMETER_ISOLATION_STRIP"


def test_parse_sylomer_sr11_soft():
    text = "ACOUSTIC FLOATING FLOOR: SYLOMER SR 11 PADS 50X50MM, 12.5MM THICK, 6.5 HZ"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR11"
    assert res["static_range_n_per_mm2"] == 0.011
    assert res["pad_thickness_mm"] == 12.5
    assert res["pad_dimensions_mm"] == (50.0, 50.0)
    assert res["natural_frequency_hz"] == 6.5


def test_parse_sylodyn_high_load():
    text = "PLANT ROOM FLOATING FLOOR: SYLODYN BEARING PADS 50MM THICK WITH RESILIENT SEALANT AT EDGES"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLODYN_NC"
    assert res["static_range_n_per_mm2"] == 1.200
    assert res["pad_thickness_mm"] == 50.0
    assert res["perimeter_isolation"] == "RESILIENT_CAULKING"


def test_parse_sylomer_strip():
    text = "FLOATING FLOOR: SYLOMER SR 28 75MM STRIP ISOLATION WITH 100MM AIR VOID"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR28"
    assert res["static_range_n_per_mm2"] == 0.028
    assert res["pad_dimensions_mm"] == (75.0, 1000.0)
    assert res["air_cavity_depth_mm"] == 100.0


def test_parse_defaults():
    text = "ACOUSTIC FLOATING FLOOR"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR55"
    assert res["pad_thickness_mm"] == 25.0
    assert res["pad_dimensions_mm"] == (100.0, 100.0)
    assert res["natural_frequency_hz"] == 8.0
    assert res["air_cavity_depth_mm"] == 50.0
    assert res["perimeter_isolation"] == "PERIMETER_ISOLATION_STRIP"


def test_parse_unrelated_text_returns_none():
    assert parse_acoustic_sylomer_bearing_pad_callout("FIRE SPRINKLER HEAD DN20") is None
    assert parse_acoustic_sylomer_bearing_pad_callout("ALUMINIUM BALUSTRADE POST") is None


def test_snap_point_regular():
    pt = snap_point(17.3, 29.8, snap_tol=2.5)
    assert pt == (17.5, 30.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(17.34, 29.87, snap_tol=0.0)
    assert pt == (17.34, 29.87)


def test_authority_processing_batch():
    auth = SourceAcousticSylomerBearingPadShadowAuthority()
    candidates = [
        ("SYLOMER SR 55 PADS", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("ACOUSTIC FLOATING FLOOR SR 110", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].sylomer_grade == "SYLOMER_SR110"


def test_safety_primitive_cap():
    auth = SourceAcousticSylomerBearingPadShadowAuthority()
    large_list = [("SYLOMER PADS", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = AcousticSylomerBearingPadCallout(
        raw_text="SAMPLE",
        sylomer_grade="SYLOMER_SR55",
        static_range_n_per_mm2=0.055,
        pad_thickness_mm=25.0,
        pad_dimensions_mm=(100.0, 100.0),
        natural_frequency_hz=8.0,
        air_cavity_depth_mm=50.0,
        perimeter_isolation="PERIMETER_ISOLATION_STRIP",
    )
    with pytest.raises(Exception):
        callout.natural_frequency_hz = 10.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   sylomer sr 42 pads: 25mm thick, 10 hz   "
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR42"
    assert res["static_range_n_per_mm2"] == 0.042
    assert res["natural_frequency_hz"] == 10.0


def test_sylomer_sr18_grade():
    text = "FLOATING SLAB WITH SYLOMER SR 18 ELASTOMER PADS"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR18"
    assert res["static_range_n_per_mm2"] == 0.018


def test_sylomer_sr220_heavy_duty():
    text = "FLOATING CONCRETE FLOOR: SYLOMER SR 220 ISOLATION PADS"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR220"
    assert res["static_range_n_per_mm2"] == 0.220


def test_sylomer_sr450():
    text = "ACOUSTIC ISOLATION BEARING: SYLOMER SR 450"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR450"
    assert res["static_range_n_per_mm2"] == 0.450


def test_sylomer_sr850():
    text = "RESILIENT FLOOR PAD: SYLOMER SR 850 HEAVY DUTY"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR850"
    assert res["static_range_n_per_mm2"] == 0.850


def test_custom_snap_tolerance():
    auth = SourceAcousticSylomerBearingPadShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("SYLOMER PADS", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceAcousticSylomerBearingPadShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_no_perimeter_strip_negation():
    text = "FLOATING SLAB PADS WITHOUT PERIMETER STRIP"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["perimeter_isolation"] == "NONE"


def test_adversarial_special_characters():
    text = "SYLOMER @@@ [SR 55] +++ (150X150MM) // 25MM THICK *** 8HZ ###"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["sylomer_grade"] == "SYLOMER_SR55"
    assert res["pad_dimensions_mm"] == (150.0, 150.0)
    assert res["pad_thickness_mm"] == 25.0
    assert res["natural_frequency_hz"] == 8.0


def test_flanking_edge_strip():
    text = "FLOATING FLOOR PADS WITH FLANKING STRIP AT PERIMETER WALLS"
    res = parse_acoustic_sylomer_bearing_pad_callout(text)
    assert res is not None
    assert res["perimeter_isolation"] == "PERIMETER_ISOLATION_STRIP"

