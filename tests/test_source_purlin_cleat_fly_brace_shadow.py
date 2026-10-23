"""
test_source_purlin_cleat_fly_brace_shadow.py

Unit tests for SourcePurlinCleatFlyBraceShadowAuthority.
"""

import pytest
from pb_source_purlin_cleat_fly_brace_shadow import (
    SourcePurlinCleatFlyBraceShadowAuthority,
    PurlinCleatType,
    FlyBracingType,
    PurlinConnectionSpec,
    PurlinConnectionExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_purlin_connection_callout_parsing():
    parsed1 = SourcePurlinCleatFlyBraceShadowAuthority.parse_callout(
        "Z200 PURLIN CLEAT 150x100x8 W/ 2x M12 BOLTS & 50x50x5 EA FLY BRACE"
    )
    assert parsed1["cleat_type"] == PurlinCleatType.STANDARD_ANGLE_CLEAT
    assert parsed1["purlin_profile"] == "Z200"
    assert parsed1["cleat_dimensions"] == "150x100x8"
    assert parsed1["bolts_count"] == 2
    assert parsed1["bolt_size"] == "M12"
    assert parsed1["fly_bracing_type"] == FlyBracingType.SINGLE_ANGLE_FLY_BRACE
    assert parsed1["fly_brace_profile"] == "50x50x5 EA"

    parsed2 = SourcePurlinCleatFlyBraceShadowAuthority.parse_callout(
        "Z250 FORMED PLATE CLEAT W/ 2x M16 BOLTS DOUBLE FLY BRACE"
    )
    assert parsed2["cleat_type"] == PurlinCleatType.FORMED_PLATE_CLEAT
    assert parsed2["purlin_profile"] == "Z250"
    assert parsed2["bolt_size"] == "M16"
    assert parsed2["fly_bracing_type"] == FlyBracingType.DOUBLE_ANGLE_FLY_BRACE

    parsed3 = SourcePurlinCleatFlyBraceShadowAuthority.parse_callout(
        "C150 ANGLE CLEAT W/ 2x M12 BOLTS NO FLY BRACE"
    )
    assert parsed3["purlin_profile"] == "C150"
    assert parsed3["fly_bracing_type"] == FlyBracingType.NO_FLY_BRACE


def test_purlin_connection_point_snapping():
    pt = (1201.3, 3000.8)
    snapped = SourcePurlinCleatFlyBraceShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (1202.5, 3000.0)


def test_purlin_connection_evaluation_quantities():
    raw_data = [
        {
            "connection_id": "PC-01",
            "location_point": (1200.0, 0.0),
            "callout": "Z200 PURLIN CLEAT 150x100x8 W/ 2x M12 BOLTS & 50x50x5 EA FLY BRACE",
            "level_id": "ROOF",
            "rafter_id": "RAFTER-01",
        },
        {
            "connection_id": "PC-02",
            "location_point": (2400.0, 0.0),
            "callout": "Z200 PURLIN CLEAT 150x100x8 W/ 2x M12 BOLTS NO FLY BRACE",
            "level_id": "ROOF",
            "rafter_id": "RAFTER-01",
        },
        {
            "connection_id": "PC-03",
            "location_point": (3600.0, 0.0),
            "callout": "Z250 FORMED PLATE CLEAT W/ 2x M16 BOLTS DOUBLE FLY BRACE",
            "level_id": "ROOF",
            "rafter_id": "RAFTER-01",
        },
    ]

    result = SourcePurlinCleatFlyBraceShadowAuthority.evaluate_connections(raw_data)
    assert len(result.connections) == 3
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_connections_count == 3
    assert q.total_cleats_count == 3
    assert q.total_bolts_count == 6  # 2 per cleat * 3

    # Fly braces:
    # PC-01: 1 single fly brace (1.2m)
    # PC-02: 0 no fly brace (0m)
    # PC-03: 2 double fly braces (2.4m)
    # Total fly braces: 3, total length: 3.6m
    assert q.total_fly_braces_count == 3
    assert pytest.approx(q.total_fly_brace_length_meters, rel=1e-3) == 3.6

    assert q.connections_by_cleat_type[PurlinCleatType.STANDARD_ANGLE_CLEAT.value] == 2
    assert q.connections_by_cleat_type[PurlinCleatType.FORMED_PLATE_CLEAT.value] == 1
    assert q.connections_by_fly_brace[FlyBracingType.SINGLE_ANGLE_FLY_BRACE.value] == 1
    assert q.connections_by_fly_brace[FlyBracingType.DOUBLE_ANGLE_FLY_BRACE.value] == 1
    assert q.connections_by_fly_brace[FlyBracingType.NO_FLY_BRACE.value] == 1
