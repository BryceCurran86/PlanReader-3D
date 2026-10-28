"""
tests/test_source_chilled_beam_active_passive_induction_shadow.py

Comprehensive test suite for HVAC active and passive chilled beam induction terminals,
multi-service beams, and exposed architectural hydronic beams.
"""

import pytest
from pb_source_chilled_beam_active_passive_induction_shadow import (
    ChilledBeamCandidate,
    extract_chilled_beam_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_active_chilled_beam_extraction():
    prims = [{
        "id": "p1",
        "text": "Active Chilled Beam ACB-01 2400x600mm 4-Pipe 35 L/s 1500W Cooling",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_chilled_beam_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "ACTIVE_CHILLED_BEAM"
    assert cand.length_mm == 2400
    assert cand.width_mm == 600
    assert cand.pipe_configuration == "4_PIPE_HEATING_COOLING"
    assert cand.primary_air_flow_l_s == 35
    assert cand.cooling_capacity_w == 1500
    assert cand.tag == "ACB-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_passive_chilled_beam_extraction():
    prims = [{
        "id": "p2",
        "text": "Passive Chilled Beam PCB-02 1800x600mm 2-Pipe Convection 800W",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_chilled_beam_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "PASSIVE_CHILLED_BEAM"
    assert cand.length_mm == 1800
    assert cand.primary_air_flow_l_s == 0
    assert cand.pipe_configuration == "2_PIPE_COOLING"
    assert cand.nozzle_configuration == "NONE_PASSIVE"
    assert cand.tag == "PCB-02"


def test_multi_service_chilled_beam():
    prims = [{
        "id": "p3",
        "text": "Multi-Service Beam MSB-03 3000x600mm with Integrated LED Lighting & PIR",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_chilled_beam_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "MULTI_SERVICE_CHILLED_BEAM"
    assert cand.length_mm == 3000
    assert cand.has_integrated_lighting is True
    assert cand.tag == "MSB-03"


def test_exposed_architectural_beam():
    prims = [{
        "id": "p4",
        "text": "Exposed Architectural Chilled Beam CB-04 3600mm Length Perforated Fascia",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_chilled_beam_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "EXPOSED_ARCHITECTURAL_BEAM"
    assert cand.length_mm == 3600
    assert cand.tag == "CB-04"


def test_kw_capacity_parsing():
    prims = [{
        "id": "p5",
        "text": "Active Chilled Beam ACB-05 2.2 kW Cooling Capacity",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_chilled_beam_candidates(prims)
    assert len(results) == 1
    assert results[0].cooling_capacity_w == 2200


def test_negative_lookalike_structural_steel_beam():
    prims = [{
        "id": "neg1",
        "text": "Structural Steel Universal Beam UB 460x82 Grade 300",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_chilled_beam_candidates(prims) == []


def test_negative_lookalike_concrete_transfer_beam():
    prims = [{
        "id": "neg2",
        "text": "Concrete Transfer Beam TB-01 1200x800mm Post-Tensioned",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_chilled_beam_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Chilled Beam ACB-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_chilled_beam_candidates(prims)


def test_empty_primitives():
    assert extract_chilled_beam_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Aluminum Window Frame Glazing Schedule", "x": 0.0, "y": 0.0}
    ]
    assert extract_chilled_beam_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p6", "text": "Chilled Beam ACB-01", "x": 10.0, "y": 20.0}]
    cand = extract_chilled_beam_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Chilled Beam ACB_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Passive Beam PCB-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Multi-Service Beam MSB_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_chilled_beam_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "ACB_10"
    assert results[1].tag == "PCB-04"
    assert results[2].tag == "MSB_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Active Chilled Beam", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Active Chilled Beam ACB-01 2400x600mm 1500W",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_chilled_beam_candidates(prims_simple)[0]
    cand_rich = extract_chilled_beam_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Active Chilled Beam Induction Terminal", "x": 0.0, "y": 0.0}]
    cand = extract_chilled_beam_candidates(prims)[0]
    assert cand.length_mm == 2400
    assert cand.width_mm == 600
    assert cand.cooling_capacity_w == 1200
    assert cand.primary_air_flow_l_s == 25
    assert cand.tag is None
    assert cand.has_integrated_lighting is False


def test_2_pipe_cooling_only():
    prims = [{
        "id": "p7",
        "text": "Active Chilled Beam 2-Pipe Cooling Only ACB-07",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_chilled_beam_candidates(prims)[0]
    assert cand.pipe_configuration == "2_PIPE_COOLING"


def test_integrated_luminaire():
    prims = [{
        "id": "l1",
        "text": "Active Chilled Beam with Luminaire",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_chilled_beam_candidates(prims)[0]
    assert cand.has_integrated_lighting is True


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Chilled Beam 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Chilled Beam 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_chilled_beam_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_width_300mm():
    prims = [{
        "id": "w1",
        "text": "Chilled Beam 1200x300mm ACB-15",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_chilled_beam_candidates(prims)[0]
    assert cand.length_mm == 1200
    assert cand.width_mm == 300


def test_airflow_extraction():
    prims = [{
        "id": "af1",
        "text": "Active Chilled Beam 45 L/s Airflow",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_chilled_beam_candidates(prims)[0]
    assert cand.primary_air_flow_l_s == 45


def test_chilled_word_does_not_trigger_led():
    prims = [{
        "id": "led1",
        "text": "Chilled Beam Standard Non-Lighted",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_chilled_beam_candidates(prims)[0]
    assert cand.has_integrated_lighting is False
