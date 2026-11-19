"""Production wiring for Cursor-07..10 interior-face / open-plan runtime."""
from __future__ import annotations

import fitz

from pb_external_footprint_inside_face_runtime import (
    run_inside_face_footprint_runtime_stage,
)
from pb_source_interior_face_open_plan_runtime import (
    discover_room_labels_from_words,
    run_interior_face_open_plan_runtime_stage,
)


def _words(*pairs: tuple[str, tuple[float, float, float, float]]):
    return tuple((b[0], b[1], b[2], b[3], text, 0, 0, 0) for text, b in pairs)


def test_discover_labels_unique_only_no_boq_hardcode():
    words = _words(
        ("SCALE", (0, 0, 10, 5)),
        ("WIR", (20, 20, 40, 30)),
        ("BED", (50, 20, 70, 30)),
        ("2", (72, 20, 80, 30)),
        ("LIVING", (100, 40, 140, 50)),
        ("LIVING", (200, 40, 240, 50)),  # duplicate → not unique
    )
    labels = discover_room_labels_from_words(words)
    assert "WIR" in labels
    assert "BED 2" in labels
    assert "LIVING" not in labels  # not unique


def test_runtime_false_wall_thickness_veto_and_fail_closed():
    drawings = (
        {"layer": "WallInternal", "rect": (0.0, 0.0, 40.0, 0.02)},
        {"layer": "WallInternal", "rect": (0.0, 20.0, 40.0, 20.02)},
        {"layer": "Door", "path_id": 7, "rect": (10.0, 10.0, 12.0, 14.0)},
    )
    words = _words(("BED", (10, 8, 30, 12)), ("2", (31, 8, 40, 12)))
    receipt = run_interior_face_open_plan_runtime_stage(
        drawings, source_words=words, page_index=0, source_sha256="a" * 64,
    )
    assert receipt["measurement_authorized"] is False
    assert receipt["commercial_publishable"] is False
    assert receipt["official_frozen120_score_change"] == 0
    faces = receipt["finished_interior_faces"]["candidates"]
    assert faces and faces[0]["reason"] == "false_wall_thickness_veto"
    assert receipt["open_plan_room_rings"]["status"] == "ABSTAINED"
    assert receipt["opening_host_correlation_index"]["status"] == "CANDIDATE"
    assert receipt["live_trace_diagnostics"]["visual_output_non_commercial"] is True


def test_open_plan_present_when_living_kitchen_on_page():
    drawings = ({"layer": "WallInternal", "rect": (0.0, 0.0, 40.0, 4.0)},)
    words = _words(("LIVING", (10, 10, 40, 20)), ("KITCHEN", (50, 10, 90, 20)))
    receipt = run_interior_face_open_plan_runtime_stage(
        drawings, source_words=words, page_index=1, source_sha256="b" * 64,
    )
    open_plan = receipt["open_plan_room_rings"]
    assert open_plan["invented_partition_count"] == 0
    assert open_plan["commercial_publishable"] is False
    assert "LIVING" in open_plan["open_section_labels"]
    assert "KITCHEN" in open_plan["open_section_labels"]


def test_footprint_runtime_includes_07_10_stage():
    drawings = (
        {
            "layer": "Enclosure_WallExternal",
            "type": "s",
            "color": (0, 0, 0),
            "width": 2.5,
            "fill": None,
            "items": [("l", fitz.Point(40, 40), fitz.Point(260, 40))],
            "rect": fitz.Rect(40, 40, 260, 40),
        },
        {
            "layer": "Enclosure_WallExternal",
            "type": "s",
            "color": (0, 0, 0),
            "width": 2.5,
            "fill": None,
            "items": [("l", fitz.Point(260, 40), fitz.Point(260, 160))],
            "rect": fitz.Rect(260, 40, 260, 160),
        },
        {
            "layer": "Enclosure_WallExternal",
            "type": "s",
            "color": (0, 0, 0),
            "width": 2.5,
            "fill": None,
            "items": [("l", fitz.Point(260, 160), fitz.Point(40, 160))],
            "rect": fitz.Rect(40, 160, 260, 160),
        },
        {
            "layer": "Enclosure_WallExternal",
            "type": "s",
            "color": (0, 0, 0),
            "width": 2.5,
            "fill": None,
            "items": [("l", fitz.Point(40, 160), fitz.Point(40, 40))],
            "rect": fitz.Rect(40, 40, 40, 160),
        },
    )
    receipt = run_inside_face_footprint_runtime_stage(
        drawings,
        page_bounds_pdf_pts=(0.0, 0.0, 400.0, 300.0),
        source_words=_words(("WIR", (80, 80, 110, 95))),
        page_index=0,
        source_sha256="c" * 64,
    )
    assert "interior_face_open_plan_07_10" in receipt
    stage = receipt["interior_face_open_plan_07_10"]
    assert stage["commercial_publishable"] is False
    assert "Cursor-07" in stage["tasks_covered"]
    assert receipt["measurement_authorized"] is False
