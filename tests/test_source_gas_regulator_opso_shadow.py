"""
Unit and adversarial test suite for Source Natural Gas / LPG Service Regulator & OPSO Valve Shadow Authority.
"""

import pytest
from pb_source_gas_regulator_opso_shadow import (
    GasRegulatorOpsoCallout,
    SourceGasRegulatorOpsoShadowAuthority,
    parse_gas_regulator_opso_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_ng_service_regulator():
    text = "GAS METER STATION: NATURAL GAS SERVICE REGULATOR DN32 WITH INTEGRAL OPSO SLAM-SHUT VALVE, INLET: 200 KPA, OUTLET: 2.75 KPA, OPSO AT 5.0 KPA, ATMOSPHERIC VENT DN20"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["gas_service_type"] == "NATURAL_GAS_NG"
    assert res["regulator_type"] == "SERVICE_REGULATOR_WITH_INTEGRAL_OPSO"
    assert res["pipe_connection_dn"] == "DN32"
    assert res["inlet_pressure_kpa"] == 200.0
    assert res["outlet_pressure_kpa"] == 2.75
    assert res["opso_trip_kpa"] == 5.0
    assert res["relief_vent_dn"] == "DN20"


def test_parse_lpg_first_stage():
    text = "LPG REGULATOR FIRST STAGE HIGH PRESSURE DN25, INLET: 1000 KPA, OUTLET: 70 KPA"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["gas_service_type"] == "LIQUEFIED_PETROLEUM_GAS_LPG"
    assert res["regulator_type"] == "FIRST_STAGE_LPG_HIGH_PRESSURE"
    assert res["inlet_pressure_kpa"] == 1000.0
    assert res["outlet_pressure_kpa"] == 70.0


def test_parse_mbar_outlet():
    text = "GAS REGULATOR DN20, 20 MBAR OUTLET"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["outlet_pressure_kpa"] == 2.0


def test_parse_appliance_regulator():
    text = "SECONDARY APPLIANCE PRESSURE REGULATOR DN20"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["regulator_type"] == "APPLIANCE_PRESSURE_REGULATOR"
    assert res["pipe_connection_dn"] == "DN20"


def test_parse_defaults():
    text = "GAS REGULATOR"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["gas_service_type"] == "NATURAL_GAS_NG"
    assert res["pipe_connection_dn"] == "DN25"
    assert res["outlet_pressure_kpa"] == 2.75


def test_parse_non_gas():
    text = "FIRE SPRINKLER CONTROL VALVE"
    res = parse_gas_regulator_opso_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(18.9, 61.1, snap_tol=2.5)
    assert pt == (20.0, 60.0)


def test_authority_processing_dedup():
    auth = SourceGasRegulatorOpsoShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("GAS REGULATOR DN25", (10.0, 20.0)),
        ("GAS REGULATOR DN25", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceGasRegulatorOpsoShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("GAS REGULATOR DN25", (10.0, 20.0)),
        ("GAS REGULATOR DN25", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceGasRegulatorOpsoShadowAuthority()
    oversized = [("GAS REGULATOR", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceGasRegulatorOpsoShadowAuthority()
    res = auth.process_callouts([("GAS REGULATOR", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_gas_regulator_opso_callout("") is None


def test_propane_keyword():
    text = "PROPANE PRESSURE REGULATOR DN20"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["gas_service_type"] == "LIQUEFIED_PETROLEUM_GAS_LPG"


def test_dn50_large_commercial_meter():
    text = "GAS SERVICE REGULATOR DN50 WITH SLAM SHUT"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["pipe_connection_dn"] == "DN50"


def test_zero_tolerance_snap():
    pt = snap_point(11.11, 22.22, snap_tol=0.0)
    assert pt == (11.11, 22.22)


def test_frozen_dataclass_immutability():
    callout = GasRegulatorOpsoCallout(
        raw_text="text",
        gas_service_type="NG",
        regulator_type="REG",
        pipe_connection_dn="DN25",
        inlet_pressure_kpa=200.0,
        outlet_pressure_kpa=2.75,
        opso_trip_kpa=5.0,
        relief_vent_dn="DN15",
    )
    with pytest.raises(Exception):
        callout.outlet_pressure_kpa = 5.0  # type: ignore


def test_different_services_same_point():
    auth = SourceGasRegulatorOpsoShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("NATURAL GAS REGULATOR DN25", (10.0, 20.0)),
        ("LPG REGULATOR DN25", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_opso_alone_trigger():
    text = "OPSO VALVE DN32 TRIP AT 6.5 KPA"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["pipe_connection_dn"] == "DN32"
    assert res["opso_trip_kpa"] == 6.5


def test_gas_meter_regulator_trigger():
    text = "GAS METER REGULATOR 2.5 KPA"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["outlet_pressure_kpa"] == 2.5


def test_calculated_opso_default():
    text = "NATURAL GAS REGULATOR OUTLET: 1.5 KPA"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["opso_trip_kpa"] == 3.0  # 1.5 * 2.0


def test_vent_dn15():
    text = "GAS REGULATOR WITH ATMOSPHERIC VENT DN15"
    res = parse_gas_regulator_opso_callout(text)
    assert res is not None
    assert res["relief_vent_dn"] == "DN15"
