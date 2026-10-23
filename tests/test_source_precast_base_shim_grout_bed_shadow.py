"""
Unit and adversarial test suite for Source Precast Concrete Panel Base Shim Pack & Structural Grout Bed Shadow Authority.
"""

import pytest
from pb_source_precast_base_shim_grout_bed_shadow import (
    PrecastBaseShimGroutBedCallout,
    SourcePrecastBaseShimGroutBedShadowAuthority,
    parse_precast_base_shim_grout_bed_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_plastic_horseshoe_shim_flowable():
    text = "PRECAST PANEL BASE: 20MM GROUT BED WITH PLASTIC HORSESHOE SHIMS (100X100MM), 65MPA FLOWABLE GROUT, FOAM BACKER ROD"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_bed_thickness_mm"] == 20.0
    assert res["shim_pack_type"] == "PLASTIC_HORSESHOE_SHIM"
    assert res["shim_dimensions_mm"] == (100.0, 100.0)
    assert res["grout_strength_mpa"] == 65.0
    assert res["grout_placement_method"] == "FLOWABLE_FLUID_GROUT"
    assert res["containment_backer"] == "FOAM_BACKER_ROD"


def test_parse_steel_packer_dry_pack():
    text = "PANEL BASE JOINT: 50MM BEDDING GROUT, STEEL PACKER PLATES 150*100MM, DRY PACK MORTAR 80MPA, TIMBER STOP"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_bed_thickness_mm"] == 50.0
    assert res["shim_pack_type"] == "STEEL_PACKER_PLATE"
    assert res["shim_dimensions_mm"] == (150.0, 100.0)
    assert res["grout_strength_mpa"] == 80.0
    assert res["grout_placement_method"] == "DRY_PACK_MORTAR"
    assert res["containment_backer"] == "TIMBER_STOP"


def test_parse_elastomeric_bearing_pad():
    text = "PRECAST WALL BASE: 30MM NON-SHRINK GROUT BED WITH ELASTOMERIC BEARING PAD AND GROUT FOAM TAPE"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_bed_thickness_mm"] == 30.0
    assert res["shim_pack_type"] == "ELASTOMERIC_BEARING_PAD"
    assert res["containment_backer"] == "GROUT_FOAM_TAPE"


def test_parse_pressure_pumped():
    text = "BASE GROUT: 25MM GAP, HIGH-DENSITY LEVELLING SHIM PACK, PRESSURE PUMPED NON-SHRINK GROUT 70MPA"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_bed_thickness_mm"] == 25.0
    assert res["grout_placement_method"] == "PRESSURE_PUMPED_GROUT"
    assert res["grout_strength_mpa"] == 70.0


def test_parse_class_c_grout_default_strength():
    text = "PANEL BASE 25MM GROUT BED WITH CLASS C DUAL-EXPANSION GROUT AND LEVELLING SHIMS"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_strength_mpa"] == 70.0


def test_parse_default_strength_and_dims():
    text = "PRECAST PANEL BASE GROUT BED 20MM THICKNESS WITH SHIMS"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["shim_dimensions_mm"] == (100.0, 100.0)
    assert res["grout_strength_mpa"] == 60.0
    assert res["containment_backer"] == "UNSPECIFIED"


def test_parse_unrelated_text_returns_none():
    assert parse_precast_base_shim_grout_bed_callout("ALUMINUM FRAMED WINDOW GLAZING") is None
    assert parse_precast_base_shim_grout_bed_callout("SUSPENDED CEILING GRID 1200X600") is None


def test_snap_point_regular():
    pt = snap_point(12.3, 14.8, snap_tol=2.5)
    assert pt == (12.5, 15.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(12.34, 56.78, snap_tol=0.0)
    assert pt == (12.34, 56.78)


def test_authority_processing_batch():
    auth = SourcePrecastBaseShimGroutBedShadowAuthority()
    candidates = [
        ("PRECAST PANEL BASE: 20MM GROUT BED WITH PLASTIC HORSESHOE SHIMS", (10.1, 20.2)),
        ("UNRELATED TEXT NOTE", (30.0, 40.0)),
        ("PANEL BASE 40MM GROUT BED WITH STEEL PACKER PLATES 80MPA", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].grout_bed_thickness_mm == 40.0


def test_safety_primitive_cap():
    auth = SourcePrecastBaseShimGroutBedShadowAuthority()
    large_list = [("PRECAST PANEL BASE GROUT BED 25MM WITH SHIMS", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = PrecastBaseShimGroutBedCallout(
        raw_text="SAMPLE",
        grout_bed_thickness_mm=25.0,
        shim_pack_type="PLASTIC_HORSESHOE_SHIM",
        shim_dimensions_mm=(100.0, 100.0),
        grout_strength_mpa=60.0,
        grout_placement_method="FLOWABLE_FLUID_GROUT",
        containment_backer="FOAM_BACKER_ROD",
    )
    with pytest.raises(Exception):
        callout.grout_bed_thickness_mm = 30.0  # dataclass is frozen


def test_case_insensitivity_and_whitespace():
    text = "   precast panel base: 35mm bedding grout with plastic shims and foam backer rod   "
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_bed_thickness_mm"] == 35.0
    assert res["shim_pack_type"] == "PLASTIC_HORSESHOE_SHIM"
    assert res["containment_backer"] == "FOAM_BACKER_ROD"


def test_adversarial_steel_keyword_isolation():
    # Ensure reinforcing steel notes do not falsely flip horseshoe shims to steel packer plates
    text = "PRECAST PANEL BASE: 20MM GROUT BED WITH PLASTIC HORSESHOE SHIMS (REINFORCING STEEL DOWELS CAST INTO FOUNDATION)"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["shim_pack_type"] == "PLASTIC_HORSESHOE_SHIM"


def test_adversarial_special_characters():
    text = "PANEL BASE @ GROUT BED [25MM] +++ HIGH STRENGTH (65 MPA) NON-SHRINK GROUT // SHIMS ***"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_bed_thickness_mm"] == 25.0
    assert res["grout_strength_mpa"] == 65.0
    assert res["shim_pack_type"] == "HIGH_DENSITY_PLASTIC_SHIM"


def test_custom_snap_tolerance():
    auth = SourcePrecastBaseShimGroutBedShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("PANEL BASE 25MM GROUT BED WITH SHIMS", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourcePrecastBaseShimGroutBedShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_rammed_dry_pack_mortar():
    text = "PANEL BASE 30MM BEDDING WITH RAMMED MORTAR 60MPA"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_placement_method"] == "DRY_PACK_MORTAR"


def test_gravity_flow_fluid_grout():
    text = "PANEL BASE JOINT: 25MM GROUT BED, GRAVITY FLOW NON-SHRINK GROUT WITH TIMBER FORMWORK STOP"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["grout_placement_method"] == "FLOWABLE_FLUID_GROUT"
    assert res["containment_backer"] == "TIMBER_STOP"


def test_polypropylene_horseshoe_shim():
    text = "PANEL BASE: 20MM GROUT BED WITH POLYPROPYLENE SHIMS"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["shim_pack_type"] == "PLASTIC_HORSESHOE_SHIM"


def test_generic_packer_fallback():
    text = "PANEL BASE: 25MM GROUT BED WITH PACKER LEVELLING SYSTEM"
    res = parse_precast_base_shim_grout_bed_callout(text)
    assert res is not None
    assert res["shim_pack_type"] == "HIGH_DENSITY_PLASTIC_SHIM"

