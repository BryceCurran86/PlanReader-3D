"""
Tests for Source High-Pressure Misting Fire Suppression Nozzle & Zoned Solenoid Valve Shadow Authority.
"""

import pytest
from pb_source_high_pressure_water_mist_nozzle_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    HighPressureWaterMistNozzleCallout,
    snap_point,
    parse_high_pressure_water_mist_nozzle_callout,
    extract_high_pressure_water_mist_nozzle_candidates,
    validate_high_pressure_water_mist_nozzle_system,
)


def test_snap_point_regular():
    pt = snap_point(53.8, 71.2, snap_tol=2.5)
    assert pt == (55.0, 70.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(53.8, 71.2, snap_tol=0.0)
    assert pt == (53.8, 71.2)


def test_parse_none_on_irrelevant_text():
    assert parse_high_pressure_water_mist_nozzle_callout("ALUMINUM WINDOW MULLION") is None
    assert parse_high_pressure_water_mist_nozzle_callout("CARPET TILES OVER SCREED") is None
    assert parse_high_pressure_water_mist_nozzle_callout("SUSPENDED CEILING GRID 600X600") is None


def test_parse_high_pressure_water_mist_turbine_enclosure():
    text = "HIGH PRESSURE WATER MIST NOZZLE 140 BAR K=2.5 50 MICRONS 316L SEAMLESS SS TUBING FOR TURBINE GENERATOR ENCLOSURE"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["nozzle_type"] == "HIGH_PRESSURE_WATER_MIST_NOZZLE"
    assert parsed["operating_pressure_bar"] == 140.0
    assert parsed["k_factor"] == "K2.5"
    assert parsed["droplet_size_microns"] == 50.0
    assert parsed["piping_material"] == "STAINLESS_STEEL_316L"
    assert parsed["protected_hazard"] == "TURBINE_GENERATOR_ENCLOSURE"


def test_parse_automatic_bulb_data_center():
    text = "AUTOMATIC BULB MIST HEAD 57°C 100 BAR K=1.2 WITH DN20 SOLENOID VALVE FOR SERVER ROOM DATA CENTER"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["nozzle_type"] == "AUTOMATIC_BULB_MIST_HEAD"
    assert parsed["operating_pressure_bar"] == 100.0
    assert parsed["k_factor"] == "K1.2"
    assert parsed["zone_solenoid_valve_dn"] == "DN20"
    assert parsed["protected_hazard"] == "SERVER_ROOM_DATA_CENTER"


def test_parse_open_deluge_mist_nozzle_kitchen():
    text = "OPEN DELUGE MIST NOZZLE 12 MPA 80 UM DUPLEX 2205 FOR COMMERCIAL KITCHEN COOKING HOOD"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["nozzle_type"] == "OPEN_DELUGE_MIST_NOZZLE"
    assert parsed["operating_pressure_bar"] == 120.0
    assert parsed["droplet_size_microns"] == 80.0
    assert parsed["piping_material"] == "DUPLEX_2205"
    assert parsed["protected_hazard"] == "COMMERCIAL_KITCHEN_HOOD"


def test_parse_total_flooding_micro_orifice_archive():
    text = "TOTAL FLOODING MICRO-ORIFICE MIST SUPPRESSION NOZZLE 80 BAR FOR HERITAGE ARCHIVE STORAGE"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["nozzle_type"] == "TOTAL_FLOODING_MICRO_ORIFICE"
    assert parsed["operating_pressure_bar"] == 80.0
    assert parsed["protected_hazard"] == "HERITAGE_ARCHIVE_STORAGE"


def test_parse_hi_fog_brand():
    text = "HI-FOG WATER MIST NOZZLE 140 BAR WITH DN25 HIGH PRESSURE SOLENOID VALVE"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["nozzle_type"] == "HIGH_PRESSURE_WATER_MIST_NOZZLE"
    assert parsed["operating_pressure_bar"] == 140.0
    assert parsed["zone_solenoid_valve_dn"] == "DN25"


def test_parse_sem_safe_brand():
    text = "SEM-SAFE HPWM NOZZLE K=0.5 WITH SEAMLESS TUBING"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["k_factor"] == "K0.5"
    assert parsed["piping_material"] == "SEAMLESS_SS_TUBING"


def test_extract_high_pressure_water_mist_nozzle_candidates():
    items = [
        ("HIGH PRESSURE WATER MIST NOZZLE 140 BAR K=2.5", (150.2, 250.3)),
        ("VINYL WALL COVERING", (40.0, 50.0)),
        ("AUTOMATIC BULB MIST HEAD 100 BAR DATA CENTER", (300.0, 400.0)),
    ]
    candidates = extract_high_pressure_water_mist_nozzle_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (150.0, 250.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"HIGH PRESSURE WATER MIST NOZZLE {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_high_pressure_water_mist_nozzle_candidates(items, max_cap=12)
    assert len(candidates) == 12


def test_system_validation_summary():
    items = [
        ("HIGH PRESSURE WATER MIST NOZZLE 140 BAR K=2.5", (10.0, 20.0)),
        ("AUTOMATIC BULB MIST HEAD 100 BAR DATA CENTER", (30.0, 40.0)),
        ("TOTAL FLOODING MICRO ORIFICE MIST NOZZLE 80 BAR", (50.0, 60.0)),
    ]
    candidates = extract_high_pressure_water_mist_nozzle_candidates(items)
    summary = validate_high_pressure_water_mist_nozzle_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["pressurized_count"] == 3
    assert summary["k_factor_count"] == 1
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = HighPressureWaterMistNozzleCallout(
        raw_text="SAMPLE",
        nozzle_type="HIGH_PRESSURE_WATER_MIST_NOZZLE",
        operating_pressure_bar=140.0,
        k_factor="K2.5",
        droplet_size_microns=50.0,
        piping_material="STAINLESS_STEEL_316L",
        zone_solenoid_valve_dn="DN20",
        protected_hazard="TURBINE_GENERATOR_ENCLOSURE",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_high_pressure_water_mist_nozzle_candidates([])
    assert len(candidates) == 0
    summary = validate_high_pressure_water_mist_nozzle_system([])
    assert summary["total_candidates"] == 0
    assert summary["pressurized_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_high_pressure_water_mist_nozzle_callout("STANDARD SPRINKLER PENDENT HEAD") is None
    assert parse_high_pressure_water_mist_nozzle_callout("GARDEN IRRIGATION MISTING LINE") is None
    assert parse_high_pressure_water_mist_nozzle_callout("HUMIDIFIER MIST GENERATOR IN AHU") is None


def test_dn32_solenoid_valve():
    text = "MIST SUPPRESSION ZONED SOLENOID VALVE DN32"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["zone_solenoid_valve_dn"] == "DN32"


def test_micromist_brand():
    text = "MICROMIST SYSTEM HEAD 120 BAR"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["operating_pressure_bar"] == 120.0


def test_68deg_automatic_bulb():
    text = "WATER MIST NOZZLE 68°C THERMAL BULB K3.6"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["nozzle_type"] == "AUTOMATIC_BULB_MIST_HEAD"
    assert parsed["k_factor"] == "K3.6"


def test_genset_protected_hazard():
    text = "HPWM NOZZLE FOR DIESEL GENERATOR GENSET"
    parsed = parse_high_pressure_water_mist_nozzle_callout(text)
    assert parsed is not None
    assert parsed["protected_hazard"] == "TURBINE_GENERATOR_ENCLOSURE"
