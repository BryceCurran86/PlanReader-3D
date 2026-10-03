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


def _rotated_framed_plan(*, rotation: int = 90):
    doc = fitz.open()
    page = doc.new_page(width=600.0, height=800.0)
    frame = fitz.Rect(60.0, 80.0, 500.0, 650.0)
    page.draw_rect(frame, color=(0, 0, 0), width=1.0)

    # Dense plans commonly contain far more than eight rectangle primitives.
    # Keep a repeated same-size family, but deliberately not a row/column grid:
    # count alone must never make the physical drawing frame look like a table.
    for index in range(12):
        x0 = 80.0 + index * 24.0
        y0 = 110.0 + index * 28.0
        page.draw_rect(
            fitz.Rect(x0, y0, x0 + 12.0, y0 + 8.0),
            color=(0, 0, 0),
            width=0.5,
        )

    # Mirror a real /Rotate 90 CAD convention: the visually horizontal drawing
    # title is authored vertically in native space, just to the right of the
    # native frame. After page rotation it appears directly below the frame.
    page.insert_text(
        (530.0, 300.0),
        "GROUND FLOOR PLAN",
        fontsize=12.0,
        rotate=90,
    )

    # Reference furniture exists elsewhere on the same sheet and must not
    # prevent the framed physical plan from owning its own geometry.
    page.insert_text((100.0, 720.0), "LEGEND", fontsize=12.0)
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
        floor_rows = [row for row in rows if row.view_type == "floor_plan"]
        legend_rows = [row for row in rows if row.view_type == "legend"]

        assert len(floor_rows) == 1
        floor = floor_rows[0]
        assert floor.status == ViewportSegmentationStatus.RESOLVED.value
        assert floor.bounding_box == pytest.approx(
            (frame.x0, frame.y0, frame.x1, frame.y1)
        )

        # Native-space placement is to the right of the frame.
        assert floor.title_bbox[0] > frame.x1

        # Visual-space placement is the normal drawing-title convention:
        # horizontally overlapping and immediately below the frame.
        visual_frame = fitz.Rect(frame) * page.rotation_matrix
        visual_title = fitz.Rect(floor.title_bbox) * page.rotation_matrix
        assert visual_title.y0 > visual_frame.y1
        assert visual_title.y0 - visual_frame.y1 < 30.0
        assert visual_title.x1 > visual_frame.x0
        assert visual_title.x0 < visual_frame.x1

        assert len(legend_rows) == 1
        assert (
            legend_rows[0].status
            == ViewportSegmentationStatus.UNSUPPORTED.value
        )
        assert legend_rows[0].bounding_box is None
    finally:
        doc.close()


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
