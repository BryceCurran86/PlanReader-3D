"""Tests for Vertical Transportation Machine-Room-Less (MRL) Traction Elevator Pit & Buffer Spring Shadow Authority."""

import pytest
from pb_source_mrl_elevator_pit_buffer_spring_shadow import (
    MRLElevatorPitCandidate,
    extract_mrl_elevator_pit_items,
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


def test_mrl_elevator_pit_complete():
    texts = [{
        "id": "lift_1",
        "text": "LIFT-01 Passenger Elevator Pit 1600mm Deep Speed 1.6 m/s Capacity 1000 kg with Retractable Pit Ladder",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "LIFT-01"
    assert c.element_type == "ELEVATOR_PIT"
    assert c.pit_depth_mm == 1600
    assert c.rated_speed_mps == 1.6
    assert c.rated_load_kg == 1000
    assert c.buffer_technology == "HYDRAULIC_OIL"
    assert c.has_retractable_ladder is True


def test_hydraulic_oil_car_buffer():
    texts = [{
        "id": "lift_2",
        "text": "BUF-02 Elevator Car Buffer Hydraulic Oil Energy Dissipation Type for 2.0 m/s Speed",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "BUF-02"
    assert c.element_type == "CAR_BUFFER"
    assert c.buffer_technology == "HYDRAULIC_OIL"
    assert c.rated_speed_mps == 2.0


def test_counterweight_buffer():
    texts = [{
        "id": "lift_3",
        "text": "CWT-03 Counterweight Buffer Assembly with Steel Support Pedestal in Lift Pit",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "COUNTERWEIGHT_BUFFER"


def test_energy_accumulation_spring_buffer():
    texts = [{
        "id": "lift_4",
        "text": "BUF-04 Coil Spring Buffer Energy Accumulation for 1.0 m/s Speed Lift",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.buffer_technology == "ENERGY_ACCUMULATION_SPRING"
    assert c.rated_speed_mps == 1.0


def test_polyurethane_cellular_buffer():
    texts = [{
        "id": "lift_5",
        "text": "BUF-05 Polyurethane Cellular Plastic Buffer under Elevator Car",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.buffer_technology == "POLYURETHANE_CELLULAR"


def test_guide_rail_bracket():
    texts = [{
        "id": "lift_6",
        "text": "EL-06 Guide Rail Bracket Anchored to Concrete Shaft Wall",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "GUIDE_RAIL_BRACKET"


def test_fixed_pit_ladder():
    texts = [{
        "id": "lift_7",
        "text": "PIT-07 Galvanized Steel Pit Ladder with Electrical Safety Interlock Switch",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "PIT_LADDER"
    assert c.has_retractable_ladder is False


def test_pit_drainage_sump():
    texts = [{
        "id": "lift_8",
        "text": "PIT-08 Elevator Pit Sump Box 600x600x600mm with Grate Cover",
        "coordinates": (120.0, 130.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "PIT_SUMP"


def test_negative_lookalike_platform_lift():
    texts = [{
        "id": "neg_1",
        "text": "DDA Platform Lift for Disability Wheelchair Access",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_dumbwaiter():
    texts = [{
        "id": "neg_2",
        "text": "Food Dumbwaiter Electric Hoist 100kg",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_escalator():
    texts = [{
        "id": "neg_3",
        "text": "Escalator Pit Lower Truss Landing Support",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "lift_9",
        "text": "LIFT-09 MRL Lift Pit",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "lift_10",
        "text": "LIFT-10: 1600kg Rated Load MRL Elevator Pit 1800mm Deep",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "LIFT-10"
    assert d["rated_load_kg"] == 1600
    assert d["pit_depth_mm"] == 1800
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"lift_{i}", "text": "LIFT-01 Elevator Pit", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_mrl_elevator_pit_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_mrl_elevator_pit_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Plasterboard lining 13mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "lift_def",
        "text": "Traction Elevator Pit Enclosure",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "LIFT-PIT"
    assert c.element_type == "ELEVATOR_PIT"
    assert c.buffer_technology == "HYDRAULIC_OIL"
    assert c.has_retractable_ladder is False


def test_high_speed_2_5mps():
    texts = [{
        "id": "lift_hs",
        "text": "LIFT-11 High Speed Passenger Elevator 2.5 m/s 1350 kg Pit Depth 2100mm",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.rated_speed_mps == 2.5
    assert c.rated_load_kg == 1350
    assert c.pit_depth_mm == 2100
    assert c.buffer_technology == "HYDRAULIC_OIL"


def test_goods_lift_load_3000kg():
    texts = [{
        "id": "lift_goods",
        "text": "EL-12 Goods Service Lift 3000 kg Rated Load 1.0 m/s",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_mrl_elevator_pit_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.rated_load_kg == 3000
    assert c.rated_speed_mps == 1.0
    assert c.buffer_technology == "ENERGY_ACCUMULATION_SPRING"
