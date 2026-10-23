"""
Unit and adversarial test suite for Source Industrial Concrete Slab Sawcut Dowel Basket Assembly Shadow Authority.
"""

import pytest
from pb_source_slab_dowel_basket_assembly_shadow import (
    SlabDowelBasketAssemblyCallout,
    SourceSlabDowelBasketAssemblyShadowAuthority,
    parse_slab_dowel_basket_assembly_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_dowel_basket_r20_complete():
    text = "SAWCUT CONTRACTION JOINT: PREFABRICATED DOWEL BASKET ASSEMBLY WITH R20 ROUND BARS X 450MM LONG @ 300MM CTS, 200MM SLAB, PLASTIC EXPANSION SLEEVES"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["joint_type"] == "SAWCUT_CONTRACTION_JOINT"
    assert res["dowel_bar_type"] == "ROUND_STEEL_DOWEL_R20"
    assert res["dowel_length_mm"] == 450.0
    assert res["dowel_spacing_mm"] == 300.0
    assert res["slab_thickness_mm"] == 200.0
    assert res["debonding_treatment"] == "PLASTIC_EXPANSION_SLEEVE"


def test_parse_r24_dowel_basket_greased():
    text = "EXPANSION BASKET JOINT: R24 DOWELS 500MM LG AT 450MM CENTRES IN 250MM SLAB, HALF GREASED DEBONDED"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["joint_type"] == "EXPANSION_BASKET_JOINT"
    assert res["dowel_bar_type"] == "ROUND_STEEL_DOWEL_R24"
    assert res["dowel_length_mm"] == 500.0
    assert res["dowel_spacing_mm"] == 450.0
    assert res["slab_thickness_mm"] == 250.0
    assert res["debonding_treatment"] == "HALF_GREASED_DEBONDED"


def test_parse_r16_dowel_cradle():
    text = "DOWEL CRADLE: R16 BARS 400MM LONG @ 300MM PITCH IN 150MM SLAB"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["dowel_bar_type"] == "ROUND_STEEL_DOWEL_R16"
    assert res["dowel_length_mm"] == 400.0
    assert res["dowel_spacing_mm"] == 300.0
    assert res["slab_thickness_mm"] == 150.0


def test_parse_plate_dowel_basket():
    text = "SLAB DOWEL BASKET WITH PLATE DOWELS AND TECTYL COATING"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["dowel_bar_type"] == "PLATE_DOWEL_BASKET"
    assert res["debonding_treatment"] == "TECTYL_COATED"


def test_parse_square_dowel_basket():
    text = "CONTRACTION JOINT BASKET: SQUARE DOWEL BARS AT 350MM CTS"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["dowel_bar_type"] == "SQUARE_DOWEL_BAR"
    assert res["dowel_spacing_mm"] == 350.0


def test_parse_defaults():
    text = "DOWEL BASKET ASSEMBLY"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["joint_type"] == "SAWCUT_CONTRACTION_JOINT"
    assert res["dowel_bar_type"] == "ROUND_STEEL_DOWEL_R20"
    assert res["dowel_spacing_mm"] == 300.0
    assert res["dowel_length_mm"] == 450.0
    assert res["slab_thickness_mm"] == 200.0
    assert res["debonding_treatment"] == "PLASTIC_EXPANSION_SLEEVE"


def test_parse_unrelated_text_returns_none():
    assert parse_slab_dowel_basket_assembly_callout("ALUMINUM FRAMED SKYLIGHT") is None
    assert parse_slab_dowel_basket_assembly_callout("CARPET TILES OVER SCREED") is None


def test_snap_point_regular():
    pt = snap_point(14.3, 27.8, snap_tol=2.5)
    assert pt == (15.0, 27.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(14.34, 27.87, snap_tol=0.0)
    assert pt == (14.34, 27.87)


def test_authority_processing_batch():
    auth = SourceSlabDowelBasketAssemblyShadowAuthority()
    candidates = [
        ("DOWEL BASKET R20 @ 300MM CTS", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("SLAB DOWEL BASKET 250MM SLAB", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].slab_thickness_mm == 250.0


def test_safety_primitive_cap():
    auth = SourceSlabDowelBasketAssemblyShadowAuthority()
    large_list = [("DOWEL BASKET", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = SlabDowelBasketAssemblyCallout(
        raw_text="SAMPLE",
        joint_type="SAWCUT_CONTRACTION_JOINT",
        dowel_bar_type="ROUND_STEEL_DOWEL_R20",
        dowel_spacing_mm=300.0,
        dowel_length_mm=450.0,
        slab_thickness_mm=200.0,
        debonding_treatment="PLASTIC_EXPANSION_SLEEVE",
    )
    with pytest.raises(Exception):
        callout.dowel_spacing_mm = 400.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   sawcut joint basket: r20 dowels at 300mm centres in 175mm slab   "
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["dowel_bar_type"] == "ROUND_STEEL_DOWEL_R20"
    assert res["slab_thickness_mm"] == 175.0


def test_no_sleeve_negation():
    text = "DOWEL BASKET ASSEMBLY WITHOUT SLEEVE"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["debonding_treatment"] == "NONE"


def test_induced_crack_joint_trigger():
    text = "INDUCED CRACK JOINT WITH DOWEL BASKET"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["joint_type"] == "INDUCED_CRACK_JOINT"


def test_longitudinal_hinged_joint():
    text = "LONGITUDINAL HINGED JOINT DOWEL CRADLE"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["joint_type"] == "LONGITUDINAL_HINGED_JOINT"


def test_custom_snap_tolerance():
    auth = SourceSlabDowelBasketAssemblyShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("DOWEL BASKET", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceSlabDowelBasketAssemblyShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_r28_heavy_hardstand():
    text = "CRADLE ASSEMBLY: R28 DOWEL BARS 600MM LG IN 300MM HEAVY INDUSTRIAL SLAB"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["dowel_bar_type"] == "ROUND_STEEL_DOWEL_R28"
    assert res["dowel_length_mm"] == 600.0
    assert res["slab_thickness_mm"] == 300.0


def test_alternate_spacing_notation():
    text = "DOWEL BASKET @ 450 O/C"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["dowel_spacing_mm"] == 450.0


def test_adversarial_special_characters():
    text = "DOWEL BASKET @@@ [SAWCUT] +++ (R20 X 450MM) // @ 300MM CTS *** 200MM SLAB ###"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["joint_type"] == "SAWCUT_CONTRACTION_JOINT"
    assert res["dowel_bar_type"] == "ROUND_STEEL_DOWEL_R20"
    assert res["dowel_length_mm"] == 450.0
    assert res["dowel_spacing_mm"] == 300.0
    assert res["slab_thickness_mm"] == 200.0


def test_cradle_assembly_trigger():
    text = "CRADLE ASSEMBLY WITH DOWELS AT CONTRACTION JOINT"
    res = parse_slab_dowel_basket_assembly_callout(text)
    assert res is not None
    assert res["joint_type"] == "SAWCUT_CONTRACTION_JOINT"
