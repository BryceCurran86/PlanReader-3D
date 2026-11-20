"""Production wiring for inside-face footprint runtime stage."""
from __future__ import annotations

import fitz

from pb_external_footprint_inside_face_runtime import (
    exterior_wall_segments_from_drawings,
    run_inside_face_footprint_runtime_stage,
)


def _wall_drawings():
    return (
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
            "items": [("l", fitz.Point(260, 160), fitz.Point(150, 160))],
            "rect": fitz.Rect(150, 160, 260, 160),
        },
        {
            "layer": "Enclosure_WallExternal",
            "type": "s",
            "color": (0, 0, 0),
            "width": 2.5,
            "fill": None,
            "items": [("l", fitz.Point(150, 160), fitz.Point(40, 160))],
            "rect": fitz.Rect(40, 160, 150, 160),
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


def test_runtime_extracts_segments_and_emits_fail_closed_receipt():
    page = (0.0, 0.0, 400.0, 300.0)
    segs = exterior_wall_segments_from_drawings(_wall_drawings(), page_bounds_pdf_pts=page)
    assert len(segs) == 5
    receipt = run_inside_face_footprint_runtime_stage(
        _wall_drawings(), page_bounds_pdf_pts=page, page_index=0,
    )
    assert receipt["measurement_authorized"] is False
    assert receipt["commercial_publishable"] is False
    assert "inside_face_start" in receipt
    assert "clockwise_walk" in receipt
    assert "dual_dwelling" in receipt
    assert "interior_face_open_plan_07_10" in receipt
    assert receipt["interior_face_open_plan_07_10"]["commercial_publishable"] is False
    assert receipt["segment_count"] == 5
