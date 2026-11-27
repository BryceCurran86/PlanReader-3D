"""Which paint made each raster segment (#4764 7227402524, Lot16 raster walls). Synthetic only."""
from __future__ import annotations

import fitz
import numpy as np
import pytest

from pb_raster_segment_paint_lineage_shadow import (
    IMAGE_AND_VECTOR, IMAGE_INK, UNATTRIBUTED, VECTOR_INK, classify_raster_segment_paint,
)
from pb_raster_visible_segment_detector import detect_axis_aligned_raster_segments
from pb_source_visibility_authority import SourceVisibilityProducer

DPI = 144


def _page(shift=0.0, *, text=False):
    """A picture holding one black line at y=100; a native line over its blank part at y=140 and one along its line."""
    pixels = np.full((400, 400), 255, dtype=np.uint8)
    pixels[198:202, 40:360] = 0  # the picture's own line, at page y = 100 for a 200 pt square placed at (0, 0)
    picture = fitz.Pixmap(fitz.csGRAY, 400, 400, pixels.tobytes(), False)
    document = fitz.open()
    page = document.new_page(width=300, height=300)
    page.insert_image(fitz.Rect(shift, 0, 200 + shift, 200), pixmap=picture)
    page.draw_line((20 + shift, 140), (180 + shift, 140), color=(0, 0, 0), width=1.0)
    page.draw_line((20 + shift, 170), (180 + shift, 170), color=(0, 0, 0), width=1.0)
    page.draw_line((60 + shift, 100), (140 + shift, 100), color=(0, 0, 0), width=1.0)  # drawn again on the picture
    if text:
        page.insert_text((40 + shift, 60), "IIIIIIIIIIIIIIIIIIIIII", fontsize=18)
    natives = [(f"d{i}", d["rect"].x0, d["rect"].y0, d["rect"].x1, d["rect"].y1, float(d["width"]))
               for i, d in enumerate(page.get_drawings())]
    data = document.tobytes()
    document.close()
    return data, natives


