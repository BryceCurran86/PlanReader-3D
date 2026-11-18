"""#4549-21..31 room/trace acceptance runtime."""
from __future__ import annotations

from pb_source_room_trace_acceptance_runtime import (
    RoomRing,
    build_source_trace_regression_packet,
    combine_open_plan_living_kitchen,
    cross_scale_invariant_check,
    emit_live_trace_steps,
    filter_green_exclusion_graphics,
    inside_finished_face_measurement_policy,
    refuse_title_block_as_walls,
    run_room_trace_acceptance_stage,
    split_rooms_by_door_thresholds,
    validate_watertight_polygon,
)


def test_21_watertight_and_self_intersection():
    ok = validate_watertight_polygon(((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)))
    assert ok["watertight"] is True
    bad = validate_watertight_polygon(((0, 0), (10, 10), (10, 0), (0, 10), (0, 0)))
    assert bad["status"] == "ABSTAINED"


def test_22_23_doorway_split_and_open_plan():
    rooms = (
        RoomRing("A", ((0, 0), (5, 0), (5, 5), (0, 5), (0, 0)), split_by="doorway"),
    )
    assert split_rooms_by_door_thresholds(rooms)["furniture_splits_rejected"] == 0
    merged = combine_open_plan_living_kitchen(
        ("LIVING", "KITCHEN"), has_physical_or_marked_boundary=False,
    )
    assert merged["combined_label"] == "LIVING_KITCHEN"


def test_24_28_29_guards():
    assert filter_green_exclusion_graphics(
        wall_candidates=10, green_mask_pixels=100, green_as_wall_promotions=0,
    )["status"] == "CANDIDATE"
    assert refuse_title_block_as_walls(
        candidate_bbox=(10, 90, 90, 99), page_bounds=(0, 0, 100, 100),
    )["accepted_as_wall"] is False
    assert inside_finished_face_measurement_policy(
        measured_to="centerline",
    )["status"] == "ABSTAINED"


def test_26_27_30_31():
    assert emit_live_trace_steps(
        ({"action": "start", "evidence": "wall", "confidence": 0.8},),
    )["status"] == "CANDIDATE"
    assert cross_scale_invariant_check(
        area_a=100.0, area_b=400.0, scale_ratio=2.0,
    )["status"] == "CANDIDATE"
    pkt = build_source_trace_regression_packet(
        project_key="Lot16",
        source_sha256="a" * 64,
        before_polygon=((0, 0), (1, 0), (1, 1), (0, 0)),
        after_polygon=((0, 0), (2, 0), (2, 2), (0, 0)),
    )
    assert pkt["uses_benchmark_gold_as_input"] is False


def test_bundle():
    b = run_room_trace_acceptance_stage(
        polygon_pdf_pts=((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)),
        room_labels=("LIVING",),
        wall_candidates=3,
        green_mask_pixels=10,
        measured_to="inside_finished_face",
        area_a=1.0,
        area_b=1.0,
        scale_ratio=1.0,
        project_key="3Laurel",
        source_sha256="b" * 64,
        candidate_bbox=(20, 20, 40, 40),
        page_bounds=(0, 0, 100, 100),
        trace_steps=({"action": "step", "evidence": "e", "confidence": 0.5},),
    )
    assert b["measurement_authorized"] is False
    assert "21" in b["tasks_covered"]
