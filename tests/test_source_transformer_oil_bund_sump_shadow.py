"""
Tests for Source Electrical Substation Transformer Bund Oil Containment Sump Shadow Authority.
"""

import pytest
from pb_source_transformer_oil_bund_sump_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    TransformerOilBundSumpCallout,
    snap_point,
    parse_transformer_oil_bund_sump_callout,
    extract_transformer_oil_bund_sump_candidates,
    validate_transformer_oil_bund_sump_system,
)


def test_snap_point_regular():
    pt = snap_point(27.4, 82.6, snap_tol=2.5)
    assert pt == (27.5, 82.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(27.4, 82.6, snap_tol=0.0)
    assert pt == (27.4, 82.6)


def test_parse_none_on_irrelevant_text():
    assert parse_transformer_oil_bund_sump_callout("ALUMINUM DOOR THRESHOLD") is None
    assert parse_transformer_oil_bund_sump_callout("CARPET TILES OVER SCREED") is None
    assert parse_transformer_oil_bund_sump_callout("FIRE SPRINKLER PENDENT HEAD") is None


def test_parse_transformer_oil_bund_wall_with_gravel():
    text = "TRANSFORMER OIL BUND WALL 600MM HIGH 15,000 LITRES WITH WASHED CRUSHED GRAVEL BED FOR 1500 KVA TRANSFORMER"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["containment_type"] == "TRANSFORMER_OIL_BUND_WALL"
    assert parsed["bund_wall_height_mm"] == 600.0
    assert parsed["bund_capacity_litres"] == 15000.0
    assert parsed["flame_trap_medium"] == "WASHED_CRUSHED_GRAVEL_BED"
    assert parsed["transformer_kva_rating"] == "1500KVA"


def test_parse_oil_water_separator_sump():
    text = "SUBSTATION OIL/WATER SEPARATOR SUMP WITH OIL DETECTION OPTICAL SENSOR AND PNEUMATIC FAIL-SAFE SHUTOFF VALVE"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["containment_type"] == "OIL_WATER_SEPARATOR_SUMP"
    assert parsed["oil_sensor_shutoff"] == "OIL_DETECTION_OPTICAL_SENSOR"


def test_parse_fire_quenching_flame_trap_baffles():
    text = "TRANSFORMER BUND FLAME TRAP WITH ALUMINUM FLAME QUENCHING BAFFLES 2500 KVA"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["containment_type"] == "FIRE_QUENCHING_FLAME_TRAP"
    assert parsed["flame_trap_medium"] == "ALUMINUM_FLAME_QUENCHING_BAFFLES"
    assert parsed["transformer_kva_rating"] == "2500KVA"


def test_parse_fr3_natural_ester_fluid():
    text = "DIELECTRIC OIL CONTAINMENT BUND 5000 L NATURAL ESTER FR3 WITH LEVEL SWITCH"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["dielectric_fluid_type"] == "NATURAL_ESTER_FR3"
    assert parsed["bund_capacity_litres"] == 5000.0
    assert parsed["oil_sensor_shutoff"] == "OIL_SPILL_FLOAT_SWITCH"


def test_parse_mva_rating_and_gallons():
    text = "TRANSFORMER COMPOUND BUND 10 MVA 5,000 GALLONS MINERAL INSULATING OIL 450MM HIGH BUND WALL"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["transformer_kva_rating"] == "10MVA"
    assert parsed["bund_capacity_litres"] == round(5000.0 * 3.78541, 1)
    assert parsed["dielectric_fluid_type"] == "MINERAL_INSULATING_OIL"
    assert parsed["bund_wall_height_mm"] == 450.0


def test_parse_poly_containment_basin():
    text = "PREFABRICATED POLYETHYLENE CONTAINMENT BASIN FOR TRANSFORMER SUMP 2000 L"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["containment_type"] == "INTEGRAL_POLY_CONTAINMENT_BASIN"
    assert parsed["bund_capacity_litres"] == 2000.0


def test_parse_synthetic_ester_midel():
    text = "TRANSFORMER OIL BUND WITH SYNTHETIC ESTER MIDEL FLUID"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["dielectric_fluid_type"] == "SYNTHETIC_ESTER_FLUID"


def test_extract_transformer_oil_bund_sump_candidates():
    items = [
        ("TRANSFORMER OIL BUND WALL 600MM HIGH 15000 L", (120.4, 240.8)),
        ("TIMBER SKIRTING BOARD", (50.0, 50.0)),
        ("OIL/WATER SEPARATOR SUMP WITH OIL SENSOR", (300.0, 400.0)),
    ]
    candidates = extract_transformer_oil_bund_sump_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (120.0, 240.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"TRANSFORMER OIL BUND {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_transformer_oil_bund_sump_candidates(items, max_cap=15)
    assert len(candidates) == 15


def test_system_validation_summary():
    items = [
        ("TRANSFORMER OIL BUND WALL 600MM HIGH 15000 L WITH GRAVEL BED", (10.0, 20.0)),
        ("OIL/WATER SEPARATOR SUMP WITH OPTICAL PROBE SENSOR", (30.0, 40.0)),
        ("TRANSFORMER BUND FLAME TRAP WITH ALUMINIUM BAFFLE", (50.0, 60.0)),
    ]
    candidates = extract_transformer_oil_bund_sump_candidates(items)
    summary = validate_transformer_oil_bund_sump_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["instrumented_count"] == 1
    assert summary["sized_bund_count"] == 1
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = TransformerOilBundSumpCallout(
        raw_text="SAMPLE",
        containment_type="TRANSFORMER_OIL_BUND_WALL",
        bund_capacity_litres=15000.0,
        flame_trap_medium="WASHED_CRUSHED_GRAVEL_BED",
        oil_sensor_shutoff="OIL_DETECTION_OPTICAL_SENSOR",
        bund_wall_height_mm=600.0,
        transformer_kva_rating="1500KVA",
        dielectric_fluid_type="MINERAL_INSULATING_OIL",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_transformer_oil_bund_sump_candidates([])
    assert len(candidates) == 0
    summary = validate_transformer_oil_bund_sump_system([])
    assert summary["total_candidates"] == 0
    assert summary["instrumented_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_transformer_oil_bund_sump_callout("HOT WATER BOILER EXPANSION TANK") is None
    assert parse_transformer_oil_bund_sump_callout("CAR PARK SLAB JOINT SEALANT") is None
    assert parse_transformer_oil_bund_sump_callout("KITCHEN GREASE TRAP 2000L") is None


def test_silicone_fluid_detection():
    text = "TRANSFORMER OIL CONTAINMENT SILICONE FLUID 10000 LTR"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["dielectric_fluid_type"] == "SILICONE_OIL"
    assert parsed["bund_capacity_litres"] == 10000.0


def test_pneumatic_fail_safe_shutoff():
    text = "TRANSFORMER SUMP WITH PNEUMATIC SHUTOFF VALVE"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["oil_sensor_shutoff"] == "PNEUMATIC_FAIL_SAFE_SHUTOFF_VALVE"


def test_300mm_bund_wall():
    text = "SUBSTATION TRANSFORMER BUND 300MM DEEP"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["bund_wall_height_mm"] == 300.0


def test_fire_retardant_grating():
    text = "OIL SPILL BUND WITH FIRE RETARDANT GRATING"
    parsed = parse_transformer_oil_bund_sump_callout(text)
    assert parsed is not None
    assert parsed["flame_trap_medium"] == "FIRE_RETARDANT_GRATING"
