"""
Unit and adversarial test suite for Source Acoustic Ceiling Baffle Suspended Absorber Shadow Authority.
"""

import pytest
from pb_source_acoustic_ceiling_baffle_shadow import (
    AcousticCeilingBaffleCallout,
    SourceAcousticCeilingBaffleShadowAuthority,
    parse_acoustic_ceiling_baffle_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_pet_baffle_complete():
    text = "CEILING BAFFLE: 24MM PET POLYESTER ACOUSTIC BAFFLE, 2400X300MM, NRC 0.85, SUSPENDED ON ADJUSTABLE AIRCRAFT CABLE @ 300MM CTS"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "POLYESTER_FIBER_PET"
    assert res["baffle_thickness_mm"] == 24.0
    assert res["baffle_dimensions_mm"] == (2400.0, 300.0)
    assert res["nrc_sound_absorption"] == 0.85
    assert res["suspension_method"] == "ADJUSTABLE_AIRCRAFT_WIRE"
    assert res["center_spacing_mm"] == 300.0


def test_parse_timber_slat_baffle():
    text = "ACOUSTIC CEILING BLADE: TIMBER SLAT PERFORATED VENEER 2400X200MM, NRC 0.75, THREADED ROD SUSPENSION AT 200MM CENTRES"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "TIMBER_SLAT_PERFORATED"
    assert res["baffle_dimensions_mm"] == (2400.0, 200.0)
    assert res["nrc_sound_absorption"] == 0.75
    assert res["suspension_method"] == "THREADED_ROD_SUSPENSION"
    assert res["center_spacing_mm"] == 200.0


def test_parse_aluminium_micro_perf_baffle():
    text = "SUSPENDED BAFFLE: ALUMINIUM BAFFLE MICRO-PERFORATED WITH UNISTRUT CHANNEL FIXING @ 400MM PITCH"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "ALUMINIUM_BAFFLE_MICRO_PERF"
    assert res["suspension_method"] == "DIRECT_UNISTRUT_CHANNEL"
    assert res["center_spacing_mm"] == 400.0


def test_parse_fiberglass_fabric_wrapped():
    text = "ACOUSTIC BAFFLE: 50MM FABRIC WRAPPED GLASSWOOL BAFFLE, 0.95 NRC"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "GLASSWOOL_RESIN_BONDED"
    assert res["baffle_thickness_mm"] == 50.0
    assert res["nrc_sound_absorption"] == 0.95


def test_parse_defaults():
    text = "ACOUSTIC BAFFLE"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "POLYESTER_FIBER_PET"
    assert res["nrc_sound_absorption"] == 0.85
    assert res["baffle_thickness_mm"] == 24.0
    assert res["baffle_dimensions_mm"] == (2400.0, 300.0)
    assert res["suspension_method"] == "ADJUSTABLE_AIRCRAFT_WIRE"
    assert res["center_spacing_mm"] == 300.0


def test_parse_unrelated_text_returns_none():
    assert parse_acoustic_ceiling_baffle_callout("CARPET TILES FINISH") is None
    assert parse_acoustic_ceiling_baffle_callout("SKIRTING BOARD 100MM") is None


def test_snap_point_regular():
    pt = snap_point(16.3, 28.8, snap_tol=2.5)
    assert pt == (17.5, 30.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(16.34, 28.87, snap_tol=0.0)
    assert pt == (16.34, 28.87)


def test_authority_processing_batch():
    auth = SourceAcousticCeilingBaffleShadowAuthority()
    candidates = [
        ("ACOUSTIC BAFFLE 2400X300", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("PET BAFFLE CEILING", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].baffle_material == "POLYESTER_FIBER_PET"


def test_safety_primitive_cap():
    auth = SourceAcousticCeilingBaffleShadowAuthority()
    large_list = [("ACOUSTIC BAFFLE", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = AcousticCeilingBaffleCallout(
        raw_text="SAMPLE",
        baffle_material="POLYESTER_FIBER_PET",
        nrc_sound_absorption=0.85,
        baffle_thickness_mm=24.0,
        baffle_dimensions_mm=(2400.0, 300.0),
        suspension_method="ADJUSTABLE_AIRCRAFT_WIRE",
        center_spacing_mm=300.0,
    )
    with pytest.raises(Exception):
        callout.nrc_sound_absorption = 0.90  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   sound baffle: 12mm pet felt baffle, 1200x200mm, nrc 0.80   "
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_thickness_mm"] == 12.0
    assert res["baffle_dimensions_mm"] == (1200.0, 200.0)
    assert res["nrc_sound_absorption"] == 0.80


def test_autex_brand_mapping():
    text = "SUSPENDED CEILING BAFFLE: AUTEX FRONTIER 24MM"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "POLYESTER_FIBER_PET"
    assert res["baffle_thickness_mm"] == 24.0


def test_echopanel_brand_mapping():
    text = "HANGING BAFFLE: ECHOPANEL 12MM BAFFLE SYSTEM"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "POLYESTER_FIBER_PET"
    assert res["baffle_thickness_mm"] == 12.0


def test_custom_snap_tolerance():
    auth = SourceAcousticCeilingBaffleShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("ACOUSTIC BAFFLE", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceAcousticCeilingBaffleShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_gripple_wire_suspension():
    text = "ACOUSTIC BLADES WITH GRIPPLE SUSPENSION WIRE"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["suspension_method"] == "ADJUSTABLE_AIRCRAFT_WIRE"


def test_m8_threaded_rod():
    text = "CEILING BAFFLE ON M8 ROD SUSPENSION"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["suspension_method"] == "THREADED_ROD_SUSPENSION"


def test_baffle_ceiling_trigger():
    text = "BAFFLE CEILING SYSTEM AT 150MM CENTRES"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["center_spacing_mm"] == 150.0


def test_metal_baffle_trigger():
    text = "SUSPENDED BAFFLE: METAL BAFFLE SYSTEM"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_material"] == "ALUMINIUM_BAFFLE_MICRO_PERF"


def test_adversarial_special_characters():
    text = "ACOUSTIC BAFFLE @@@ [PET 24MM] +++ (2400X400MM) // NRC 0.90 *** @ 300MM CTS ###"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_thickness_mm"] == 24.0
    assert res["baffle_dimensions_mm"] == (2400.0, 400.0)
    assert res["nrc_sound_absorption"] == 0.90
    assert res["center_spacing_mm"] == 300.0


def test_40mm_thickness():
    text = "SOUND BAFFLE: 40MM THICKNESS ACOUSTIC BAFFLE"
    res = parse_acoustic_ceiling_baffle_callout(text)
    assert res is not None
    assert res["baffle_thickness_mm"] == 40.0

