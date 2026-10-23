"""
test_source_fire_smoke_damper_hvac_shadow.py

Unit tests for SourceFireSmokeDamperHVACShadowAuthority.
"""

import pytest
from pb_source_fire_smoke_damper_hvac_shadow import (
    SourceFireSmokeDamperHVACShadowAuthority,
    DamperType,
    ActuatorPowerType,
    HVACDamperSpec,
    HVACDamperExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_hvac_damper_callout_parsing():
    parsed1 = SourceFireSmokeDamperHVACShadowAuthority.parse_callout(
        "600x400 MOTORIZED COMBINATION FIRE/SMOKE DAMPER FRL -/120/- W/ 24V SPRING RETURN ACTUATOR & 450x450 ACCESS PANEL"
    )
    assert parsed1["damper_type"] == DamperType.MOTORIZED_FIRE_SMOKE_DAMPER
    assert parsed1["duct_width_mm"] == 600.0
    assert parsed1["duct_height_mm"] == 400.0
    assert parsed1["fire_rating_frl"] == "-/120/-"
    assert parsed1["actuator_type"] == ActuatorPowerType.ELECTRIC_SPRING_RETURN_24V
    assert parsed1["access_door_included"] is True

    parsed2 = SourceFireSmokeDamperHVACShadowAuthority.parse_callout(
        "400x300 MECHANICAL CURTAIN FIRE DAMPER FRL -/120/- FUSIBLE LINK"
    )
    assert parsed2["damper_type"] == DamperType.MECHANICAL_CURTAIN_FIRE_DAMPER
    assert parsed2["actuator_type"] == ActuatorPowerType.THERMAL_FUSIBLE_LINK_ONLY

    parsed3 = SourceFireSmokeDamperHVACShadowAuthority.parse_callout(
        "800x600 MULTI-BLADE SMOKE DAMPER 240V ACTUATOR"
    )
    assert parsed3["damper_type"] == DamperType.MULTI_BLADE_SMOKE_DAMPER
    assert parsed3["actuator_type"] == ActuatorPowerType.ELECTRIC_SPRING_RETURN_240V

    parsed4 = SourceFireSmokeDamperHVACShadowAuthority.parse_callout(
        "300x150 INTUMESCENT AIR TRANSFER DAMPER FRL -/60/-"
    )
    assert parsed4["damper_type"] == DamperType.INTUMESCENT_AIR_TRANSFER_DAMPER
    assert parsed4["access_door_included"] is False


def test_hvac_damper_point_snapping():
    pt = (601.3, 400.8)
    snapped = SourceFireSmokeDamperHVACShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (602.5, 400.0)


def test_hvac_damper_evaluation_quantities():
    raw_data = [
        {
            "damper_id": "FSD-01",
            "location_point": (1000.0, 2000.0),
            "callout": "600x400 MOTORIZED COMBINATION FIRE/SMOKE DAMPER FRL -/120/- W/ 24V ACTUATOR",
            "level_id": "L01",
            "host_wall_id": "W-FIRE-01",
        },
        {
            "damper_id": "FD-01",
            "location_point": (3000.0, 2000.0),
            "callout": "400x300 MECHANICAL CURTAIN FIRE DAMPER FRL -/120/- FUSIBLE LINK",
            "level_id": "L01",
            "host_wall_id": "W-FIRE-02",
        },
    ]

    result = SourceFireSmokeDamperHVACShadowAuthority.evaluate_dampers(raw_data)
    assert len(result.dampers) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_dampers_count == 2

    # Face areas:
    # FSD-01: 0.6 * 0.4 = 0.24 m2
    # FD-01: 0.4 * 0.3 = 0.12 m2
    # Total: 0.36 m2
    assert pytest.approx(q.total_face_area_m2, rel=1e-3) == 0.36

    # Retaining angles: 4 * (W + H)
    # FSD-01: 4 * (0.6 + 0.4) = 4.0m
    # FD-01: 4 * (0.4 + 0.3) = 2.8m
    # Total: 6.8m
    assert pytest.approx(q.total_retaining_angles_meters, rel=1e-3) == 6.8

    # Motorized actuators: FSD-01 (1), FD-01 (0 fusible link) = 1
    assert q.total_motorized_actuators_count == 1
    assert q.total_access_doors_count == 2

    assert q.dampers_by_type[DamperType.MOTORIZED_FIRE_SMOKE_DAMPER.value] == 1
    assert q.dampers_by_type[DamperType.MECHANICAL_CURTAIN_FIRE_DAMPER.value] == 1
    assert q.dampers_by_frl["-/120/-"] == 2
