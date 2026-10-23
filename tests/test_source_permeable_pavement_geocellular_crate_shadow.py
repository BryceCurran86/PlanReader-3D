"""Tests for Stormwater Permeable Pavement & Geocellular Crate Shadow Authority."""

import pytest
from pb_source_permeable_pavement_geocellular_crate_shadow import (
    PermeableStormwaterCandidate,
    extract_permeable_stormwater_items,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_permeable_paver():
    data = [{
        "id": "p1",
        "text": "PP-01 PERMEABLE INTERLOCKING CONCRETE PAVERS ON 150MM OPEN GRADED SUBBASE",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].system_type == "PERMEABLE_PAVERS"
    assert res[0].tag == "PP-01"
    assert res[0].subbase_depth_mm == 150


def test_geocellular_crate_tank():
    data = [{
        "id": "p2",
        "text": "OSTA-01 MODULAR GEOCELLULAR ATTENUATION CRATE TANK 120M3 WITH 95% VOID",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].system_type == "GEOCELLULAR_CRATES"
    assert res[0].tag == "OSTA-01"
    assert res[0].storage_volume_m3 == 120.0
    assert res[0].void_ratio_percent == 95.0


def test_porous_asphalt():
    data = [{
        "id": "p3",
        "text": "POROUS ASPHALT WEARING COURSE OVER 200MM CRUSHED ROCK SUBBASE",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].system_type == "POROUS_ASPHALT"
    assert res[0].subbase_depth_mm == 200


def test_pervious_concrete():
    data = [{
        "id": "p4",
        "text": "PERVIOUS CONCRETE PAVEMENT 20% VOID FOR PEDESTRIAN WALKWAY",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].system_type == "PERVIOUS_CONCRETE"
    assert res[0].void_ratio_percent == 20.0
    assert res[0].traffic_loading == "LIGHT_PEDESTRIAN"


def test_impermeable_geomembrane_liner():
    data = [{
        "id": "p5",
        "text": "GEOCELLULAR CRATE TANK WRAPPED IN 1.0MM HDPE IMPERMEABLE GEOMEMBRANE LINER",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].system_type == "GEOCELLULAR_CRATES"
    assert res[0].liner_type == "IMPERMEABLE_GEOMEMBRANE"


def test_non_woven_geotextile_filter():
    data = [{
        "id": "p6",
        "text": "PERMEABLE PAVING WRAPPED IN NON-WOVEN GEOTEXTILE FILTER FABRIC",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].liner_type == "NON_WOVEN_GEOTEXTILE"


def test_heavy_vehicle_loading():
    data = [{
        "id": "p7",
        "text": "PERMEABLE PAVERS CLASS D HEAVY VEHICLE LOADING",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].traffic_loading == "HEAVY_VEHICLE"


def test_medium_car_park_loading():
    data = [{
        "id": "p8",
        "text": "CAR PARK PERMEABLE PAVING TRAFFIC RATED",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].traffic_loading == "MEDIUM_CAR_PARK"


def test_geocellular_default_void_ratio():
    data = [{
        "id": "p9",
        "text": "GEOCELLULAR ATTENUATION CRATE 50M3",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].storage_volume_m3 == 50.0
    assert res[0].void_ratio_percent == 95.0


def test_picp_tag_detection():
    data = [{
        "id": "p10",
        "text": "PICP-02 PERMEABLE PAVING 100MM BEDDING",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].tag == "PICP-02"
    assert res[0].subbase_depth_mm == 100


def test_negative_standard_asphalt():
    data = [{"id": "n1", "text": "STANDARD ASPHALT DRIVEWAY 50MM", "coordinates": (0.0, 0.0)}]
    assert len(extract_permeable_stormwater_items(data)) == 0


def test_negative_concrete_slab():
    data = [{"id": "n2", "text": "IMPERMEABLE CONCRETE SLAB 150MM", "coordinates": (0.0, 0.0)}]
    assert len(extract_permeable_stormwater_items(data)) == 0


def test_negative_roof_membrane():
    data = [{"id": "n3", "text": "ROOF MEMBRANE WATERPROOFING", "coordinates": (0.0, 0.0)}]
    assert len(extract_permeable_stormwater_items(data)) == 0


def test_negative_retaining_wall():
    data = [{"id": "n4", "text": "CONCRETE CRIB RETAINING WALL", "coordinates": (0.0, 0.0)}]
    assert len(extract_permeable_stormwater_items(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((24.9, 49.8), tolerance=2.5)
    assert pt == (25.0, 50.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "PP-1 PERMEABLE PAVING", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_permeable_stormwater_items(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = PermeableStormwaterCandidate(
        item_id="cand_1",
        system_type="PERMEABLE_PAVERS",
        tag="PP-01",
        subbase_depth_mm=150,
        storage_volume_m3=None,
        void_ratio_percent=None,
        liner_type="NON_WOVEN_GEOTEXTILE",
        traffic_loading="MEDIUM_CAR_PARK",
        coordinates=(10.0, 20.0),
        raw_text="PP-01 PERMEABLE PAVING",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = PermeableStormwaterCandidate(
        item_id="cand_2",
        system_type="GEOCELLULAR_CRATES",
        tag="OSTA-01",
        subbase_depth_mm=None,
        storage_volume_m3=100.0,
        void_ratio_percent=95.0,
        liner_type="IMPERMEABLE_GEOMEMBRANE",
        traffic_loading="HEAVY_VEHICLE",
        coordinates=(0.0, 0.0),
        raw_text="OSTA-01 CRATES",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "p11",
        "text": "PP-05 PERMEABLE PAVERS ON 150MM SUBBASE",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_permeable_stormwater_items(data)
    d = res[0].to_dict()
    assert d["tag"] == "PP-05"
    assert d["system_type"] == "PERMEABLE_PAVERS"
    assert d["subbase_depth_mm"] == 150
    assert d["status"] == "CANDIDATE"


def test_cubic_meters_spelling():
    data = [{
        "id": "p12",
        "text": "GEOCELLULAR INFILTRATION CRATE 75.5 CUBIC METRES",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_permeable_stormwater_items(data)
    assert len(res) == 1
    assert res[0].storage_volume_m3 == 75.5