def _renders(data):
    source = SourceVisibilityProducer(producer_method="paint-lineage-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="paint", source_bytes=data, source_locator="memory://p.pdf")
    observer = source._producer
    args = dict(document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id, page_id="1",
                dpi=float(DPI))
    full = observer.render_native_page_png(**args)[0]
    images_only = observer.render_native_page_png(**args, images_only=True)[0]
    return full, images_only


def _classify(shift=0.0, *, order=1):
    data, natives = _page(shift)
    full, images_only = _renders(data)
    segments = [(f"s{i}", s.orientation, s.geometry_pt)
                for i, s in enumerate(detect_axis_aligned_raster_segments(full, dpi=DPI))]
    rows = classify_raster_segment_paint(segments[::order], images_only, natives[::order], dpi=DPI)
    by_level = {}
    for row in rows:
        _sid, _o, geometry = next(s for s in segments if s[0] == row["segment_id"])
        by_level.setdefault(round(geometry[1] / 10) * 10, []).append(row)
    return by_level, natives


@pytest.mark.parametrize("shift", [0.0, 37.5])
def test_image_ink_vector_ink_and_both_are_told_apart(shift):
    by_level, natives = _classify(shift)
    (vector,) = by_level[140]
    assert vector["kind"] == VECTOR_INK and vector["native_ids"] == ["d0"] and vector["image_share"] <= 0.1
    assert by_level[170][0]["native_ids"] == ["d1"]
    (picture,) = by_level[100]  # one line in the picture, partly drawn again by a native line
    assert picture["kind"] == IMAGE_INK and picture["native_ids"] == [] and 0.3 < picture["native_cover"] < 0.7


def test_a_picture_line_without_native_ink_is_image_ink_only():
    data, _natives = _page()
    full, images_only = _renders(data)
    segments = [(f"s{i}", s.orientation, s.geometry_pt)
                for i, s in enumerate(detect_axis_aligned_raster_segments(full, dpi=DPI)) if round(s.geometry_pt[1] / 10) == 10]
    rows = classify_raster_segment_paint(segments, images_only, [], dpi=DPI)
    assert rows and {row["kind"] for row in rows} == {IMAGE_INK}


def test_text_strokes_are_unattributed_not_assigned_to_a_line():
    data, natives = _page(text=True)
    full, images_only = _renders(data)
    segments = [(f"s{i}", s.orientation, s.geometry_pt)
                for i, s in enumerate(detect_axis_aligned_raster_segments(full, dpi=DPI)) if s.geometry_pt[1] < 80]
    assert segments
    assert {row["kind"] for row in classify_raster_segment_paint(segments, images_only, natives, dpi=DPI)} == {UNATTRIBUTED}


def test_lines_nearby_are_not_cover_and_partial_cover_is_unattributed():
    data, natives = _page()
    _full, images_only = _renders(data)
    vector_segment = [("s", "horizontal", (20.0, 140.0, 180.0, 140.0))]
    nearby = [("n", 20.0, 142.5, 180.0, 142.5, 1.0)]
    partial = [("p", 20.0, 140.0, 100.0, 140.0, 1.0)]
    for lines in (nearby, partial):
        (row,) = classify_raster_segment_paint(vector_segment, images_only, lines, dpi=DPI)
        assert row["kind"] == UNATTRIBUTED and row["native_ids"] == []
    halves = [("a", 20.0, 140.0, 100.0, 140.0, 1.0), ("b", 100.0, 140.0, 180.0, 140.0, 1.0)]
    (row,) = classify_raster_segment_paint(vector_segment, images_only, halves, dpi=DPI)
    assert row["kind"] == VECTOR_INK and row["native_ids"] == ["a", "b"]  # both kept


def test_ink_in_both_the_picture_and_a_line_says_so():
    data, natives = _page()
    _full, images_only = _renders(data)
    (row,) = classify_raster_segment_paint([("s", "horizontal", (60.0, 100.0, 140.0, 100.0))], images_only, natives, dpi=DPI)
    assert row["kind"] == IMAGE_AND_VECTOR and row["native_ids"] == ["d2"]


def test_a_line_crossing_the_other_way_is_not_cover():
    data, _natives = _page()
    _full, images_only = _renders(data)
    upright = [("u", 100.0, 100.0, 100.0, 180.0, 1.0)]
    (row,) = classify_raster_segment_paint([("s", "horizontal", (20.0, 140.0, 180.0, 140.0))], images_only, upright, dpi=DPI)
    assert row["kind"] == UNATTRIBUTED and row["native_cover"] == 0.0


@pytest.mark.parametrize("segment,lines", [
    # five points below the picture's line: its ink is not this segment's ink
    ((20.0, 105.0, 180.0, 105.0), [("n", 20.0, 105.0, 180.0, 105.0, 1.0)]),
], ids=["near-picture-line"])
def test_picture_ink_a_few_points_away_is_not_the_segments(segment, lines):
    data, _natives = _page()
    _full, images_only = _renders(data)
    (row,) = classify_raster_segment_paint([("s", "horizontal", segment)], images_only, lines, dpi=DPI)
    assert row["kind"] == VECTOR_INK and row["image_share"] <= 0.1


@pytest.mark.parametrize("segment,lines", [
    ((20.0, 140.0, 180.0, 140.0), [("slant", 20.0, 130.0, 180.0, 150.0, 1.0)]),
    ((20.0, 140.0, 180.0, 140.0), [("a", 20.0, 140.0, 100.0, 140.0, 1.0), ("b", 20.0, 140.0, 100.0, 140.0, 1.0)]),
    ((150.0, 100.0, 210.0, 100.0), [("half", 150.0, 100.0, 210.0, 100.0, 1.0)]),  # half the pixels are in the picture
], ids=["slanted-line", "the-same-half-twice", "half-picture"])
def test_unproven_cases_stay_unattributed(segment, lines):
    data, _natives = _page()
    _full, images_only = _renders(data)
    (row,) = classify_raster_segment_paint([("s", "horizontal", segment)], images_only, lines, dpi=DPI)
    assert row["kind"] == UNATTRIBUTED and row["native_ids"] == []


def test_order_and_repeat_do_not_change_the_answer():
    first, _ = _classify()
    assert first == _classify(order=-1)[0] == _classify()[0]
