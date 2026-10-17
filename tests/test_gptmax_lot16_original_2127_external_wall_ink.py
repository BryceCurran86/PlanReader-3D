"""SHA-authenticated ORIGINAL 2127 STACKER external wall source-ink regression.

This verifies only the original two solid raster flank footprints. It does
NOT assert physical opening identity, unique W4 structural host, frame,
schedule count, customer seal, or FIRM area. Those remain downstream gates.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytest

from pb_raster_unchanged_band_segments import (
    detect_original_one_ended_ink_band_segments,
)
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT


ORIGINAL = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
SHA256 = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
DPI = 300
# Original plan-only, images-only G17 band envelopes located on the very
# SAME south external wall as the p3 and p5 2127 STACKER callouts. The boxes
# are ORIGINAL ink census fixtures, never passed to a production authority.
LEFT = ("horizontal", (716.16, 426.48, 760.32, 429.36))
RIGHT = ("horizontal", (836.4, 426.48, 949.68, 429.36))


@pytest.fixture(scope="module")
def original_page3_images():
    original_bytes = ORIGINAL.read_bytes()
    assert sha256(original_bytes).hexdigest() == SHA256
    source = fitz.open(stream=original_bytes, filetype="pdf")
    image_only = fitz.open()
    try:
        assert len(source) == 13 and source[2].rotation == 0
        image_only.insert_pdf(source, from_page=2, to_page=2)
        p3 = image_only[0]
        p3.add_redact_annot(p3.rect, fill=False)
        p3.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
            text=fitz.PDF_REDACT_TEXT_REMOVE,
        )
        mat = fitz.Matrix(DPI / 72.0, DPI / 72.0)
        ink = p3.get_pixmap(matrix=mat, alpha=False, annots=False).tobytes("png")
        full = source[2].get_pixmap(
            matrix=mat, alpha=False, annots=False
        ).tobytes("png")
        return ink, full
    finally:
        image_only.close()
        source.close()


def _segments(ink, full):
    return detect_original_one_ended_ink_band_segments(
        ink, full, dpi=DPI, source_closed_flank_boxes=(LEFT, RIGHT),
    )


def test_original_both_2127_host_wall_sides_have_full_owned_ink(original_page3_images):
    ink, full = original_page3_images
    segments = _segments(ink, full)
    assert len(segments) == 2
    assert {s.pixel_support_bounds for s in segments} == {
        (2984, 1777, 3168, 1789),
        (3485, 1777, 3957, 1789),
    }
    assert _MIN_LINE_LENGTH_PT == 4.0
    assert sorted((r.pixel_support_bounds[2] - r.pixel_support_bounds[0] + 1)
                  * 72.0 / DPI for r in segments) == pytest.approx(
        [44.40, 113.52]
    )
    # The old measured, long-source 300DPI line endpoints are unchanged:
    # edge expansion is exclusively for the 17-cell, 3.84pt-centre case.
    for segment in segments:
        x0, _, x1, _ = segment.pixel_support_bounds
        assert segment.pixel_geometry[0] == x0
        assert segment.pixel_geometry[2] == x1


def _altered_png(original_png, y, x, rgb):
    matrix = cv2.imdecode(np.frombuffer(original_png, np.uint8), cv2.IMREAD_COLOR)
    assert matrix is not None
    matrix[y, x] = rgb
    ok, encoded = cv2.imencode(".png", matrix)
    assert ok
    return encoded.tobytes()


def test_changed_full_rgb_cannot_borrow_left_2127_flank(original_page3_images):
    ink, full = original_page3_images
    # Alter an ORIGINAL left-band central pixel on the full render only:
    # independently original-image supported LEFT must fail, RIGHT retained.
    changed = _altered_png(full, 1783, 3050, (255, 255, 255))
    observed = _segments(ink, changed)
    assert len(observed) == 1
    assert observed[0].pixel_support_bounds == (3485, 1777, 3957, 1789)


def test_unpainted_original_left_band_core_never_becomes_wall(original_page3_images):
    ink, full = original_page3_images
    changed_ink = _altered_png(ink, 1783, 3050, (255, 255, 255))
    observed = _segments(changed_ink, full)
    assert len(observed) == 1
    assert observed[0].pixel_support_bounds == (3485, 1777, 3957, 1789)


def test_overpaint_of_right_source_only_must_not_borrow_adjacent_left(original_page3_images):
    ink, full = original_page3_images
    changed = _altered_png(full, 1783, 3640, (255, 255, 255))
    observed = _segments(ink, changed)
    assert len(observed) == 1
    assert observed[0].pixel_support_bounds == (2984, 1777, 3168, 1789)
