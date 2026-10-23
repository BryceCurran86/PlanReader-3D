"""
Unit and adversarial test suite for Source Hot Water Expansion Vessel & Relief Valve Shadow Authority.
"""

import pytest
from pb_source_expansion_vessel_relief_valve_shadow import (
    ExpansionVesselReliefValveCallout,
    SourceExpansionVesselReliefValveShadowAuthority,
    parse_expansion_vessel_relief_valve_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_expansion_vessel():
    text = "DHW PLANT: 100 LITRES POTABLE EXPANSION VESSEL, PRECHARGE: 500 KPA, BUTYL BLADDER, WITH PTRV SET AT 1000 KPA, 99 DEG C, DISCHARGE PIPE DN25"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["vessel_capacity_litres"] == 100.0
    assert res["precharge_pressure_kpa"] == 500.0
    assert res["relief_valve_set_kpa"] == 1000.0
    assert res["relief_temperature_deg_c"] == 99.0
    assert res["relief_drain_dn"] == "DN25"
    assert res["bladder_material"] == "BUTYL_RUBBER_FOOD_GRADE"


def test_parse_epdm_small_tank():
    text = "EXPANSION TANK 18L, EPDM MEMBRANE, RELIEF: 850 KPA, DN20"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["vessel_capacity_litres"] == 18.0
    assert res["bladder_material"] == "EPDM_MEMBRANE"
    assert res["relief_valve_set_kpa"] == 850.0
    assert res["relief_drain_dn"] == "DN20"


def test_parse_ptrv_alone():
    text = "P&T RELIEF VALVE DN20, SET: 700 KPA, 95 DEG C"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["relief_valve_set_kpa"] == 700.0
    assert res["relief_temperature_deg_c"] == 95.0
    assert res["relief_drain_dn"] == "DN20"


def test_parse_defaults():
    text = "THERMAL EXPANSION TANK"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["vessel_capacity_litres"] == 24.0
    assert res["precharge_pressure_kpa"] == 450.0
    assert res["relief_valve_set_kpa"] == 850.0
    assert res["relief_drain_dn"] == "DN20"


def test_parse_non_vessel():
    text = "ELECTRICAL DISTRIBUTION BOARD"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(55.2, 122.3, snap_tol=2.5)
    assert pt == (55.0, 122.5)


def test_authority_processing_dedup():
    auth = SourceExpansionVesselReliefValveShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("EXPANSION VESSEL 24L", (10.0, 20.0)),
        ("EXPANSION VESSEL 24L", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceExpansionVesselReliefValveShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("EXPANSION VESSEL 24L", (10.0, 20.0)),
        ("EXPANSION VESSEL 24L", (70.0, 80.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceExpansionVesselReliefValveShadowAuthority()
    oversized = [("EXPANSION VESSEL 24L", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceExpansionVesselReliefValveShadowAuthority()
    res = auth.process_callouts([("EXPANSION VESSEL 24L", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_expansion_vessel_relief_valve_callout("") is None


def test_diaphragm_potable():
    text = "POTABLE EXPANSION DIAPHRAGM TANK 50 LITRES"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["vessel_capacity_litres"] == 50.0
    assert res["bladder_material"] == "DIAPHRAGM_POTABLE"


def test_large_commercial_vessel():
    text = "COMMERCIAL EXPANSION VESSEL 300 LITRES, CHARGE: 600 KPA, DISCHARGE DN32"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["vessel_capacity_litres"] == 300.0
    assert res["precharge_pressure_kpa"] == 600.0
    assert res["relief_drain_dn"] == "DN32"


def test_safety_relief_valve_trigger():
    text = "SAFETY RELIEF VALVE DN25, SET AT 1400 KPA"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["relief_valve_set_kpa"] == 1400.0
    assert res["relief_drain_dn"] == "DN25"


def test_zero_tolerance_snap():
    pt = snap_point(7.89, 4.32, snap_tol=0.0)
    assert pt == (7.89, 4.32)


def test_frozen_dataclass_immutability():
    callout = ExpansionVesselReliefValveCallout(
        raw_text="text",
        vessel_capacity_litres=24.0,
        precharge_pressure_kpa=450.0,
        relief_valve_set_kpa=850.0,
        relief_temperature_deg_c=99.0,
        relief_drain_dn="DN20",
        bladder_material="BUTYL",
    )
    with pytest.raises(Exception):
        callout.vessel_capacity_litres = 50.0  # type: ignore


def test_different_capacities_same_point():
    auth = SourceExpansionVesselReliefValveShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("EXPANSION VESSEL 24L", (10.0, 20.0)),
        ("EXPANSION VESSEL 80L", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_temperature_relief_valve_keyword():
    text = "TEMPERATURE RELIEF VALVE 95 DEG C"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["relief_temperature_deg_c"] == 95.0


def test_pressure_relief_valve_keyword():
    text = "PRESSURE RELIEF VALVE DN15, SET AT 800 KPA"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["relief_drain_dn"] == "DN15"
    assert res["relief_valve_set_kpa"] == 800.0


def test_pre_charge_hyphenated():
    text = "EXPANSION TANK 60L PRE-CHARGE 400 KPA"
    res = parse_expansion_vessel_relief_valve_callout(text)
    assert res is not None
    assert res["precharge_pressure_kpa"] == 400.0
