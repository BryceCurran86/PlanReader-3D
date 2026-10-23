"""
test_source_grease_trap_trade_waste_shadow.py

Unit tests for SourceGreaseTrapTradeWasteShadowAuthority.
"""

import pytest
from pb_source_grease_trap_trade_waste_shadow import (
    SourceGreaseTrapTradeWasteShadowAuthority,
    GreaseTrapType,
    AccessCoverLoadClass,
    GreaseTrapSpec,
    GreaseTrapExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_grease_trap_callout_parsing():
    parsed1 = SourceGreaseTrapTradeWasteShadowAuthority.parse_callout(
        "2000L IN-GROUND CONCRETE GREASE ARRESTOR W/ TWIN CLASS D GASTIGHT COVERS, DN100 INLET/OUTLET & SAMPLE PIT"
    )
    assert parsed1["trap_type"] == GreaseTrapType.IN_GROUND_CONCRETE_INTERCEPTOR
    assert parsed1["capacity_liters"] == 2000.0
    assert parsed1["cover_class"] == AccessCoverLoadClass.CLASS_D_HEAVY_DUTY_GASTIGHT
    assert parsed1["access_covers_count"] == 2
    assert parsed1["pipe_diameter_dn"] == 100
    assert parsed1["sampling_pit_included"] is True

    parsed2 = SourceGreaseTrapTradeWasteShadowAuthority.parse_callout(
        "1500L ABOVE GROUND POLYETHYLENE GREASE INTERCEPTOR CLASS B COVERS NO SAMPLE PIT"
    )
    assert parsed2["trap_type"] == GreaseTrapType.ABOVE_GROUND_POLY_INTERCEPTOR
    assert parsed2["capacity_liters"] == 1500.0
    assert parsed2["cover_class"] == AccessCoverLoadClass.CLASS_B_GASTIGHT
    assert parsed2["sampling_pit_included"] is False

    parsed3 = SourceGreaseTrapTradeWasteShadowAuthority.parse_callout(
        "250L UNDER-SINK AUTOMATIC GREASE RECOVERY DEVICE"
    )
    assert parsed3["trap_type"] == GreaseTrapType.UNDER_SINK_AUTOMATIC_RECOVERY
    assert parsed3["capacity_liters"] == 250.0

    parsed4 = SourceGreaseTrapTradeWasteShadowAuthority.parse_callout(
        "5000L PRECAST CONCRETE GREASE TRAP DN150"
    )
    assert parsed4["capacity_liters"] == 5000.0
    assert parsed4["pipe_diameter_dn"] == 150


def test_grease_trap_point_snapping():
    pt = (2001.3, 1500.8)
    snapped = SourceGreaseTrapTradeWasteShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (2002.5, 1500.0)


def test_grease_trap_evaluation_quantities():
    raw_data = [
        {
            "trap_id": "GT-01",
            "location_point": (5000.0, 0.0),
            "callout": "2000L IN-GROUND CONCRETE GREASE ARRESTOR W/ TWIN CLASS D GASTIGHT COVERS, DN100 INLET/OUTLET & SAMPLE PIT",
            "level_id": "CIVIL",
        },
        {
            "trap_id": "GT-02",
            "location_point": (10000.0, 0.0),
            "callout": "1500L ABOVE GROUND POLYETHYLENE GREASE INTERCEPTOR CLASS B COVERS NO SAMPLE PIT",
            "level_id": "L01",
        },
    ]

    result = SourceGreaseTrapTradeWasteShadowAuthority.evaluate_traps(raw_data)
    assert len(result.traps) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_traps_count == 2
    # Liters: 2000 + 1500 = 3500 L -> 3.5 m3
    assert q.total_capacity_liters == 3500.0
    assert pytest.approx(q.total_capacity_m3, rel=1e-3) == 3.5

    # Access covers: GT-01 (2) + GT-02 (2 default) = 4
    assert q.total_access_covers_count == 4

    # Sampling pits: GT-01 has sample pit, GT-02 does not -> 1
    assert q.total_sampling_pits_count == 1

    assert q.traps_by_type[GreaseTrapType.IN_GROUND_CONCRETE_INTERCEPTOR.value] == 1
    assert q.traps_by_type[GreaseTrapType.ABOVE_GROUND_POLY_INTERCEPTOR.value] == 1
    assert q.traps_by_cover_class[AccessCoverLoadClass.CLASS_D_HEAVY_DUTY_GASTIGHT.value] == 1
    assert q.traps_by_cover_class[AccessCoverLoadClass.CLASS_B_GASTIGHT.value] == 1
