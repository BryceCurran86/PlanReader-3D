"""
tests/test_source_louvered_sunshade_aerofoil_cantilever_shadow.py

Comprehensive test suite for architectural louvered sunshades, horizontal aerofoil
cantilevers, vertical solar fins, motorized tracking louvers, and outrigger brackets.
"""

import pytest
from pb_source_louvered_sunshade_aerofoil_cantilever_shadow import (
    LouveredSunshadeCandidate,
    extract_louvered_sunshade_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_horizontal_cantilever_sunshade_extraction():
    prims = [{
        "id": "p1",
        "text": "Horizontal Louvered Sunshade Canopy SS-01 200mm Aerofoil Blade 900mm Projection 45° Tilt Powder Coated",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "HORIZONTAL_CANTILEVER_SUNSHADE"
    assert cand.blade_width_mm == 200
    assert cand.projection_outreach_mm == 900
    assert cand.blade_tilt_angle_deg == 45
    assert cand.blade_profile == "AEROFOIL_ELLIPTICAL"
    assert cand.finish_type == "POWDER_COATED_DURATEC"
    assert cand.is_motorized is False
    assert cand.tag == "SS-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_vertical_aerofoil_solar_fin():
    prims = [{
        "id": "p2",
        "text": "Vertical Solar Fin SF-02 300mm Aerofoil Fin Anodized Finish",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "VERTICAL_AEROFOIL_SOLAR_FIN"
    assert cand.blade_width_mm == 300
    assert cand.finish_type == "ANODIZED_25UM"
    assert cand.blade_tilt_angle_deg == 90
    assert cand.tag == "SF-02"


def test_motorized_operable_solar_louver():
    prims = [{
        "id": "p3",
        "text": "Motorized Operable Solar Louver AFL-03 250mm Blade 24V Linear Actuator Tracking",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "MOTORIZED_ELECTRIC_OPERABLE_SOLAR_LOUVER"
    assert cand.blade_width_mm == 250
    assert cand.is_motorized is True
    assert cand.tag == "AFL-03"


def test_structural_outrigger_bracket():
    prims = [{
        "id": "p4",
        "text": "Sunshade Structural Outrigger Bracket OB-04 1200mm Outreach Aluminum Knife Plate",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "STRUCTURAL_OUTRIGGER_BRACKET"
    assert cand.projection_outreach_mm == 1200
    assert cand.tag == "OB-04"


def test_continuous_linear_facade_louver():
    prims = [{
        "id": "p5",
        "text": "Continuous Linear Facade Louver Screen Plant Deck LOU-05 Z-Blade Profile",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CONTINUOUS_LINEAR_FACADE_LOUVER"
    assert cand.blade_profile == "Z_BLADE"
    assert cand.tag == "LOU-05"


def test_timber_grain_finish():
    prims = [{
        "id": "p6",
        "text": "Architectural Sunshade with Timber Grain Sublimation Finish",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 1
    assert results[0].finish_type == "TIMBER_GRAIN_SUBLIMATION"


def test_negative_lookalike_acoustic_louver():
    prims = [{
        "id": "neg1",
        "text": "Acoustic Louver 300mm Deep Plant Room Air Intake",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_louvered_sunshade_candidates(prims) == []


def test_negative_lookalike_interior_venetian():
    prims = [{
        "id": "neg2",
        "text": "Interior Venetian Blind 25mm Aluminum Slats",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_louvered_sunshade_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Sunshade SS-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_louvered_sunshade_candidates(prims)


def test_empty_primitives():
    assert extract_louvered_sunshade_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Carpet Underlay Foam 10mm Standard", "x": 0.0, "y": 0.0}
    ]
    assert extract_louvered_sunshade_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Sunshade SS-01", "x": 10.0, "y": 20.0}]
    cand = extract_louvered_sunshade_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Sunshade SS_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Aerofoil Louver AFL-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Solar Fin SF_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "SS_10"
    assert results[1].tag == "AFL-04"
    assert results[2].tag == "SF_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Sunshade Canopy", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Sunshade SS-01 200mm Aerofoil 900mm Projection",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_louvered_sunshade_candidates(prims_simple)[0]
    cand_rich = extract_louvered_sunshade_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Architectural Sunshade Canopy", "x": 0.0, "y": 0.0}]
    cand = extract_louvered_sunshade_candidates(prims)[0]
    assert cand.blade_width_mm == 200
    assert cand.projection_outreach_mm == 900
    assert cand.blade_tilt_angle_deg == 45
    assert cand.blade_profile == "AEROFOIL_ELLIPTICAL"
    assert cand.finish_type == "POWDER_COATED_DURATEC"
    assert cand.is_motorized is False
    assert cand.tag is None


def test_rectangular_box_blade():
    prims = [{
        "id": "bx1",
        "text": "Solar Shade with 150x50 Rectangular Box Blade",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_louvered_sunshade_candidates(prims)[0]
    assert cand.blade_profile == "RECTANGULAR_BOX"


def test_tilt_angle_30_deg():
    prims = [{
        "id": "ta1",
        "text": "Aerofoil Sunshade 30° Tilt SS-12",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_louvered_sunshade_candidates(prims)[0]
    assert cand.blade_tilt_angle_deg == 30


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Sunshade 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Sunshade 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_louvered_sunshade_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_projection_1500mm():
    prims = [{
        "id": "pr1",
        "text": "Sunshade Canopy 1500mm Projection Cantilever",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_louvered_sunshade_candidates(prims)[0]
    assert cand.projection_outreach_mm == 1500


def test_blade_width_350mm():
    prims = [{
        "id": "bw1",
        "text": "Aerofoil Louver 350mm Blade SS-25",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_louvered_sunshade_candidates(prims)[0]
    assert cand.blade_width_mm == 350
