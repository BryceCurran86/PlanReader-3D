"""
tests/test_source_retaining_wall_geocomposite_strip_drain_shadow.py

Comprehensive test suite for civil retaining wall perforated corrugated strip drains,
geocomposite sheet drainage, and subsoil collector shadow authority.
"""

import pytest
from pb_source_retaining_wall_geocomposite_strip_drain_shadow import (
    StripDrainCandidate,
    extract_strip_drain_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_geocomposite_dimple_sheet_extraction():
    prims = [{
        "id": "p1",
        "text": "Geocomposite Dimpled Sheet Drainage GCS-01 1200mm Wide 10mm Thick 600 kPa on Basement Wall",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "GEOCOMPOSITE_DIMPLE_SHEET"
    assert cand.width_mm == 1200
    assert cand.core_thickness_mm == 10
    assert cand.compressive_strength_kpa == 600
    assert cand.tag == "GCS-01"
    assert cand.filter_fabric == "NON_WOVEN_GEOTEXTILE"
    assert cand.installation_orientation == "VERTICAL_WALL"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_perforated_strip_drain_megaflo():
    prims = [{
        "id": "p2",
        "text": "Megaflo 300mm Perforated Strip Drain SD-02 with Non-Woven Geotextile Sleeve",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "PERFORATED_STRIP_DRAIN"
    assert cand.width_mm == 300
    assert cand.tag == "SD-02"


def test_ag_pipe_slotted():
    prims = [{
        "id": "p3",
        "text": "DN100 Slotted Ag Pipe with Polyester Filter Sock Invert Trench AGP-1",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "AGRICULTURAL_AG_PIPE"
    assert cand.filter_fabric == "POLYESTER_FILTER_SOCK"
    assert cand.installation_orientation == "SLOPE_TO_INVERT"
    assert cand.tag == "AGP-1"


def test_retaining_wall_weephole():
    prims = [{
        "id": "p4",
        "text": "Through-wall 50mm Weep-Hole assembly WEEP-04 at 1200 crs",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "DISCHARGE_WEEPHOLE_ASSEMBLY"
    assert cand.tag == "WEEP-04"
    assert cand.filter_fabric == "NONE"


def test_horizontal_deck_orientation():
    prims = [{
        "id": "p5",
        "text": "Miradrain Dimple Sheet Horizontal Deck Drainage Plaza Slab",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.installation_orientation == "HORIZONTAL_DECK"


def test_woven_monofilament_filter():
    prims = [{
        "id": "p6",
        "text": "Strip Drain SD-05 with Woven Monofilament Filter Fabric 400 L/min",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    assert results[0].filter_fabric == "WOVEN_MONOFILAMENT"
    assert results[0].flow_capacity_l_min_m == 400


def test_negative_lookalike_shower_strip_drain():
    prims = [{
        "id": "neg1",
        "text": "Ensuite Bathroom Shower Strip Drain Stainless Grate",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_strip_drain_candidates(prims) == []


def test_negative_lookalike_roof_gutter():
    prims = [{
        "id": "neg2",
        "text": "Box Roof Gutter with Strip Drainage Overflow",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_strip_drain_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 12.3, 27.6
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 12.5
    assert snapped[1] == 27.5


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Strip Drain SD-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_strip_drain_candidates(prims)


def test_empty_primitive_list():
    assert extract_strip_drain_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Concrete Footing 600x400 C30", "x": 0.0, "y": 0.0}
    ]
    assert extract_strip_drain_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Strip Drain SD-01", "x": 10.0, "y": 20.0}]
    cand = extract_strip_drain_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "VERIFIED"


def test_collector_discharge_outlet():
    prims = [{
        "id": "p8",
        "text": "Strip Drain Collector Discharge Outlet Adaptor to Stormwater Pit",
        "x": 15.0,
        "y": 30.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    assert results[0].element_type == "COLLECTOR_DISCHARGE_OUTLET"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Strip Drain SD_12", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Geocomposite Sheet GCS-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Subsoil Pipe AG_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "SD_12"
    assert results[1].tag == "GCS-04"
    assert results[2].tag == "AG_2"


def test_flow_rate_extraction():
    prims = [{
        "id": "f1",
        "text": "Geocomposite Drainage Sheet 350 L/min Flow Capacity",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_strip_drain_candidates(prims)[0]
    assert cand.flow_capacity_l_min_m == 350


def test_compressive_strength_extraction():
    prims = [{
        "id": "s1",
        "text": "Dimpled Sheet 800 kPa Compressive Resistance",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_strip_drain_candidates(prims)[0]
    assert cand.compressive_strength_kpa == 800


def test_default_values_when_unspecified():
    prims = [{"id": "d1", "text": "Retaining Wall Strip Drain", "x": 0.0, "y": 0.0}]
    cand = extract_strip_drain_candidates(prims)[0]
    assert cand.width_mm == 300
    assert cand.core_thickness_mm == 18
    assert cand.flow_capacity_l_min_m == 250
    assert cand.compressive_strength_kpa == 600
    assert cand.tag is None


def test_confidence_scoring_variations():
    prims_simple = [{"id": "c1", "text": "Strip Drain", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Strip Drain SD-01 800 kPa 350 L/min",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_strip_drain_candidates(prims_simple)[0]
    cand_rich = extract_strip_drain_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Strip Drain SD-1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Strip Drain SD-2", "x": 10.0, "y": 10.0}
    ]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_width_mm_override():
    prims = [{
        "id": "w1",
        "text": "Retaining wall strip drain 450mm wide",
        "x": 0.0,
        "y": 0.0
    }]
    results = extract_strip_drain_candidates(prims)
    assert len(results) == 1
    assert results[0].width_mm == 450
