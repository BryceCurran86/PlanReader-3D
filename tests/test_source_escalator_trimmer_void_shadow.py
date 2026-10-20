"""
test_source_escalator_trimmer_void_shadow.py

Unit tests for SourceEscalatorTrimmerVoidShadowAuthority.
"""

import math
import pytest
from pb_source_escalator_trimmer_void_shadow import (
    SourceEscalatorTrimmerVoidShadowAuthority,
    VerticalTransportationType,
    EscalatorVoidSpec,
    EscalatorTrimmerExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_escalator_callout_parsing():
    parsed1 = SourceEscalatorTrimmerVoidShadowAuthority.parse_callout(
        "COMMERCIAL ESCALATOR 30 DEG W=1000mm RISE=4.5m W/ 500mm GLASS SMOKE BAFFLE"
    )
    assert parsed1["unit_type"] == VerticalTransportationType.COMMERCIAL_ESCALATOR_30_DEG
    assert parsed1["incline_angle_deg"] == 30.0
    assert parsed1["vertical_rise_m"] == 4.5
    assert parsed1["step_pallet_width_mm"] == 1000.0
    assert parsed1["has_smoke_baffle"] is True
    assert parsed1["smoke_baffle_depth_mm"] == 500.0

    parsed2 = SourceEscalatorTrimmerVoidShadowAuthority.parse_callout(
        "TRANSIT ESCALATOR 35 DEG INCLINE H=6.0m"
    )
    assert parsed2["unit_type"] == VerticalTransportationType.PUBLIC_TRANSIT_ESCALATOR_35_DEG
    assert parsed2["incline_angle_deg"] == 35.0
    assert parsed2["vertical_rise_m"] == 6.0

    parsed3 = SourceEscalatorTrimmerVoidShadowAuthority.parse_callout(
        "MOVING WALKWAY AUTOWALK 12 DEG INCLINE"
    )
    assert parsed3["unit_type"] == VerticalTransportationType.INCLINED_MOVING_WALKWAY_12_DEG
    assert parsed3["incline_angle_deg"] == 12.0


def test_escalator_snapping():
    pt = (123.4, 456.7)
    snapped = SourceEscalatorTrimmerVoidShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_escalator_evaluation_quantities():
    raw_data = [
        {
            "void_id": "ESC-01",
            "boundary_polygon": [
                (0.0, 0.0),
                (2000.0, 0.0),
                (2000.0, 12000.0),
                (0.0, 12000.0),
            ],
            "callout": "COMMERCIAL ESCALATOR 30 DEG RISE=4.5m W/ 500mm SMOKE BAFFLE",
            "level_id": "L01",
        },
        {
            "void_id": "ESC-02",
            "boundary_polygon": [
                (5000.0, 0.0),
                (7000.0, 0.0),
                (7000.0, 15000.0),
                (5000.0, 15000.0),
            ],
            "callout": "TRANSIT ESCALATOR 35 DEG RISE=6.0m",
            "level_id": "L01",
        },
    ]

    res = SourceEscalatorTrimmerVoidShadowAuthority.evaluate_escalator_voids(raw_data, scale_ratio=0.001)

    assert len(res.voids) == 2
    q = res.quantities
    assert q.total_units_count == 2

    # ESC-01: 2.0m * 12.0m = 24.0 m2, perimeter = 2 * (2.0 + 12.0) = 28.0m
    # ESC-02: 2.0m * 15.0m = 30.0 m2, perimeter = 2 * (2.0 + 15.0) = 34.0m
    # Total area = 54.0 m2, Total trimmer perimeter = 62.0m
    assert pytest.approx(q.total_void_area_m2, 0.001) == 54.0
    assert pytest.approx(q.total_trimmer_perimeter_linear_meters, 0.001) == 62.0

    # Travel:
    # ESC-01: 4.5 / sin(30 deg) = 4.5 / 0.5 = 9.0m
    # ESC-02: 6.0 / sin(35 deg) = 6.0 / 0.573576 = 10.4607m
    expected_travel = 9.0 + (6.0 / math.sin(math.radians(35.0)))
    assert pytest.approx(q.total_inclined_travel_meters, 0.01) == expected_travel

    # Smoke baffle: only ESC-01 has baffle (perimeter 28.0m, depth 0.5m -> area = 14.0 m2)
    assert pytest.approx(q.total_smoke_baffle_perimeter_meters, 0.001) == 28.0
    assert pytest.approx(q.total_smoke_baffle_area_m2, 0.001) == 14.0

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
