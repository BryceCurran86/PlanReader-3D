"""
Unit and adversarial test suite for Source External Louvered Equipment Screen Plant Deck Shadow Authority.
"""

import pytest
from pb_source_louvered_plant_screen_shadow import (
    LouveredPlantScreenCallout,
    SourceLouveredPlantScreenShadowAuthority,
    parse_louvered_plant_screen_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_continuous_horizontal_screen_complete():
    text = "ROOFTOP PLANT SCREEN: CONTINUOUS HORIZONTAL LOUVERS, 55% FREE AREA, 2400MM HIGH, STEEL SHS POSTS, 100% VISUAL BLOCKAGE, DULUX POWDER COAT"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["screen_profile"] == "CONTINUOUS_HORIZONTAL_LOUVER"
    assert res["blade_free_area_percent"] == 55.0
    assert res["overall_height_mm"] == 2400.0
    assert res["structural_support_post"] == "STEEL_SHS_POST"
    assert res["visual_screening_percent"] == 100.0
    assert res["finish_specification"] == "POWDER_COATED_DULUX"


def test_parse_acoustic_louver_screen():
    text = "MECHANICAL PLANT SCREEN: ACOUSTIC LOUVER SCREEN 3000MM HEIGHT, 45% FREE AREA, HOT DIP GALVANIZED PFC POSTS"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["screen_profile"] == "ACOUSTIC_LOUVER_SCREEN"
    assert res["overall_height_mm"] == 3000.0
    assert res["blade_free_area_percent"] == 45.0
    assert res["structural_support_post"] == "C-CHANNEL_MULLION"
    assert res["finish_specification"] == "HOT_DIP_GALVANIZED"


def test_parse_chevron_visual_screen():
    text = "EQUIPMENT SCREEN: CHEVRON SIGHT PROOF LOUVRE SCREEN, 1800MM HIGH, ALUMINIUM BOX POSTS, ANODIZED 25UM"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["screen_profile"] == "CHEVRON_VISUAL_SCREEN"
    assert res["overall_height_mm"] == 1800.0
    assert res["structural_support_post"] == "ALUMINIUM_BOX_POST"
    assert res["visual_screening_percent"] == 100.0
    assert res["finish_specification"] == "ANODIZED_25UM"


def test_parse_vertical_slat_screen():
    text = "CONDENSER SCREEN: VERTICAL SLAT SCREEN 2100MM HIGH, 60% VENTILATION"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["screen_profile"] == "VERTICAL_SLAT_SCREEN"
    assert res["overall_height_mm"] == 2100.0
    assert res["blade_free_area_percent"] == 60.0


def test_parse_defaults():
    text = "PLANT SCREEN"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["screen_profile"] == "CONTINUOUS_HORIZONTAL_LOUVER"
    assert res["blade_free_area_percent"] == 50.0
    assert res["overall_height_mm"] == 2400.0
    assert res["structural_support_post"] == "STEEL_SHS_POST"
    assert res["visual_screening_percent"] == 100.0
    assert res["finish_specification"] == "POWDER_COATED_DULUX"


def test_parse_unrelated_text_returns_none():
    assert parse_louvered_plant_screen_callout("ALUMINUM INTERNAL DOOR D01") is None
    assert parse_louvered_plant_screen_callout("CARPET TILES OVER UNDERLAY") is None


def test_snap_point_regular():
    pt = snap_point(19.3, 32.8, snap_tol=2.5)
    assert pt == (20.0, 32.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(19.34, 32.87, snap_tol=0.0)
    assert pt == (19.34, 32.87)


def test_authority_processing_batch():
    auth = SourceLouveredPlantScreenShadowAuthority()
    candidates = [
        ("PLANT SCREEN 2400MM HIGH", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("CHILLER SCREEN 3000MM", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].overall_height_mm == 3000.0


def test_safety_primitive_cap():
    auth = SourceLouveredPlantScreenShadowAuthority()
    large_list = [("PLANT SCREEN", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = LouveredPlantScreenCallout(
        raw_text="SAMPLE",
        screen_profile="CONTINUOUS_HORIZONTAL_LOUVER",
        blade_free_area_percent=50.0,
        overall_height_mm=2400.0,
        structural_support_post="STEEL_SHS_POST",
        visual_screening_percent=100.0,
        finish_specification="POWDER_COATED_DULUX",
    )
    with pytest.raises(Exception):
        callout.overall_height_mm = 3000.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   louvered screen: 2400mm high, interpon powder coated   "
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["overall_height_mm"] == 2400.0
    assert res["finish_specification"] == "POWDER_COATED_DULUX"


def test_steel_post_vs_galv_finish_guard():
    # Powder coated aluminium louvers mounted on steel SHS posts must not trigger hot-dip galvanized finish
    text = "EQUIPMENT SCREEN: DULUX POWDER COATED ALUMINIUM LOUVERS ON STEEL SHS POSTS"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["structural_support_post"] == "STEEL_SHS_POST"
    assert res["finish_specification"] == "POWDER_COATED_DULUX"


def test_custom_snap_tolerance():
    auth = SourceLouveredPlantScreenShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("PLANT SCREEN", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceLouveredPlantScreenShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_unistrut_support():
    text = "ROOF SCREEN ON UNISTRUT FRAME 1800MM HIGH"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["structural_support_post"] == "UNISTRUT_FRAME"
    assert res["overall_height_mm"] == 1800.0


def test_mill_finish():
    text = "PLANT DECK SCREEN IN MILL FINISH"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["finish_specification"] == "MILL_FINISH"


def test_80_percent_visual_blockage():
    text = "EQUIPMENT SCREEN: 80% VISUAL BLOCKAGE WITH 50% FREE AREA"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["visual_screening_percent"] == 80.0
    assert res["blade_free_area_percent"] == 50.0


def test_spelling_louvre_screen():
    text = "ROOF LOUVRE SCREEN 2700MM HIGH"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["overall_height_mm"] == 2700.0


def test_rhs_post_support():
    text = "PLANT SCREEN ON RHS STEEL POSTS"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["structural_support_post"] == "STEEL_SHS_POST"


def test_adversarial_special_characters():
    text = "PLANT SCREEN @@@ [2400MM HIGH] +++ (55% FREE AREA) // SHS POSTS *** DULUX ###"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["overall_height_mm"] == 2400.0
    assert res["blade_free_area_percent"] == 55.0
    assert res["structural_support_post"] == "STEEL_SHS_POST"
    assert res["finish_specification"] == "POWDER_COATED_DULUX"


def test_free_area_alt_regex():
    text = "LOUVERED SCREEN: FREE AREA OF 65%"
    res = parse_louvered_plant_screen_callout(text)
    assert res is not None
    assert res["blade_free_area_percent"] == 65.0
