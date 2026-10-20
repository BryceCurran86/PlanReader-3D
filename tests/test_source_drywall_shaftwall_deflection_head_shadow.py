"""
test_source_drywall_shaftwall_deflection_head_shadow.py

Unit tests for SourceDrywallShaftwallDeflectionHeadShadowAuthority.
"""

import pytest
from pb_source_drywall_shaftwall_deflection_head_shadow import (
    SourceDrywallShaftwallDeflectionHeadShadowAuthority,
    DrywallSystemType,
    DeflectionHeadType,
    DrywallPartitionSpec,
    DrywallShaftwallExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_drywall_callout_parsing():
    parsed1 = SourceDrywallShaftwallDeflectionHeadShadowAuthority.parse_callout(
        "92mm STEEL STUD SHAFTWALL 2-HR W/ 25mm SHAFTLINER SLOTTED DEFLECTION HEAD 25mm TRAVEL H=3.6m"
    )
    assert parsed1["system_type"] == DrywallSystemType.SHAFTWALL_SYSTEM
    assert parsed1["has_shaftliner_core"] is True
    assert parsed1["deflection_head_type"] == DeflectionHeadType.SLOTTED_DEFLECTION_TRACK
    assert parsed1["deflection_allowance_mm"] == 25.0
    assert parsed1["stud_width_mm"] == 92.0
    assert parsed1["fire_rating_hours"] == 2
    assert parsed1["wall_height_m"] == 3.6

    parsed2 = SourceDrywallShaftwallDeflectionHeadShadowAuthority.parse_callout(
        "64mm C-STUD FIRE PARTITION 1-HR DEEP LEG DEFLECTION TRACK"
    )
    assert parsed2["system_type"] == DrywallSystemType.STANDARD_FIRE_PARTITION
    assert parsed2["deflection_head_type"] == DeflectionHeadType.DEEP_LEG_NESTED_TRACK
    assert parsed2["stud_width_mm"] == 64.0
    assert parsed2["fire_rating_hours"] == 1

    parsed3 = SourceDrywallShaftwallDeflectionHeadShadowAuthority.parse_callout(
        "DOUBLE STUD ACOUSTIC WALL 2-HR INTUMESCENT HEAD TRACK"
    )
    assert parsed3["system_type"] == DrywallSystemType.ACOUSTIC_DOUBLE_STUD
    assert parsed3["deflection_head_type"] == DeflectionHeadType.FIRE_RATED_INTUMESCENT_TRACK
    assert parsed3["fire_rating_hours"] == 2
    assert parsed3["wall_height_m"] == 0.0
    assert parsed3["stud_width_mm"] == 0.0
    assert parsed3["deflection_allowance_mm"] == 0.0

    omitted_h = SourceDrywallShaftwallDeflectionHeadShadowAuthority.parse_callout(
        "64mm C-STUD FIRE PARTITION 1-HR DEEP LEG DEFLECTION TRACK"
    )
    assert omitted_h["wall_height_m"] == 0.0
    omitted_spec = DrywallPartitionSpec(wall_id="W-OMIT")
    assert omitted_spec.wall_height_m == 0.0
    assert omitted_spec.stud_width_mm == 0.0
    assert omitted_spec.deflection_allowance_mm == 0.0


def test_drywall_snapping():
    pt = (123.4, 456.7)
    snapped = SourceDrywallShaftwallDeflectionHeadShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_drywall_evaluation_quantities():
    raw_data = [
        {
            "wall_id": "W-01",
            "centerline_points": [(0.0, 0.0), (10000.0, 0.0)],
            "callout": "92mm STEEL STUD SHAFTWALL 2-HR W/ 25mm SHAFTLINER SLOTTED DEFLECTION HEAD H=3.5m",
            "level_id": "L01",
        },
        {
            "wall_id": "W-02",
            "centerline_points": [(0.0, 5000.0), (8000.0, 5000.0)],
            "callout": "64mm C-STUD FIRE PARTITION 1-HR FIXED HEAD H=3.0m",
            "level_id": "L01",
        },
    ]

    res = SourceDrywallShaftwallDeflectionHeadShadowAuthority.evaluate_partitions(raw_data, scale_ratio=0.001)

    assert len(res.walls) == 2
    q = res.quantities
    assert q.total_walls_count == 2
    # W-01: 10.0m len, H=3.5m -> Area = 35.0 m2, Slotted head = 10.0m, Shaftliner = 35.0 m2
    # W-02: 8.0m len, H=3.0m -> Area = 24.0 m2, Fixed head = 0m deflection head
    assert pytest.approx(q.total_linear_meters, 0.001) == 18.0
    assert pytest.approx(q.total_wall_area_m2, 0.001) == 59.0
    assert pytest.approx(q.deflection_head_linear_meters, 0.001) == 10.0
    assert pytest.approx(q.shaftwall_linear_meters, 0.001) == 10.0
    assert pytest.approx(q.shaftliner_core_area_m2, 0.001) == 35.0

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
