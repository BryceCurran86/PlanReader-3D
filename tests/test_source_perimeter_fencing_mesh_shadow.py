"""
test_source_perimeter_fencing_mesh_shadow.py

Unit tests for SourcePerimeterFencingMeshShadowAuthority.
"""

import math
import pytest
from pb_source_perimeter_fencing_mesh_shadow import (
    SourcePerimeterFencingMeshShadowAuthority,
    SecurityFencingType,
    FencingToppingType,
    SecurityFenceRunSpec,
    SecurityFencingExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_fencing_callout_parsing():
    parsed1 = SourcePerimeterFencingMeshShadowAuthority.parse_callout(
        "2.4m HIGH 358 ANTI-CLIMB WELDED MESH FENCING ON 75x75 SHS POSTS AT 2.5m CTS W/ 3 STRANDS BARBED WIRE"
    )
    assert parsed1["fencing_type"] == SecurityFencingType.ANTI_CLIMB_358_WELDED_MESH
    assert parsed1["fence_height_m"] == 2.4
    assert parsed1["post_spacing_m"] == 2.5
    assert parsed1["post_section"] == "75x75 SHS"
    assert parsed1["topping_type"] == FencingToppingType.BARBED_WIRE_3_STRANDS

    parsed2 = SourcePerimeterFencingMeshShadowAuthority.parse_callout(
        "2.1m CHAIN LINK FABRIC FENCE ON 65 NB POSTS AT 3.0m CTS"
    )
    assert parsed2["fencing_type"] == SecurityFencingType.CHAIN_LINK_FABRIC
    assert parsed2["fence_height_m"] == 2.1
    assert parsed2["post_spacing_m"] == 3.0
    assert parsed2["topping_type"] == FencingToppingType.NO_TOPPING

    parsed3 = SourcePerimeterFencingMeshShadowAuthority.parse_callout(
        "2.4m STEEL PALISADE SECURITY FENCE ON 100x100 SHS W/ RAZOR WIRE"
    )
    assert parsed3["fencing_type"] == SecurityFencingType.STEEL_PALISADE
    assert parsed3["topping_type"] == FencingToppingType.RAZOR_WIRE_CONCERTINA

    parsed4 = SourcePerimeterFencingMeshShadowAuthority.parse_callout(
        "1.8m TUBULAR PICKET BALUSTRADE"
    )
    assert parsed4["fencing_type"] == SecurityFencingType.TUBULAR_PICKET
    assert parsed4["fence_height_m"] == 1.8


def test_fencing_point_snapping():
    pt = (124.6, 253.9)
    snapped = SourcePerimeterFencingMeshShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (125.0, 255.0)


def test_fencing_polyline_length():
    points = [(0.0, 0.0), (50000.0, 0.0)]
    length = SourcePerimeterFencingMeshShadowAuthority.calculate_polyline_length(points, scale_ratio=0.001)
    assert pytest.approx(length, rel=1e-3) == 50.0


def test_fencing_evaluation_quantities():
    raw_data = [
        {
            "run_id": "FN-01",
            "centerline_points": [(0.0, 0.0), (50000.0, 0.0)],
            "callout": "2.4m HIGH 358 ANTI-CLIMB WELDED MESH FENCING ON 75x75 SHS POSTS AT 2.5m CTS",
            "level_id": "SITE",
        },
        {
            "run_id": "FN-02",
            "centerline_points": [(50000.0, 0.0), (50000.0, 30000.0)],
            "callout": "2.1m CHAIN LINK FABRIC FENCE ON 65 NB POSTS AT 3.0m CTS",
            "level_id": "SITE",
        },
    ]

    result = SourcePerimeterFencingMeshShadowAuthority.evaluate_fencing_runs(raw_data)
    assert len(result.runs) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_runs_count == 2
    # FN-01 length = 50.0m, FN-02 length = 30.0m -> total = 80.0m
    assert pytest.approx(q.total_fence_length_meters, rel=1e-3) == 80.0

    # Mesh area:
    # FN-01: 50.0 * 2.4 = 120.0 m2
    # FN-02: 30.0 * 2.1 = 63.0 m2
    # Total area: 183.0 m2
    assert pytest.approx(q.total_mesh_area_m2, rel=1e-3) == 183.0

    # Posts:
    # FN-01: ceil(50.0 / 2.5) + 1 = 20 + 1 = 21 posts
    # FN-02: ceil(30.0 / 3.0) + 1 = 10 + 1 = 11 posts
    # Total posts: 32 posts
    assert q.total_posts_count == 32

    # Concrete volume:
    # 300mm dia (r = 0.15m), 800mm depth (h = 0.8m)
    # per post = pi * 0.15^2 * 0.8 = 0.05655 m3
    # 32 posts * 0.05655 m3 = ~1.8095 m3
    assert pytest.approx(q.total_footing_concrete_m3, rel=1e-2) == 1.8095

    assert SecurityFencingType.ANTI_CLIMB_358_WELDED_MESH.value in q.length_by_type
    assert SecurityFencingType.CHAIN_LINK_FABRIC.value in q.length_by_type
