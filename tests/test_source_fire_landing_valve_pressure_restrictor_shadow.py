"""Tests for Fire Protection Wet / Dry Riser Landing Valve & Pressure Restrictor Shadow Authority."""

import pytest
from pb_source_fire_landing_valve_pressure_restrictor_shadow import (
    FireLandingValveCandidate,
    extract_landing_valves,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_oblique_landing_valve():
    data = [{
        "id": "v1",
        "text": "HLV-01 OBLIQUE FIRE LANDING VALVE DN65 WITH STORZ COUPLING IN RECESSED CABINET",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].valve_tag == "HLV-01"
    assert res[0].valve_pattern == "OBLIQUE"
    assert res[0].inlet_size_mm == 65
    assert res[0].coupling_type == "STORZ"
    assert res[0].cabinet_type == "RECESSED_CABINET"


def test_dry_riser_right_angle_valve():
    data = [{
        "id": "v2",
        "text": "DRY RISER LANDING VALVE RIGHT ANGLE WITH BS336 INSTANTANEOUS COUPLING",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].system_service == "DRY_RISER"
    assert res[0].valve_pattern == "RIGHT_ANGLE"
    assert res[0].coupling_type == "BS336_INSTANTANEOUS"


def test_wet_riser_pressure_reducing_valve():
    data = [{
        "id": "v3",
        "text": "WET RISER OUTLET WITH PRV PRESSURE REDUCING VALVE DN65",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].system_service == "WET_RISER"
    assert res[0].pressure_control == "PRESSURE_REDUCING_VALVE"


def test_pressure_restricting_orifice():
    data = [{
        "id": "v4",
        "text": "HYDRANT LANDING VALVE WITH PRO PRESSURE RESTRICTING DEVICE",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].pressure_control == "RESTRICTING_ORIFICE"


def test_fixed_orifice_plate():
    data = [{
        "id": "v5",
        "text": "FIRE LANDING VALVE WITH FIXED ORIFICE PLATE DN65",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].pressure_control == "FIXED_ORIFICE"


def test_bib_nose_valve_pattern():
    data = [{
        "id": "v6",
        "text": "BIB NOSE FIRE HYDRANT VALVE 65MM",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].valve_pattern == "BIB_NOSE"


def test_nh_thread_coupling():
    data = [{
        "id": "v7",
        "text": "STANDPIPE VALVE WITH 2.5 INCH NH THREAD COUPLING",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].coupling_type == "NH_THREAD"
    assert res[0].inlet_size_mm == 65


def test_surface_mounted_cabinet():
    data = [{
        "id": "v8",
        "text": "FIRE HYDRANT VALVE IN SURFACE MOUNTED CABINET",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].cabinet_type == "SURFACE_CABINET"


def test_combined_standpipe():
    data = [{
        "id": "v9",
        "text": "COMBINED SPRINKLER STANDPIPE LANDING VALVE",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].system_service == "COMBINED_STANDPIPE"


def test_bic_coupling():
    data = [{
        "id": "v10",
        "text": "FIRE LANDING VALVE WITH BIC COUPLING",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].coupling_type == "BIC"


def test_negative_hose_reel():
    data = [{"id": "n1", "text": "FIRE HOSE REEL ONLY 36M", "coordinates": (0.0, 0.0)}]
    assert len(extract_landing_valves(data)) == 0


def test_negative_sprinkler_head():
    data = [{"id": "n2", "text": "CONCEALED PENDENT SPRINKLER HEAD", "coordinates": (0.0, 0.0)}]
    assert len(extract_landing_valves(data)) == 0


def test_negative_gas_solenoid():
    data = [{"id": "n3", "text": "GAS SOLENOID VALVE DN50", "coordinates": (0.0, 0.0)}]
    assert len(extract_landing_valves(data)) == 0


def test_negative_drain_valve():
    data = [{"id": "n4", "text": "DRAIN VALVE ONLY DN25", "coordinates": (0.0, 0.0)}]
    assert len(extract_landing_valves(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((29.9, 59.8), tolerance=2.5)
    assert pt == (30.0, 60.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "HLV-1 FIRE LANDING VALVE", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_landing_valves(items, max_primitives=35)
    assert len(res) == 35


def test_candidate_guardrails_default():
    candidate = FireLandingValveCandidate(
        item_id="cand_1",
        valve_tag="HLV-01",
        valve_pattern="OBLIQUE",
        system_service="WET_RISER",
        inlet_size_mm=65,
        coupling_type="STORZ",
        pressure_control="RESTRICTING_ORIFICE",
        cabinet_type="RECESSED_CABINET",
        coordinates=(10.0, 20.0),
        raw_text="HLV-01 LANDING VALVE",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = FireLandingValveCandidate(
        item_id="cand_2",
        valve_tag="LV-02",
        valve_pattern="RIGHT_ANGLE",
        system_service="DRY_RISER",
        inlet_size_mm=65,
        coupling_type="BS336_INSTANTANEOUS",
        pressure_control="NONE",
        cabinet_type="EXPOSED",
        coordinates=(0.0, 0.0),
        raw_text="LV-02 DRY RISER VALVE",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "v11", "text": "HLV-05 FIRE LANDING VALVE DN65", "coordinates": (30.0, 40.0)}]
    res = extract_landing_valves(data)
    d = res[0].to_dict()
    assert d["valve_tag"] == "HLV-05"
    assert d["inlet_size_mm"] == 65
    assert d["status"] == "CANDIDATE"


def test_valve_tag_detection():
    data = [{"id": "v12", "text": "WRV-02 WET RISER LANDING VALVE", "coordinates": (15.0, 30.0)}]
    res = extract_landing_valves(data)
    assert len(res) == 1
    assert res[0].valve_tag == "WRV-02"
    assert res[0].system_service == "WET_RISER"
