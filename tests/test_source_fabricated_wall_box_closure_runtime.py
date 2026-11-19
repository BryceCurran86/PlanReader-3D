"""#4443 production stage: fabricated boxes collapse; alcoves/doors kept."""
from __future__ import annotations

from pb_source_fabricated_wall_box_closure_runtime import (
    run_fabricated_wall_box_closure_stage,
)
from pb_structural_wall_ink_shadow import OpeningGapCandidate


def _rect_poly_with_two_boxes():
    return [
        (0.0, 100.0),
        (40.0, 100.0),
        (40.0, 40.0),
        (70.0, 40.0),
        (70.0, 100.0),
        (120.0, 100.0),
        (120.0, 40.0),
        (150.0, 40.0),
        (150.0, 100.0),
        (200.0, 100.0),
        (200.0, 300.0),
        (0.0, 300.0),
    ]


def _straight_walls():
    return (
        (0.0, 100.0, 200.0, 100.0),
        (200.0, 100.0, 200.0, 300.0),
        (200.0, 300.0, 0.0, 300.0),
        (0.0, 300.0, 0.0, 100.0),
    )


def test_two_fabricated_boxes_collapse_on_production_stage():
    r = run_fabricated_wall_box_closure_stage(
        exterior_polygon_pdf_pts=_rect_poly_with_two_boxes(),
        wall_ink_segments=_straight_walls(),
    )
    assert r.collapsed_detour_count == 2
    assert not any(abs(p[1] - 40.0) <= 1.0 for p in r.polygon_pdf_pts)
    assert r.measurement_authorized is False
    assert r.to_dict()["owner_issue"] == 4443


def test_genuine_alcove_retained():
    poly = [
        (0.0, 100.0),
        (40.0, 100.0),
        (40.0, 40.0),
        (70.0, 40.0),
        (70.0, 100.0),
        (200.0, 100.0),
        (200.0, 300.0),
        (0.0, 300.0),
    ]
    walls = (
        (0.0, 100.0, 40.0, 100.0),
        (40.0, 100.0, 40.0, 40.0),
        (40.0, 40.0, 70.0, 40.0),
        (70.0, 40.0, 70.0, 100.0),
        (70.0, 100.0, 200.0, 100.0),
        (200.0, 100.0, 200.0, 300.0),
        (200.0, 300.0, 0.0, 300.0),
        (0.0, 300.0, 0.0, 100.0),
    )
    r = run_fabricated_wall_box_closure_stage(
        exterior_polygon_pdf_pts=poly, wall_ink_segments=walls,
    )
    assert r.collapsed_detour_count == 0
    assert any(abs(p[1] - 40.0) <= 1.0 for p in r.polygon_pdf_pts)


def test_typed_door_closes_room_false_gap_suppressed():
    scene = [
        {"id": "top.a", "x1": 100, "y1": 100, "x2": 170, "y2": 100},
        {"id": "top.b", "x1": 220, "y1": 100, "x2": 400, "y2": 100},
        {"id": "right", "x1": 400, "y1": 100, "x2": 400, "y2": 300},
        {"id": "bottom", "x1": 400, "y1": 300, "x2": 100, "y2": 300},
        {"id": "left", "x1": 100, "y1": 300, "x2": 100, "y2": 100},
    ]
    door = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "top.a", "top.b")
    poly = [(100, 100), (400, 100), (400, 300), (100, 300)]
    r = run_fabricated_wall_box_closure_stage(
        exterior_polygon_pdf_pts=poly,
        wall_ink_segments=(
            (100, 100, 170, 100),
            (220, 100, 400, 100),
            (400, 100, 400, 300),
            (400, 300, 100, 300),
            (100, 300, 100, 100),
        ),
        wall_network_segments=scene,
        opening_gaps=(door,),
        room_labels=("LIVING", "KITCHEN"),
    )
    assert r.room_region_count == 1
    assert r.doorway_closure_count == 1
    assert r.open_plan_merged is True
    assert r.to_dict()["doorway_closure_is_not_physical_wall"] is True


def test_continuous_wall_suppresses_false_opening_gap():
    scene = [
        {"id": "top", "x1": 100, "y1": 100, "x2": 400, "y2": 100},
        {"id": "right", "x1": 400, "y1": 100, "x2": 400, "y2": 300},
        {"id": "bottom", "x1": 400, "y1": 300, "x2": 100, "y2": 300},
        {"id": "left", "x1": 100, "y1": 300, "x2": 100, "y2": 100},
    ]
    ghost = OpeningGapCandidate((170, 100), (220, 100), 50, 2.6, "ghost.a", "ghost.b")
    r = run_fabricated_wall_box_closure_stage(
        exterior_polygon_pdf_pts=[(100, 100), (400, 100), (400, 300), (100, 300)],
        wall_ink_segments=((100, 100, 400, 100), (400, 100, 400, 300),
                           (400, 300, 100, 300), (100, 300, 100, 100)),
        wall_network_segments=scene,
        opening_gaps=(ghost,),
    )
    assert r.suppressed_false_gap_count == 1
    assert r.doorway_closure_count == 0
