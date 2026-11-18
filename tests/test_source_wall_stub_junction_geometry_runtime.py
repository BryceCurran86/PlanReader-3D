"""#4549-11..15 posts, stubs, T-junctions, rail corners, cross-page scale."""
from __future__ import annotations

from pb_source_wall_stub_junction_geometry_runtime import (
    GeometryPrimitive,
    align_cross_page_footprint_scale,
    classify_door_versus_timber_post,
    detect_t_junctions,
    reconstruct_short_wall_stubs,
    run_wall_stub_junction_geometry_stage,
    suppress_rail_shadow_corners,
)


def test_11_timber_post_not_promoted_to_wall():
    post = GeometryPrimitive(1, (10, 10), (14, 14), kind="post", label="140x140 POST")
    wall = GeometryPrimitive(2, (0, 0), (100, 0), kind="wall")
    r = classify_door_versus_timber_post(post, nearby=(post, wall))
    assert r["promote_to_wall"] is False
    assert r["role"] == "timber_post_not_wall"


def test_11_door_retained_as_opening_not_wall():
    door = GeometryPrimitive(3, (40, 0), (60, 0), kind="door", label="D12")
    r = classify_door_versus_timber_post(door)
    assert r["promote_to_wall"] is False
    assert r["role"] == "door_object"


def test_12_unique_perpendicular_stub_join():
    a = GeometryPrimitive(1, (0, 0), (50, 0))
    b = GeometryPrimitive(2, (52, 0), (52, 40))  # 2pt gap, perpendicular
    r = reconstruct_short_wall_stubs((a, b))
    assert r["status"] == "CANDIDATE"
    assert len(r["stub_joins"]) == 1
    assert r["stub_joins"][0]["join"] == "perpendicular"


def test_13_t_junction_without_phantom_extension():
    bar = GeometryPrimitive(1, (0, 20), (100, 20))
    stem = GeometryPrimitive(2, (50, 20), (50, 80))
    r = detect_t_junctions((bar, stem))
    assert r["status"] == "CANDIDATE"
    assert any(j.get("phantom_extension") is False and "crossbar_id" in j for j in r["junctions"])


def test_14_rail_shadow_corner_suppressed():
    rail = GeometryPrimitive(1, (10, 10), (10.2, 10.2), kind="rail_shadow", stroke_weight_pt=0.2)
    wall = GeometryPrimitive(2, (0, 0), (80, 0), stroke_weight_pt=2.0)
    r = suppress_rail_shadow_corners(
        (rail, wall), corner_candidates=((10, 10), (80, 0)),
    )
    assert r["suppressed_count"] == 1
    assert r["kept_corners"] == [[80.0, 0.0]]


def test_15_cross_page_scale_from_anchors_or_abstain():
    ok = align_cross_page_footprint_scale(
        cover_anchor_pdf_pts=((0, 0), (100, 0)),
        plan_anchor_pdf_pts=((0, 0), (200, 0)),
        cover_page_index=0,
        plan_page_index=2,
    )
    assert ok["status"] == "CANDIDATE"
    assert ok["scale_plan_per_cover"] == 2.0
    bad = align_cross_page_footprint_scale(
        cover_anchor_pdf_pts=((0, 0),),
        plan_anchor_pdf_pts=((0, 0), (10, 0)),
        cover_page_index=0,
        plan_page_index=2,
    )
    assert bad["status"] == "ABSTAINED"


def test_bundle_fail_closed():
    prims = (
        GeometryPrimitive(1, (0, 0), (80, 0)),
        GeometryPrimitive(2, (0, 0), (0, 60)),
        GeometryPrimitive(9, (5, 5), (8, 8), kind="post", label="POST"),
    )
    bundle = run_wall_stub_junction_geometry_stage(prims, corner_candidates=((0, 0),))
    assert bundle["measurement_authorized"] is False
    assert bundle["commercial_publishable"] is False
    assert "11" in bundle["tasks_covered"]
