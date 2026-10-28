"""Tests for Stormwater Bioretention Raingarden & Saturated Zone Shadow Authority."""

import pytest
from pb_source_bioretention_raingarden_filter_media_shadow import (
    BioretentionRaingardenCandidate,
    extract_bioretention_raingardens,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_bioretention_basin():
    data = [{
        "id": "b1",
        "text": "BIO-01 BIORETENTION BASIN 600MM FILTER MEDIA 100MM TRANSITION SAND LAYER 150MM DRAINAGE GRAVEL LAYER 200MM PONDING DN100 SLOTTED UNDERDRAIN",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].element_type == "BIORETENTION_BASIN"
    assert res[0].tag == "BIO-01"
    assert res[0].filter_media_depth_mm == 600
    assert res[0].transition_layer_depth_mm == 100
    assert res[0].drainage_layer_depth_mm == 150
    assert res[0].ponding_depth_mm == 200
    assert res[0].underdrain_pipe_mm == 100
    assert res[0].has_saturated_zone is False


def test_raingarden_cell_with_saturated_zone():
    data = [{
        "id": "b2",
        "text": "RG-02 RAINGARDEN CELL 500MM BIORETENTION MEDIA WITH 450MM SATURATED ZONE AND DN150 PERFORATED AG PIPE",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].element_type == "RAINGARDEN_CELL"
    assert res[0].tag == "RG-02"
    assert res[0].filter_media_depth_mm == 500
    assert res[0].has_saturated_zone is True
    assert res[0].saturated_zone_depth_mm == 450
    assert res[0].underdrain_pipe_mm == 150


def test_tree_pit_biofilter():
    data = [{
        "id": "b3",
        "text": "TREE-01 TREE PIT BIOFILTER 800MM FILTER MEDIA",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].element_type == "TREE_PIT_BIOFILTER"
    assert res[0].tag == "TREE-01"
    assert res[0].filter_media_depth_mm == 800


def test_vegetated_swale():
    data = [{
        "id": "b4",
        "text": "SWALE-01 VEGETATED SWALE WITH 400MM BIORETENTION FILTER MEDIA",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].element_type == "VEGETATED_SWALE"
    assert res[0].tag == "SWALE-01"
    assert res[0].filter_media_depth_mm == 400


def test_anoxic_zone_detection():
    data = [{
        "id": "b5",
        "text": "BIORETENTION BASIN WITH ANOXIC ZONE FOR DENITRIFICATION",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].has_saturated_zone is True


def test_internal_water_storage_iws():
    data = [{
        "id": "b6",
        "text": "RAINGARDEN WITH INTERNAL WATER STORAGE IWS",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].has_saturated_zone is True


def test_max_ponding_depth():
    data = [{
        "id": "b7",
        "text": "BIORETENTION WITH 300MM MAX PONDING",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].ponding_depth_mm == 300


def test_drainage_aggregate_layer():
    data = [{
        "id": "b8",
        "text": "RAINGARDEN CELL 200MM DRAINAGE AGGREGATE LAYER",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].drainage_layer_depth_mm == 200


def test_transition_sand_layer():
    data = [{
        "id": "b9",
        "text": "BIOFILTER 150MM TRANSITION SAND LAYER",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].transition_layer_depth_mm == 150


def test_slotted_pvc_underdrain():
    data = [{
        "id": "b10",
        "text": "BIORETENTION 100MM SLOTTED UNDERDRAIN",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].underdrain_pipe_mm == 100


def test_negative_grease_trap():
    data = [{"id": "n1", "text": "TRADE WASTE GREASE TRAP 1500L", "coordinates": (0.0, 0.0)}]
    assert len(extract_bioretention_raingardens(data)) == 0


def test_negative_septic_tank():
    data = [{"id": "n2", "text": "SEPTIC DRAINFIELD EFFLUENT PIPE", "coordinates": (0.0, 0.0)}]
    assert len(extract_bioretention_raingardens(data)) == 0


def test_negative_plantroom_louver():
    data = [{"id": "n3", "text": "PLANTROOM LOUVER 300MM DEEP", "coordinates": (0.0, 0.0)}]
    assert len(extract_bioretention_raingardens(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((29.9, 59.8), tolerance=2.5)
    assert pt == (30.0, 60.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "RG-1 RAINGARDEN", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_bioretention_raingardens(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = BioretentionRaingardenCandidate(
        item_id="cand_1",
        element_type="BIORETENTION_BASIN",
        tag="BIO-01",
        filter_media_depth_mm=600,
        transition_layer_depth_mm=100,
        drainage_layer_depth_mm=150,
        ponding_depth_mm=200,
        has_saturated_zone=True,
        saturated_zone_depth_mm=450,
        underdrain_pipe_mm=100,
        coordinates=(10.0, 20.0),
        raw_text="BIO-01 BASIN",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = BioretentionRaingardenCandidate(
        item_id="cand_2",
        element_type="RAINGARDEN_CELL",
        tag="RG-02",
        filter_media_depth_mm=500,
        transition_layer_depth_mm=None,
        drainage_layer_depth_mm=None,
        ponding_depth_mm=None,
        has_saturated_zone=False,
        saturated_zone_depth_mm=None,
        underdrain_pipe_mm=None,
        coordinates=(0.0, 0.0),
        raw_text="RG-02 RAINGARDEN",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "b11",
        "text": "RG-05 RAINGARDEN CELL 600MM FILTER MEDIA",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_bioretention_raingardens(data)
    d = res[0].to_dict()
    assert d["tag"] == "RG-05"
    assert d["filter_media_depth_mm"] == 600
    assert d["status"] == "CANDIDATE"


def test_br_tag_detection():
    data = [{
        "id": "b12",
        "text": "BR-03 BIO-RETENTION BASIN 700MM FILTER MEDIA",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].tag == "BR-03"
    assert res[0].filter_media_depth_mm == 700


def test_submerged_zone_depth():
    data = [{
        "id": "b13",
        "text": "BIORETENTION CELL WITH 500MM SUBMERGED ZONE",
        "coordinates": (20.0, 40.0)
    }]
    res = extract_bioretention_raingardens(data)
    assert len(res) == 1
    assert res[0].saturated_zone_depth_mm == 500
    assert res[0].has_saturated_zone is True
