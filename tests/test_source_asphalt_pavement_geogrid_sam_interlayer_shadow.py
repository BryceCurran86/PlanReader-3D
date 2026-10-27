"""
tests/test_source_asphalt_pavement_geogrid_sam_interlayer_shadow.py

Comprehensive test suite for civil asphalt pavement geogrid reinforcements,
Stress Absorbing Membrane Interlayers (SAMI), glass/carbon fiber grids, and crack bandages.
"""

import pytest
from pb_source_asphalt_pavement_geogrid_sam_interlayer_shadow import (
    PavementGeogridCandidate,
    extract_pavement_geogrid_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_fiberglass_asphalt_geogrid_extraction():
    prims = [{
        "id": "p1",
        "text": "Fiberglass Asphalt Geogrid PGR-01 100 kN/m Tensile Strength 25x25mm Aperture 2.0m Wide Roll Self-Adhesive Backing 250°C",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "FIBERGLASS_ASPHALT_GEOGRID"
    assert cand.ultimate_tensile_strength_kn_m == 100
    assert cand.grid_aperture_mm == 25
    assert cand.roll_width_m == 2.0
    assert cand.has_adhesive_backing is True
    assert cand.temperature_resistance_c == 250
    assert cand.tag == "PGR-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_sami_stress_absorbing_membrane():
    prims = [{
        "id": "p2",
        "text": "SAMI Stress Absorbing Membrane Interlayer Paving Fabric SAMI-02 1.1 L/m2 Bitumen Retention",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "SAMI_STRESS_ABSORBING_MEMBRANE"
    assert cand.bitumen_retention_l_m2 == 1.1
    assert cand.grid_aperture_mm == 0
    assert cand.tag == "SAMI-02"


def test_carbon_fiber_pavement_grid():
    prims = [{
        "id": "p3",
        "text": "Carbon Fiber Pavement Geogrid 200 kN/m High Modulus Bus Lane Overlay PGR-03",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CARBON_FIBER_PAVEMENT_GRID"
    assert cand.ultimate_tensile_strength_kn_m == 200
    assert cand.tag == "PGR-03"


def test_joint_seal_reinforcement_strip():
    prims = [{
        "id": "p4",
        "text": "Self-Adhesive Crack Bandage 500mm Wide Asphalt Joint Reinforcement Strip CRB-04",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "JOINT_SEAL_REINFORCEMENT_STRIP"
    assert cand.roll_width_m == 0.5
    assert cand.tag == "CRB-04"


def test_polypropylene_biaxial_geogrid():
    prims = [{
        "id": "p5",
        "text": "Polypropylene Biaxial Geogrid Subbase Stabilization 50 kN/m PGR-05",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "POLYPROPYLENE_BIAXIAL_GEOGRID"
    assert cand.ultimate_tensile_strength_kn_m == 50


def test_glasgrid_proprietary_name():
    prims = [{
        "id": "p6",
        "text": "GlasGrid 8501 Asphalt Reinforcement Mesh 100 kN/m",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 1
    assert results[0].element_type == "FIBERGLASS_ASPHALT_GEOGRID"


def test_negative_lookalike_turf_grid():
    prims = [{
        "id": "neg1",
        "text": "Turf Grid Plastic Paver for Grass Porous Driveway",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_pavement_geogrid_candidates(prims) == []


def test_negative_lookalike_gabion():
    prims = [{
        "id": "neg2",
        "text": "Gabion Basket Wire Mesh Rock Retaining Wall",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_pavement_geogrid_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Pavement Geogrid PGR-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_pavement_geogrid_candidates(prims)


def test_empty_primitives():
    assert extract_pavement_geogrid_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Kerb and Gutter Extruded Concrete Profile", "x": 0.0, "y": 0.0}
    ]
    assert extract_pavement_geogrid_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Pavement Geogrid PGR-01", "x": 10.0, "y": 20.0}]
    cand = extract_pavement_geogrid_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Pavement Grid PGR_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "SAMI Layer SAMI-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Crack Bandage CRB_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "PGR_10"
    assert results[1].tag == "SAMI-04"
    assert results[2].tag == "CRB_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Pavement Geogrid", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Pavement Geogrid PGR-01 100 kN/m 25x25mm",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_pavement_geogrid_candidates(prims_simple)[0]
    cand_rich = extract_pavement_geogrid_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Asphalt Pavement Geogrid Interlayer", "x": 0.0, "y": 0.0}]
    cand = extract_pavement_geogrid_candidates(prims)[0]
    assert cand.ultimate_tensile_strength_kn_m == 100
    assert cand.grid_aperture_mm == 25
    assert cand.roll_width_m == 2.0
    assert cand.temperature_resistance_c == 250
    assert cand.tag is None


def test_temperature_300c():
    prims = [{
        "id": "tp1",
        "text": "Fiberglass Geogrid with 300C Melt Point",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_pavement_geogrid_candidates(prims)[0]
    assert cand.temperature_resistance_c == 300


def test_aperture_12_5mm():
    prims = [{
        "id": "ap1",
        "text": "Pavement Geogrid 12.5x12.5mm Aperture",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_pavement_geogrid_candidates(prims)[0]
    assert cand.grid_aperture_mm == 12


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Pavement Grid 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Pavement Grid 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_pavement_geogrid_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_roll_width_3_8m():
    prims = [{
        "id": "rw1",
        "text": "Pavement Geogrid 3.8m Wide Roll PGR-15",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_pavement_geogrid_candidates(prims)[0]
    assert cand.roll_width_m == 3.8


def test_tensile_strength_150_kn():
    prims = [{
        "id": "ts1",
        "text": "Asphalt Geogrid 150 kN/m High Strength",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_pavement_geogrid_candidates(prims)[0]
    assert cand.ultimate_tensile_strength_kn_m == 150
