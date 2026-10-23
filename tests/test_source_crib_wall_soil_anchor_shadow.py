"""
test_source_crib_wall_soil_anchor_shadow.py

Unit tests for SourceCribWallSoilAnchorShadowAuthority.
"""

import pytest
from pb_source_crib_wall_soil_anchor_shadow import (
    SourceCribWallSoilAnchorShadowAuthority,
    RetainingWallType,
    SoilAnchorType,
    RetainingWallRunSpec,
    RetainingWallExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_crib_wall_callout_parsing():
    parsed1 = SourceCribWallSoilAnchorShadowAuthority.parse_callout(
        "3.0m HIGH PRECAST CONCRETE CRIB RETAINING WALL 1:4 BATTER 1.8m HEADER DEPTH W/ CRUSHED ROCKFILL & DN100 AG DRAIN"
    )
    assert parsed1["wall_type"] == RetainingWallType.PRECAST_CONCRETE_CRIB_WALL
    assert parsed1["wall_height_m"] == 3.0
    assert parsed1["cell_depth_m"] == 1.8
    assert parsed1["batter_ratio"] == "1:4"
    assert parsed1["ag_drain_included"] is True

    parsed2 = SourceCribWallSoilAnchorShadowAuthority.parse_callout(
        "2.5m TIMBER CRIB WALL 1.2m DEPTH NO AG DRAIN"
    )
    assert parsed2["wall_type"] == RetainingWallType.TIMBER_CRIB_WALL
    assert parsed2["wall_height_m"] == 2.5
    assert parsed2["cell_depth_m"] == 1.2
    assert parsed2["ag_drain_included"] is False

    parsed3 = SourceCribWallSoilAnchorShadowAuthority.parse_callout(
        "4.0m REINFORCED SOIL NAIL WALL W/ 10x SOIL ANCHORS"
    )
    assert parsed3["wall_type"] == RetainingWallType.REINFORCED_SOIL_NAIL_WALL
    assert parsed3["wall_height_m"] == 4.0
    assert parsed3["soil_anchors_count"] == 10
    assert parsed3["anchor_type"] == SoilAnchorType.SELF_DRILLING_GROUTED_ANCHOR

    parsed4 = SourceCribWallSoilAnchorShadowAuthority.parse_callout(
        "SOLDIER PILE WALL 3.5m HIGH"
    )
    assert parsed4["wall_type"] == RetainingWallType.SOLDIER_PILE_PANEL_WALL
    assert parsed4["wall_height_m"] == 3.5


def test_crib_wall_point_snapping():
    pt = (1001.3, 2000.8)
    snapped = SourceCribWallSoilAnchorShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (1002.5, 2000.0)


def test_crib_wall_polyline_length():
    points = [(0.0, 0.0), (20000.0, 0.0)]
    length = SourceCribWallSoilAnchorShadowAuthority.calculate_polyline_length(points, scale_ratio=0.001)
    assert pytest.approx(length, rel=1e-3) == 20.0


def test_crib_wall_evaluation_quantities():
    raw_data = [
        {
            "wall_id": "RW-01",
            "centerline_points": [(0.0, 0.0), (20000.0, 0.0)],
            "callout": "3.0m HIGH PRECAST CONCRETE CRIB RETAINING WALL 1:4 BATTER 1.8m HEADER DEPTH W/ CRUSHED ROCKFILL & DN100 AG DRAIN",
            "level_id": "SITE",
        },
        {
            "wall_id": "RW-02",
            "centerline_points": [(0.0, 5000.0), (10000.0, 5000.0)],
            "callout": "4.0m REINFORCED SOIL NAIL WALL W/ 10x SOIL ANCHORS",
            "level_id": "SITE",
        },
    ]

    result = SourceCribWallSoilAnchorShadowAuthority.evaluate_walls(raw_data)
    assert len(result.runs) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_walls_count == 2
    # RW-01: 20m, RW-02: 10m -> total = 30m
    assert pytest.approx(q.total_wall_length_meters, rel=1e-3) == 30.0

    # Face area:
    # RW-01: 20 * 3.0 = 60.0 m2
    # RW-02: 10 * 4.0 = 40.0 m2
    # Total: 100.0 m2
    assert pytest.approx(q.total_face_area_m2, rel=1e-3) == 100.0

    # Rockfill volume:
    # RW-01: 20 * 3.0 * 1.8 = 108.0 m3
    # RW-02: 10 * 4.0 * 0.3 = 12.0 m3
    # Total: 120.0 m3
    assert pytest.approx(q.total_rockfill_volume_m3, rel=1e-3) == 120.0

    # AG drain: RW-01 has AG drain (20m), RW-02 has AG drain (10m) -> 30m
    assert pytest.approx(q.total_ag_drain_meters, rel=1e-3) == 30.0

    # Soil anchors: RW-01 (0) + RW-02 (10) = 10
    assert q.total_soil_anchors_count == 10

    assert q.length_by_type[RetainingWallType.PRECAST_CONCRETE_CRIB_WALL.value] == 20.0
    assert q.length_by_type[RetainingWallType.REINFORCED_SOIL_NAIL_WALL.value] == 10.0
