"""Tests for Emergency Diesel Generator Fuel Day Tank & Double-Wall Piping Shadow Authority."""

import pytest
from pb_source_diesel_generator_day_tank_fuel_piping_shadow import (
    GeneratorFuelItemCandidate,
    extract_generator_fuel_items,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_day_tank_extraction():
    data = [{"id": "t1", "text": "1000L SELF-BUNDED DIESEL DAY TANK", "coordinates": (100.2, 200.4)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].element_type == "DAY_TANK"
    assert res[0].capacity_liters == 1000.0
    assert res[0].fuel_type == "DIESEL"
    assert res[0].mounting_bunding == "SELF_BUNDED"
    assert res[0].is_double_wall is True


def test_generator_belly_tank():
    data = [{"id": "t2", "text": "500L BASE-MOUNTED GENERATOR BELLY TANK", "coordinates": (50.0, 75.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].element_type == "BELLY_TANK"
    assert res[0].capacity_liters == 500.0
    assert res[0].mounting_bunding == "BELLY_TANK"


def test_gallon_day_tank_conversion():
    data = [{"id": "t3", "text": "250 GALLON FUEL OIL DAY TANK", "coordinates": (0.0, 0.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].capacity_liters == pytest.approx(250 * 3.78541, 0.1)
    assert res[0].fuel_type == "FUEL_OIL"


def test_double_containment_fuel_supply_pipe():
    data = [{"id": "p1", "text": "DN25 DOUBLE-WALL DIESEL SUPPLY COAXIAL PIPE", "coordinates": (12.3, 45.6)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].element_type == "FUEL_PIPE"
    assert res[0].pipe_service == "SUPPLY"
    assert res[0].pipe_size_mm == 25
    assert res[0].is_double_wall is True


def test_fuel_return_line():
    data = [{"id": "p2", "text": "DN32 DIESEL RETURN LINE", "coordinates": (30.0, 40.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].element_type == "FUEL_PIPE"
    assert res[0].pipe_service == "RETURN"
    assert res[0].pipe_size_mm == 32


def test_fuel_overflow_line():
    data = [{"id": "p3", "text": "50MM FUEL OVERFLOW PIPE", "coordinates": (10.0, 20.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].element_type == "FUEL_PIPE"
    assert res[0].pipe_service == "OVERFLOW"
    assert res[0].pipe_size_mm == 50


def test_hvo_fuel_classification():
    data = [{"id": "t4", "text": "2000L HVO DAY TANK SKID-MOUNTED", "coordinates": (10.0, 10.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].fuel_type == "HVO"
    assert res[0].capacity_liters == 2000.0
    assert res[0].mounting_bunding == "SKID_MOUNTED"


def test_biodiesel_classification():
    data = [{"id": "t5", "text": "1500L BIODIESEL FUEL TANK", "coordinates": (20.0, 20.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].fuel_type == "BIODIESEL"
    assert res[0].capacity_liters == 1500.0


def test_interstitial_leak_sensor():
    data = [{"id": "s1", "text": "DOUBLE WALL INTERSTITIAL SENSOR FOR FUEL PIPE", "coordinates": (5.0, 5.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].element_type == "LEAK_SENSOR"
    assert res[0].is_double_wall is True


def test_optical_float_switch():
    data = [{"id": "s2", "text": "BUND LEAK DETECTION SENSOR OPTICAL FLOAT SWITCH", "coordinates": (15.0, 25.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].element_type == "LEAK_SENSOR"


def test_negative_water_tank():
    data = [{"id": "n1", "text": "5000L DOMESTIC WATER TANK", "coordinates": (0.0, 0.0)}]
    assert len(extract_generator_fuel_items(data)) == 0


def test_negative_rainwater_tank():
    data = [{"id": "n2", "text": "10000L RAINWATER HARVESTING TANK", "coordinates": (0.0, 0.0)}]
    assert len(extract_generator_fuel_items(data)) == 0


def test_negative_expansion_vessel():
    data = [{"id": "n3", "text": "100L CHW EXPANSION VESSEL", "coordinates": (0.0, 0.0)}]
    assert len(extract_generator_fuel_items(data)) == 0


def test_negative_compressed_air():
    data = [{"id": "n4", "text": "DN50 COMPRESSED AIR SUPPLY LINE", "coordinates": (0.0, 0.0)}]
    assert len(extract_generator_fuel_items(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((10.1, 19.9), tolerance=2.5)
    assert pt == (10.0, 20.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "500L DIESEL DAY TANK", "coordinates": (float(i), float(i))} for i in range(150)]
    res = extract_generator_fuel_items(items, max_primitives=50)
    assert len(res) == 50


def test_candidate_guardrails_default():
    candidate = GeneratorFuelItemCandidate(
        item_id="cand_1",
        element_type="DAY_TANK",
        capacity_liters=1000.0,
        fuel_type="DIESEL",
        mounting_bunding="SELF_BUNDED",
        pipe_service=None,
        pipe_size_mm=None,
        is_double_wall=True,
        coordinates=(10.0, 20.0),
        raw_text="1000L DIESEL DAY TANK",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = GeneratorFuelItemCandidate(
        item_id="cand_2",
        element_type="DAY_TANK",
        capacity_liters=500.0,
        fuel_type="DIESEL",
        mounting_bunding="STANDARD",
        pipe_service=None,
        pipe_size_mm=None,
        is_double_wall=False,
        coordinates=(0.0, 0.0),
        raw_text="500L DIESEL DAY TANK",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "t6", "text": "DN50 DIESEL FUEL VENT PIPE", "coordinates": (25.0, 50.0)}]
    res = extract_generator_fuel_items(data)
    d = res[0].to_dict()
    assert d["pipe_service"] == "VENT"
    assert d["pipe_size_mm"] == 50
    assert d["status"] == "CANDIDATE"


def test_wall_mounted_day_tank():
    data = [{"id": "t7", "text": "250L WALL-MOUNTED DIESEL DAY TANK", "coordinates": (12.5, 25.0)}]
    res = extract_generator_fuel_items(data)
    assert len(res) == 1
    assert res[0].mounting_bunding == "WALL_MOUNTED"
    assert res[0].capacity_liters == 250.0
