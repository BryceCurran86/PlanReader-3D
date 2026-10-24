"""
test_source_expansion_joint_cover_shadow.py

Unit tests for SourceExpansionJointCoverShadowAuthority.
"""

import pytest
from pb_source_expansion_joint_cover_shadow import (
    SourceExpansionJointCoverShadowAuthority,
    CoverSystemType,
    JointLocation,
    ExpansionJointCoverSpec,
    ExpansionJointCoverExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_expansion_joint_callout_parsing():
    parsed1 = SourceExpansionJointCoverShadowAuthority.parse_callout(
        "50mm GAP FLUSH ELASTOMERIC FLOOR JOINT COVER W/ 2-HR FIRE BARRIER"
    )
    assert parsed1["gap_width_mm"] == 50.0
    assert parsed1["system_type"] == CoverSystemType.FLUSH_ELASTOMERIC
    assert parsed1["location"] == JointLocation.FLOOR
    assert parsed1["has_fire_barrier"] is True
    assert parsed1["fire_rating_hours"] == 2
    assert parsed1["has_moisture_barrier"] is False

    parsed2 = SourceExpansionJointCoverShadowAuthority.parse_callout(
        "EJ-100 HEAVY DUTY ALL-METAL PLATE COVER EPDM GUTTER"
    )
    assert parsed2["gap_width_mm"] == 100.0
    assert parsed2["system_type"] == CoverSystemType.ALL_METAL_HEAVY_DUTY
    assert parsed2["has_moisture_barrier"] is True

    parsed3 = SourceExpansionJointCoverShadowAuthority.parse_callout(
        "75mm VERTICAL WALL EXPANSION JOINT COVER"
    )
    assert parsed3["gap_width_mm"] == 75.0
    assert parsed3["location"] == JointLocation.WALL
    assert parsed3["system_type"] == CoverSystemType.VERTICAL_WALL_COVER


def test_expansion_joint_snapping():
    pt = (100.8, 201.7)
    snapped = SourceExpansionJointCoverShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    # 100.8 / 2.5 = 40.32 -> round = 40 -> 40 * 2.5 = 100.0
    # 201.7 / 2.5 = 80.68 -> round = 81 -> 81 * 2.5 = 202.5
    assert snapped == (100.0, 202.5)


def test_expansion_joint_evaluation_quantities():
    raw_data = [
        {
            "joint_id": "EJ-01",
            "centerline_points": [(0.0, 0.0), (10000.0, 0.0)],
            "callout": "50mm FLUSH ELASTOMERIC FLOOR COVER W/ 2-HR FIRE BARRIER",
            "level_id": "L01",
        },
        {
            "joint_id": "EJ-02",
            "centerline_points": [(0.0, 5000.0), (5000.0, 5000.0)],
            "callout": "100mm HEAVY DUTY ALL-METAL COVER EPDM GUTTER",
            "level_id": "L01",
        },
        {
            "joint_id": "EJ-03",
            "centerline_points": [(0.0, 0.0), (0.0, 3000.0)],
            "callout": "75mm VERTICAL WALL EXPANSION JOINT COVER",
            "level_id": "L01",
        },
    ]

    res = SourceExpansionJointCoverShadowAuthority.evaluate_joints(raw_data, scale_ratio=0.001)

    assert len(res.joints) == 3
    q = res.quantities
    assert q.total_joints_count == 3
    # EJ-01: 10000mm = 10.0m
    # EJ-02: 5000mm = 5.0m
    # EJ-03: 3000mm = 3.0m
    assert pytest.approx(q.total_linear_meters, 0.001) == 18.0
    assert pytest.approx(q.floor_cover_linear_meters, 0.001) == 15.0
    assert pytest.approx(q.wall_cover_linear_meters, 0.001) == 3.0
    assert pytest.approx(q.ceiling_cover_linear_meters, 0.001) == 0.0
    assert pytest.approx(q.fire_barrier_linear_meters, 0.001) == 10.0
    assert pytest.approx(q.moisture_barrier_linear_meters, 0.001) == 5.0

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
