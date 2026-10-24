"""
test_source_acoustic_baffle_cloud_shadow.py

Unit tests for SourceAcousticBaffleCloudShadowAuthority.
"""

import pytest
from pb_source_acoustic_baffle_cloud_shadow import (
    SourceAcousticBaffleCloudShadowAuthority,
    AcousticCeilingType,
    AcousticCeilingItemSpec,
    AcousticCeilingExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_acoustic_baffle_callout_parsing():
    parsed1 = SourceAcousticBaffleCloudShadowAuthority.parse_callout(
        "50x200mm VERTICAL PET ACOUSTIC BAFFLE AT 300mm CTS NRC=0.85 W/ AIRCRAFT WIRE SUSPENSION"
    )
    assert parsed1["ceiling_type"] == AcousticCeilingType.VERTICAL_SUSPENDED_BAFFLE
    assert parsed1["baffle_width_mm"] == 50.0
    assert parsed1["baffle_depth_mm"] == 200.0
    assert parsed1["spacing_cts_mm"] == 300.0
    assert parsed1["nrc_rating"] == 0.85

    parsed2 = SourceAcousticBaffleCloudShadowAuthority.parse_callout(
        "2400x1200 HORIZONTAL ACOUSTIC CLOUD RAFT NRC=0.90"
    )
    assert parsed2["ceiling_type"] == AcousticCeilingType.HORIZONTAL_RAFT_CLOUD
    assert parsed2["baffle_width_mm"] == 1200.0
    assert parsed2["nrc_rating"] == 0.90

    parsed3 = SourceAcousticBaffleCloudShadowAuthority.parse_callout(
        "30x100mm TIMBER SLATTED ACOUSTIC BAFFLE AT 150mm CTS"
    )
    assert parsed3["ceiling_type"] == AcousticCeilingType.TIMBER_SLATTED_BAFFLE
    assert parsed3["baffle_width_mm"] == 30.0
    assert parsed3["baffle_depth_mm"] == 100.0
    assert parsed3["spacing_cts_mm"] == 150.0

    parsed4 = SourceAcousticBaffleCloudShadowAuthority.parse_callout(
        "HEXAGONAL DIRECT FIX ACOUSTIC TILE NRC=0.75"
    )
    assert parsed4["ceiling_type"] == AcousticCeilingType.DIRECT_FIX_ACOUSTIC_TILE
    assert parsed4["nrc_rating"] == 0.75


def test_acoustic_baffle_point_snapping():
    pt = (300.3, 1200.8)
    snapped = SourceAcousticBaffleCloudShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (300.0, 1200.0)


def test_acoustic_baffle_evaluation_quantities():
    raw_data = [
        {
            "item_id": "AB-01",
            "centerline_points": [(0.0, 0.0), (3000.0, 0.0)],
            "callout": "50x200mm VERTICAL PET ACOUSTIC BAFFLE AT 300mm CTS NRC=0.85",
            "level_id": "L01",
            "room_id": "OFFICE-01",
        },
        {
            "item_id": "AB-02",
            "centerline_points": [(0.0, 1000.0), (2400.0, 1000.0)],
            "callout": "2400x1200 HORIZONTAL ACOUSTIC CLOUD RAFT NRC=0.90",
            "level_id": "L01",
            "room_id": "OFFICE-01",
        },
    ]

    result = SourceAcousticBaffleCloudShadowAuthority.evaluate_ceilings(raw_data)
    assert len(result.items) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_items_count == 2
    # AB-01: 3.0m, AB-02: 2.4m -> total = 5.4m
    assert pytest.approx(q.total_linear_meters, rel=1e-3) == 5.4

    # Effective absorption:
    # AB-01 (vertical 200mm depth, double sided): 2 * 0.2 * 3.0 = 1.2 m2
    # AB-02 (horizontal cloud 1200mm width): 1.2 * 2.4 = 2.88 m2
    # Total absorption: 1.2 + 2.88 = 4.08 m2
    assert pytest.approx(q.total_effective_absorption_m2, rel=1e-3) == 4.08

    # Suspension drops:
    # AB-01: max(2, 2 * ceil(3.0 / 1.5)) = 2 * 2 = 4 drops
    # AB-02: 4 drops (cloud)
    # Total drops: 8
    assert q.total_suspension_drops_count == 8

    assert q.linear_by_type[AcousticCeilingType.VERTICAL_SUSPENDED_BAFFLE.value] == 3.0
    assert q.linear_by_type[AcousticCeilingType.HORIZONTAL_RAFT_CLOUD.value] == 2.4
