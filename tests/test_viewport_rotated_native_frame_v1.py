from __future__ import annotations

import fitz
import pytest

from pb_native_page_frame import (
    NATIVE_PAGE_FRAME_UNRESOLVED,
    NativePageFrameUnresolved,
    native_page_frame,
)
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    calibrate_viewport_layout,
    segment_page_viewports,
)


def _rotated_framed_plan(*, rotation: int = 90, title: str = "GROUND FLOOR PLAN"):
    doc = fitz.open()
    page = doc.new_page(width=600.0, height=800.0)
    frame = fitz.Rect(60.0, 80.0, 500.0, 650.0)
    page.draw_rect(frame, color=(0, 0, 0), width=1.0)
    page.insert_text((150.0, 690.0), title, fontsize=12.0)
    # Reference furniture exists elsewhere on the same sheet and must not
    # prevent the framed physical plan from owning its own geometry.
    page.insert_text((530.0, 150.0), "LEGEND", fontsize=12.0)
    page.set_rotation(rotation)
    return doc, page, frame


def test_rotation_90_viewport_calibration_uses_native_extent() -> None:
    doc, page, _frame = _rotated_framed_plan()
    try:
        assert tuple(page.rect) == (0.0, 0.0, 800.0, 600.0)
        native = native_page_frame(page)
        assert (native.native_width, native.native_height) == (600.0, 800.0)
        calibration = calibrate_viewport_layout(page)
        assert calibration.page_width_pt == 600.0
        assert calibration.page_height_pt == 800.0
    finally:
        doc.close()


def test_rotated_framed_floor_plan_resolves_beside_unbounded_legend() -> None:
    doc, page, frame = _rotated_framed_plan()
    try:
        rows = segment_page_viewports(page, page_number=1)
    finally:
        doc.close()

    floor_rows = [row for row in rows if row.view_type == "floor_plan"]
    legend_rows = [row for row in rows if row.view_type == "legend"]

    assert len(floor_rows) == 1
    floor = floor_rows[0]
    assert floor.status == ViewportSegmentationStatus.RESOLVED.value
    assert floor.bounding_box == pytest.approx(
        (frame.x0, frame.y0, frame.x1, frame.y1)
    )

    assert len(legend_rows) == 1
    assert legend_rows[0].status != ViewportSegmentationStatus.RESOLVED.value
    assert legend_rows[0].bounding_box is None


@pytest.mark.parametrize("rotation", [180, 270])
def test_unvalidated_rotations_do_not_mint_viewport_authority(rotation: int) -> None:
    doc, page, _frame = _rotated_framed_plan(rotation=rotation)
    try:
        with pytest.raises(
            NativePageFrameUnresolved,
            match=NATIVE_PAGE_FRAME_UNRESOLVED,
        ):
            native_page_frame(page)
        assert segment_page_viewports(page, page_number=1) == []
    finally:
        doc.close()


@pytest.mark.parametrize("title", ["PROP. FLOOR PLAN", "PROPOSED FLOOR PLAN"])
def test_rotated_proposed_floor_plan_title_resolves_vector_frame(title: str) -> None:
    doc, page, frame = _rotated_framed_plan(title=title)
    try:
        rows = segment_page_viewports(page, page_number=1)
    finally:
        doc.close()

    floor_rows = [row for row in rows if row.view_type == "floor_plan"]
    assert len(floor_rows) == 1
    floor = floor_rows[0]
    assert floor.label == title
    assert floor.status == ViewportSegmentationStatus.RESOLVED.value
    assert floor.bounding_box == pytest.approx(
        (frame.x0, frame.y0, frame.x1, frame.y1)
    )
