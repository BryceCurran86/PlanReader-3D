"""
test_source_stormwater_tank_sump_pump_shadow.py

Unit tests for SourceStormwaterTankSumpPumpShadowAuthority.
"""

import pytest
from pb_source_stormwater_tank_sump_pump_shadow import (
    SourceStormwaterTankSumpPumpShadowAuthority,
    StormwaterFacilityType,
    PumpingEquipmentConfig,
    GrateCoverClass,
    StormwaterFacilitySpec,
    StormwaterFacilityExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_stormwater_callout_parsing():
    parsed1 = SourceStormwaterTankSumpPumpShadowAuthority.parse_callout(
        "1200x1200x1500 DEEP BASEMENT SUMP PIT W/ DUPLEX SUBMERSIBLE PUMPS CLASS D GRATE"
    )
    assert parsed1["facility_type"] == StormwaterFacilityType.BASEMENT_DRAINAGE_SUMP_PIT
    assert parsed1["pumping_config"] == PumpingEquipmentConfig.DUPLEX_SUBMERSIBLE_PUMPS
    assert parsed1["cover_class"] == GrateCoverClass.CLASS_D_HEAVY_DUTY
    assert parsed1["internal_length_m"] == 1.2
    assert parsed1["internal_width_m"] == 1.2
    assert parsed1["internal_depth_m"] == 1.5

    parsed2 = SourceStormwaterTankSumpPumpShadowAuthority.parse_callout(
        "5.0x4.0x2.5m ON-SITE DETENTION (OSD) TANK GRAVITY DISCHARGE"
    )
    assert parsed2["facility_type"] == StormwaterFacilityType.ON_SITE_DETENTION_OSD_TANK
    assert parsed2["pumping_config"] == PumpingEquipmentConfig.GRAVITY_DISCHARGE
    assert parsed2["internal_length_m"] == 5.0
    assert parsed2["internal_width_m"] == 4.0
    assert parsed2["internal_depth_m"] == 2.5

    parsed3 = SourceStormwaterTankSumpPumpShadowAuthority.parse_callout(
        "600x600 SURFACE CATCH PIT CLASS B"
    )
    assert parsed3["facility_type"] == StormwaterFacilityType.SURFACE_STORMWATER_CATCH_PIT
    assert parsed3["cover_class"] == GrateCoverClass.CLASS_B_LIGHT_VEHICLE
    assert parsed3["internal_length_m"] == 0.6
    assert parsed3["internal_width_m"] == 0.6


def test_stormwater_snapping():
    pt = (123.4, 456.7)
    snapped = SourceStormwaterTankSumpPumpShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_stormwater_concrete_volume():
    # Pit 1.0m x 1.0m x 1.0m deep, tw = 0.2m, tb = 0.2m
    # Outer: L = 1.4, W = 1.4, D = 1.2 -> Vol = 1.4 * 1.4 * 1.2 = 2.352 m3
    # Inner: 1.0 * 1.0 * 1.0 = 1.0 m3
    # Concrete = 1.352 m3
    c_vol = SourceStormwaterTankSumpPumpShadowAuthority.calculate_concrete_volume(
        1.0, 1.0, 1.0, 200.0, 200.0
    )
    assert pytest.approx(c_vol, 0.001) == 1.352


def test_stormwater_evaluation_quantities():
    raw_data = [
        {
            "facility_id": "SP-01",
            "center_point": (100.0, 100.0),
            "callout": "1200x1200x1500 BASEMENT SUMP PIT W/ DUPLEX PUMPS",
            "level_id": "BASEMENT",
        },
        {
            "facility_id": "OSD-01",
            "center_point": (500.0, 500.0),
            "callout": "5.0x4.0x2.0m ON-SITE DETENTION TANK",
            "level_id": "BASEMENT",
        },
    ]

    res = SourceStormwaterTankSumpPumpShadowAuthority.evaluate_facilities(raw_data)

    assert len(res.facilities) == 2
    q = res.quantities
    assert q.total_facilities_count == 2
    assert q.sump_pits_count == 1
    assert q.osd_tanks_count == 1
    assert q.total_submersible_pumps_count == 2  # SP-01 has duplex (2 pumps), OSD has gravity (0 pumps)

    # Storage:
    # SP-01: 1.2 * 1.2 * 1.5 = 2.16 m3
    # OSD-01: 5.0 * 4.0 * 2.0 = 40.0 m3
    # Total = 42.16 m3
    assert pytest.approx(q.total_storage_capacity_m3, 0.001) == 42.16

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
