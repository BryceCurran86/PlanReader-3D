"""Tests for Hydronic Underfloor Heating Manifold & Actuated Circuit Loop Shadow Authority."""

import pytest
from pb_source_hydronic_underfloor_heating_manifold_loop_shadow import (
    HydronicManifoldCandidate,
    extract_hydronic_manifolds,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_ufh_manifold():
    data = [{
        "id": "h1",
        "text": "UFH-01 UNDERFLOOR HEATING MANIFOLD 8 CIRCUITS WITH 16MM PEX-A AND 24V ACTUATORS",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].manifold_tag == "UFH-01"
    assert res[0].circuit_count == 8
    assert res[0].pipe_material == "PEX_A"
    assert res[0].pipe_diameter_mm == 16
    assert res[0].has_thermal_actuators is True
    assert res[0].actuator_voltage == "24V"


def test_recessed_cabinet_and_flow_meters():
    data = [{
        "id": "h2",
        "text": "HYDRONIC MANIFOLD 6 WAY WITH SIGHT GLASS FLOW METERS IN RECESSED FLUSH CABINET",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].circuit_count == 6
    assert res[0].has_flow_meters is True
    assert res[0].enclosure_type == "RECESSED_CABINET"


def test_mixing_shunt_station():
    data = [{
        "id": "h3",
        "text": "RADIANT HEATING MANIFOLD 10 PORT WITH PUMP SET MIXING SHUNT GROUP",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].circuit_count == 10
    assert res[0].has_mixing_shunt is True


def test_surface_mounted_box():
    data = [{
        "id": "h4",
        "text": "UFH MANIFOLD 4 LOOPS SURFACE MOUNTED BOX",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].circuit_count == 4
    assert res[0].enclosure_type == "SURFACE_MOUNTED"


def test_pex_al_pex_pipe():
    data = [{
        "id": "h5",
        "text": "UNDERFLOOR HEATING MANIFOLD WITH 20MM PEX-AL-PEX MULTI-LAYER PIPE",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].pipe_material == "PEX_AL_PEX"
    assert res[0].pipe_diameter_mm == 20


def test_pert_pipe():
    data = [{
        "id": "h6",
        "text": "IN-SLAB HEATING MANIFOLD 12 PORT WITH 16MM PE-RT PIPE",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].pipe_material == "PERT"
    assert res[0].pipe_diameter_mm == 16
    assert res[0].circuit_count == 12


def test_230v_actuators():
    data = [{
        "id": "h7",
        "text": "HM-02 HYDRONIC MANIFOLD WITH 230V ELECTRO-THERMAL ZONE ACTUATORS",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].manifold_tag == "HM-02"
    assert res[0].has_thermal_actuators is True
    assert res[0].actuator_voltage == "230V"


def test_balancing_indicators():
    data = [{
        "id": "h8",
        "text": "IN-SCREED HEATING MANIFOLD WITH BALANCING INDICATOR FLOW VALVES",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].has_flow_meters is True


def test_cooling_manifold():
    data = [{
        "id": "h9",
        "text": "RADIANT COOLING MANIFOLD 6 CIRCUITS",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].circuit_count == 6


def test_tempering_valve():
    data = [{
        "id": "h10",
        "text": "UNDERFLOOR HEATING MANIFOLD WITH TEMPERING VALVE",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].has_mixing_shunt is True


def test_negative_gas_manifold():
    data = [{"id": "n1", "text": "GAS MANIFOLD WITH DUAL REGULATORS", "coordinates": (0.0, 0.0)}]
    assert len(extract_hydronic_manifolds(data)) == 0


def test_negative_sprinkler_manifold():
    data = [{"id": "n2", "text": "FIRE SPRINKLER MANIFOLD DN100", "coordinates": (0.0, 0.0)}]
    assert len(extract_hydronic_manifolds(data)) == 0


def test_negative_potable_water():
    data = [{"id": "n3", "text": "POTABLE WATER MANIFOLD TO BATHROOMS", "coordinates": (0.0, 0.0)}]
    assert len(extract_hydronic_manifolds(data)) == 0


def test_negative_expansion_vessel():
    data = [{"id": "n4", "text": "EXPANSION VESSEL ONLY 50L", "coordinates": (0.0, 0.0)}]
    assert len(extract_hydronic_manifolds(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((27.4, 52.6), tolerance=2.5)
    assert pt == (27.5, 52.5)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "UFH-1 UNDERFLOOR HEATING MANIFOLD", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_hydronic_manifolds(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = HydronicManifoldCandidate(
        item_id="cand_1",
        manifold_tag="UFH-01",
        circuit_count=8,
        pipe_material="PEX_A",
        pipe_diameter_mm=16,
        has_thermal_actuators=True,
        actuator_voltage="24V",
        has_flow_meters=True,
        enclosure_type="RECESSED_CABINET",
        has_mixing_shunt=False,
        coordinates=(10.0, 20.0),
        raw_text="UFH-01 MANIFOLD",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = HydronicManifoldCandidate(
        item_id="cand_2",
        manifold_tag="UFH-02",
        circuit_count=6,
        pipe_material="STANDARD",
        pipe_diameter_mm=None,
        has_thermal_actuators=False,
        actuator_voltage=None,
        has_flow_meters=False,
        enclosure_type="STANDARD",
        has_mixing_shunt=False,
        coordinates=(0.0, 0.0),
        raw_text="UFH-02 MANIFOLD",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "h11", "text": "UFH-05 UNDERFLOOR HEATING MANIFOLD 6 CIRCUITS", "coordinates": (30.0, 40.0)}]
    res = extract_hydronic_manifolds(data)
    d = res[0].to_dict()
    assert d["manifold_tag"] == "UFH-05"
    assert d["circuit_count"] == 6
    assert d["status"] == "CANDIDATE"


def test_tag_extraction_variant():
    data = [{
        "id": "h12",
        "text": "MAN-3 UNDERFLOOR HEATING 4 CIRCUITS",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_hydronic_manifolds(data)
    assert len(res) == 1
    assert res[0].manifold_tag == "MAN-3"
    assert res[0].circuit_count == 4
