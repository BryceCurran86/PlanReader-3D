"""
Tests for Source Laboratory Fume Hood Acid Neutralization Polypropylene Tank Shadow Authority.
"""

import pytest
from pb_source_lab_acid_neutralization_tank_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    LabAcidNeutralizationTankCallout,
    snap_point,
    parse_lab_acid_neutralization_tank_callout,
    extract_lab_acid_neutralization_tank_candidates,
    validate_lab_acid_neutralization_tank_system,
)


def test_snap_point_regular():
    pt = snap_point(41.1, 88.8, snap_tol=2.5)
    assert pt == (40.0, 90.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(41.1, 88.8, snap_tol=0.0)
    assert pt == (41.1, 88.8)


def test_parse_none_on_irrelevant_text():
    assert parse_lab_acid_neutralization_tank_callout("ALUMINUM BALUSTRADE HANDRAIL") is None
    assert parse_lab_acid_neutralization_tank_callout("CONCRETE STAIR FLIGHT") is None
    assert parse_lab_acid_neutralization_tank_callout("GYPSUM WALL CORNICE") is None


def test_parse_under_sink_polypropylene_trap():
    text = "UNDER-SINK ACID NEUTRALIZATION TRAP 15 LITRES FLAME RETARDANT PP WITH LIMESTONE MARBLE CHIPS DN40"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["tank_type"] == "UNDER_SINK_NEUTRALIZATION_TRAP"
    assert parsed["tank_capacity_litres"] == 15.0
    assert parsed["tank_material"] == "POLYPROPYLENE_PP"
    assert parsed["neutralization_medium"] == "CALCIUM_CARBONATE_LIMESTONE_CHIPS"
    assert parsed["inlet_outlet_dn"] == "DN40"


def test_parse_automatic_ph_neutralization_system():
    text = "AUTOMATIC PH NEUTRALIZATION SYSTEM 500 L HDPE WITH CAUSTIC SODA DOSING PUMP AND PH CONTROLLER - CENTRAL BASEMENT"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["tank_type"] == "AUTOMATIC_PH_NEUTRALIZATION_SYSTEM"
    assert parsed["tank_capacity_litres"] == 500.0
    assert parsed["tank_material"] == "HIGH_DENSITY_POLYETHYLENE_HDPE"
    assert parsed["neutralization_medium"] == "CAUSTIC_SODA_DOSING"
    assert parsed["monitoring_instrumentation"] == "PH_SENSOR_PROBE_CONTROLLER"


def test_parse_fume_hood_service_environment():
    text = "LABORATORY FUME HOOD ACID WASTE NEUTRALIZATION TANK 50 LITERS WITH SAMPLING PORT"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["service_environment"] == "LABORATORY_FUME_HOOD"
    assert parsed["tank_capacity_litres"] == 50.0
    assert parsed["monitoring_instrumentation"] == "SAMPLING_PORT_MANHOLE"


def test_parse_gallons_conversion():
    text = "ACID NEUTRALIZATION TANK 100 GALLONS PVDF WITH HIGH LEVEL ALARM"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["tank_capacity_litres"] == round(100.0 * 3.78541, 1)
    assert parsed["tank_material"] == "PVDF"
    assert parsed["monitoring_instrumentation"] == "HIGH_LEVEL_ALARM_SWITCH"


def test_parse_cup_sink_dilution():
    text = "CUP SINK ACID DILUTION BASIN 5 LITRES WITH WATER DILUTION BAFFLE"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["service_environment"] == "CUP_SINK"
    assert parsed["neutralization_medium"] == "DILUTION_WATER_BAFFLE"
    assert parsed["tank_capacity_litres"] == 5.0


def test_parse_inch_pipe_sizes():
    text = "NEUTRALIZATION TANK 2\" ACID DRAIN INLET DN50"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["inlet_outlet_dn"] == "DN50"


def test_parse_cleanroom_service():
    text = "CLEANROOM BENCH ACID WASTE TANK 30 LTR PP"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["service_environment"] == "CLEANROOM_BENCH"
    assert parsed["tank_material"] == "POLYPROPYLENE_PP"
    assert parsed["tank_capacity_litres"] == 30.0


def test_extract_lab_acid_neutralization_tank_candidates():
    items = [
        ("UNDER-SINK ACID NEUTRALIZATION TRAP 15 LITRES PP", (100.4, 200.8)),
        ("VINYL FLOORING TILE", (50.0, 50.0)),
        ("AUTOMATIC PH NEUTRALIZATION SYSTEM 500 L", (300.0, 400.0)),
    ]
    candidates = extract_lab_acid_neutralization_tank_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (100.0, 200.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"ACID NEUTRALIZATION TANK {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_lab_acid_neutralization_tank_candidates(items, max_cap=14)
    assert len(candidates) == 14


def test_system_validation_summary():
    items = [
        ("UNDER-SINK ACID NEUTRALIZATION TRAP 15 LITRES PP WITH LIMESTONE CHIPS", (10.0, 20.0)),
        ("AUTOMATIC PH NEUTRALIZATION SYSTEM 500 L WITH PH SENSOR", (30.0, 40.0)),
        ("CENTRAL ACID DILUTION BASIN 1000 L", (50.0, 60.0)),
    ]
    candidates = extract_lab_acid_neutralization_tank_candidates(items)
    summary = validate_lab_acid_neutralization_tank_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["instrumented_count"] == 1
    assert summary["sized_capacity_count"] == 3
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = LabAcidNeutralizationTankCallout(
        raw_text="SAMPLE",
        tank_type="UNDER_SINK_NEUTRALIZATION_TRAP",
        tank_capacity_litres=15.0,
        tank_material="POLYPROPYLENE_PP",
        neutralization_medium="CALCIUM_CARBONATE_LIMESTONE_CHIPS",
        monitoring_instrumentation="PH_SENSOR_PROBE_CONTROLLER",
        inlet_outlet_dn="DN40",
        service_environment="LABORATORY_FUME_HOOD",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_lab_acid_neutralization_tank_candidates([])
    assert len(candidates) == 0
    summary = validate_lab_acid_neutralization_tank_system([])
    assert summary["total_candidates"] == 0
    assert summary["instrumented_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_lab_acid_neutralization_tank_callout("HOT WATER STORAGE TANK 250L") is None
    assert parse_lab_acid_neutralization_tank_callout("GREASE INTERCEPTOR TRAP 1000L") is None
    assert parse_lab_acid_neutralization_tank_callout("LABORATORY CEILING DIFFUSER") is None


def test_kynar_pvdf_material():
    text = "ACID TRAP KYNAR MATERIAL 10 LTR"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["tank_material"] == "PVDF"
    assert parsed["tank_capacity_litres"] == 10.0


def test_dn100_inlet():
    text = "CENTRAL ACID WASTE TANK DN100 INLET 2000 LITRES"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["inlet_outlet_dn"] == "DN100"
    assert parsed["tank_capacity_litres"] == 2000.0


def test_single_gal_capacity():
    text = "UNDER SINK ACID TRAP 5 GALLON POLYPROPYLENE"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["tank_capacity_litres"] == round(5.0 * 3.78541, 1)


def test_3_inch_pipe_size():
    text = "ACID NEUTRALISATION TANK 3\" DRAIN"
    parsed = parse_lab_acid_neutralization_tank_callout(text)
    assert parsed is not None
    assert parsed["inlet_outlet_dn"] == "DN80"
