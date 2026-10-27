"""Tests for Civil Subsurface Infiltration Basin & Trench Geocellular Drainage Shadow Authority."""

import pytest
from pb_source_infiltration_basin_soakaway_trench_shadow import (
    InfiltrationBasinCandidate,
    extract_infiltration_basin_items,
    snap_point,
)


def test_snap_point_exact():
    pt = (100.0, 50.0)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 50.0)


def test_snap_point_offset():
    pt = (101.1, 51.9)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 52.5)


def test_geocellular_crate_basin():
    texts = [{
        "id": "inf_1",
        "text": "INF-01 Geocellular Infiltration Crate Basin 45 m3 Capacity wrapped in Non-Woven Geotextile with Inspection Riser",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "INF-01"
    assert c.system_type == "GEOCELLULAR_BASIN"
    assert c.storage_volume_m3 == 45.0
    assert c.geotextile_wrap == "NON_WOVEN_GEOTEXTILE"
    assert c.has_inspection_riser is True


def test_soakaway_gravel_trench():
    texts = [{
        "id": "inf_2",
        "text": "IT-02 Soakaway Trench 1200mm Depth filled with 20-40mm Washed Aggregate wrapped in Geotextile",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "IT-02"
    assert c.system_type == "INFILTRATION_TRENCH"
    assert c.trench_depth_mm == 1200
    assert c.aggregate_grading_desc == "20-40mm"


def test_surface_infiltration_basin():
    texts = [{
        "id": "inf_3",
        "text": "IB-03 Open Surface Infiltration Basin 120 m3 Storage Volume with Sand Filter Base",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "IB-03"
    assert c.system_type == "SURFACE_BASIN"
    assert c.storage_volume_m3 == 120.0


def test_inspection_riser_shaft():
    texts = [{
        "id": "inf_4",
        "text": "INSP-04 Infiltration System Vertical Inspection Riser and Vent Shaft",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.system_type == "INSPECTION_RISER"
    assert c.has_inspection_riser is True


def test_silt_trap_pre_treatment():
    texts = [{
        "id": "inf_5",
        "text": "ST-05 Infiltration Pre-Treatment Silt Trap Catchpit Chamber",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.system_type == "SILT_TRAP"


def test_impermeable_geomembrane_override():
    texts = [{
        "id": "inf_6",
        "text": "INF-06 Infiltration Tank wrapped in Impermeable Geomembrane Base Liner",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.geotextile_wrap == "IMPERMEABLE_GEOMEMBRANE"


def test_aggregate_grading_40_70():
    texts = [{
        "id": "inf_7",
        "text": "SOAK-07 Soakaway Trench with 40-70mm Ballast Aggregate 1500mm Deep",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.aggregate_grading_desc == "40-70mm"
    assert c.trench_depth_mm == 1500


def test_negative_lookalike_osd_tank():
    texts = [{
        "id": "neg_1",
        "text": "Impermeable Detention Tank OSD Tank 150 m3 Concrete",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_septic():
    texts = [{
        "id": "neg_2",
        "text": "Septic Absorption Trench Effluent Disposal Line",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_grease_trap():
    texts = [{
        "id": "neg_3",
        "text": "Trade Waste Grease Trap Interceptor Pit 2000L",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "inf_8",
        "text": "INF-08 Infiltration Trench",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "inf_9",
        "text": "INF-09: Soakaway Crate 30 m3 Volume",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "INF-09"
    assert d["storage_volume_m3"] == 30.0
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"inf_{i}", "text": "INF-01 Soakaway Trench", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_infiltration_basin_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_infiltration_basin_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Bitumen road paving 50mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "inf_def",
        "text": "Infiltration Trench System",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "INF-ITEM"
    assert c.geotextile_wrap == "NON_WOVEN_GEOTEXTILE"
    assert c.has_inspection_riser is False


def test_cubic_meters_spelled_out():
    texts = [{
        "id": "inf_spelled",
        "text": "INF-10 Modular Soakaway 75.5 Cubic Meters Volume",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.storage_volume_m3 == 75.5


def test_blue_metal_aggregate_default():
    texts = [{
        "id": "inf_bm",
        "text": "IT-11 Infiltration Trench with Blue Metal Gravel",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_infiltration_basin_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.aggregate_grading_desc == "20-40mm"
