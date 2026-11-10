"""The PyMuPDF diagnostic path and the source-owned path read the SAME drawn rectangles (review of #4264).

The original-source parity test (`owned == diagnostic`) only means something when both paths share one definition of "a drawn
rectangle". The diagnostic path used to take ``drawing["rect"]`` (the bounding box of a whole filled path), which invents a rectangle
across the gap of a compound path; the source-owned path was repaired to ``rectangle_components``. These synthetic pages pin the two
paths together without any private PDF.
"""
from __future__ import annotations

import hashlib

import fitz
import pytest

import pb_elevation_source_owned_witness_adapter as adapter
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_elevation_door_vertical_witness_shadow import page_primitives

FILL = (0.25, 0.25, 0.25)


def _pdf(build) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=500, height=400)
    build(page)
    return doc.tobytes()


def _shape_path(page, polygons, *, fill=FILL):
    shape = page.new_shape()
    for pts in polygons:
        shape.draw_polyline(list(pts) + [pts[0]])
    shape.finish(fill=fill, color=None, closePath=True)
    shape.commit()


def _box(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _diagnostic_rects(payload: bytes):
    doc = fitz.open(stream=payload, filetype="pdf")
    return sorted(tuple(round(v, 2) for v in r[:4]) for r in page_primitives(doc[0])[1])


def _owned_rects(payload: bytes):
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall", producer_version="1")
    sha = hashlib.sha256(payload).hexdigest()
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://parity.pdf", page_ids=(1,))
    page = adapter.read_source_owned_page(source, revision_id=initial.revision.revision_id, page_id="1")
    return sorted(tuple(round(v, 2) for v in r[:4]) for r in page.rects)


CASES = {
    "one_rectangle": lambda p: _shape_path(p, [_box(200, 200, 220, 250)]),
    "compound_two_rectangles": lambda p: _shape_path(p, [_box(200, 200, 220, 250), _box(250, 200, 270, 250)]),
    "compound_three_rectangles": lambda p: _shape_path(p, [_box(100, 100, 120, 150), _box(200, 100, 220, 150), _box(300, 100, 320, 150)]),
    "l_shape": lambda p: _shape_path(p, [[(200, 200), (240, 200), (240, 220), (220, 220), (220, 250), (200, 250)]]),
    "l_shape_beside_rectangle": lambda p: _shape_path(
        p, [[(200, 200), (240, 200), (240, 220), (220, 220), (220, 250), (200, 250)], _box(300, 200, 320, 250)]),
    "separate_paths": lambda p: (_shape_path(p, [_box(200, 200, 220, 250)]), _shape_path(p, [_box(250, 200, 270, 250)])),
    "native_rect_operator": lambda p: p.draw_rect(fitz.Rect(200, 200, 220, 250), color=None, fill=FILL),
    "two_native_rect_operators_in_one_path": lambda p: _two_re_in_one_path(p),
    "stroke_only_rectangle": lambda p: p.draw_rect(fitz.Rect(200, 200, 220, 250), color=(0, 0, 0), fill=None),
    "thin_strip_below_the_edge_floor": lambda p: _shape_path(p, [_box(100, 277.29, 134, 277.57)]),
    "thin_vertical_strip_below_the_edge_floor": lambda p: _shape_path(p, [_box(648.7, 247.8, 649.13, 277.6)]),
    "compound_of_two_thin_strips_and_a_rectangle": lambda p: _shape_path(
        p, [_box(100, 200, 134, 200.3), _box(100, 277, 134, 277.3), _box(300, 200, 320, 250)]),
    "implicitly_closed_strip_chain": lambda p: _open_chain(p, [(100, 200), (134, 200), (134, 200.3), (100, 200.3)]),
    "two_open_strokes_same_fill": lambda p: _open_lines(p, [((100, 200), (134, 200)), ((100, 200.3), (134, 200.3))]),
    "two_open_strokes_opposite_way": lambda p: _open_lines(p, [((100, 200), (134, 200)), ((134, 200.3), (100, 200.3))]),
    "strip_just_over_the_edge_floor": lambda p: _shape_path(p, [_box(100, 277.0, 134, 277.6)]),
    "two_fills_in_separate_paths": lambda p: (_shape_path(p, [_box(200, 200, 220, 250)], fill=(0.1, 0.1, 0.1)),
                                              _shape_path(p, [_box(200, 200, 220, 250)], fill=(0.9, 0.9, 0.9))),
}


def _open_lines(page, lines):
    shape = page.new_shape()
    for start, end in lines:
        shape.draw_line(start, end)
    shape.finish(fill=FILL, color=None, closePath=False)
    shape.commit()


def _open_chain(page, points):
    shape = page.new_shape()
    shape.draw_polyline(points)
    shape.finish(fill=FILL, color=None, closePath=False)               # the fill closes it; no closing side is drawn
    shape.commit()


def _two_re_in_one_path(page):
    shape = page.new_shape()
    shape.draw_rect(fitz.Rect(200, 200, 220, 250))
    shape.draw_rect(fitz.Rect(250, 200, 270, 250))
    shape.finish(fill=FILL, color=None)
    shape.commit()


# The source-owned adapter reads native `line` facts only: a filled `re` operator reaches it as `rect_edge` facts it ignores. That is a
# separate coverage gap (none of the 3Laurel elevation pages uses `re` fills); strict xfail so closing it flips these cases to passing.
NATIVE_RE_GAP = {"native_rect_operator", "two_native_rect_operators_in_one_path"}


@pytest.mark.parametrize("name", [pytest.param(n, marks=pytest.mark.xfail(strict=True, reason="source-owned adapter ignores native re (rect_edge) fills"))
                                  if n in NATIVE_RE_GAP else n for n in sorted(CASES)])
def test_both_paths_read_the_same_drawn_rectangles(name):
    payload = _pdf(CASES[name])
    assert _diagnostic_rects(payload) == _owned_rects(payload)


def test_the_diagnostic_path_never_spans_the_gap_of_a_compound_path():
    payload = _pdf(CASES["compound_two_rectangles"])
    rects = _diagnostic_rects(payload)
    assert rects == [(200.0, 200.0, 220.0, 250.0), (250.0, 200.0, 270.0, 250.0)]
    assert not any(r[0] <= 200.01 and r[2] >= 269.99 for r in rects)         # the old bounding box (200..270)


def test_the_diagnostic_path_reads_no_rectangle_from_an_l_shape_or_a_stroke_only_box():
    assert _diagnostic_rects(_pdf(CASES["l_shape"])) == []
    assert _diagnostic_rects(_pdf(CASES["stroke_only_rectangle"])) == []
    assert _diagnostic_rects(_pdf(CASES["l_shape_beside_rectangle"])) == [(300.0, 200.0, 320.0, 250.0)]


def test_the_diagnostic_path_still_reports_no_receipts():
    doc = fitz.open(stream=_pdf(CASES["compound_two_rectangles"]), filetype="pdf")
    assert all(len(r) == 5 for r in page_primitives(doc[0])[1])                 # (x0, y0, x1, y1, fill): the PyMuPDF path claims no receipts


def test_the_two_re_operators_in_one_path_are_two_rectangles_not_their_box():
    rects = _diagnostic_rects(_pdf(CASES["two_native_rect_operators_in_one_path"]))
    assert rects == [(200.0, 200.0, 220.0, 250.0), (250.0, 200.0, 270.0, 250.0)]


class _StubPage:
    """A page with hand-made drawings, to test how the diagnostic path reads items without a PDF round trip."""

    def __init__(self, drawings):
        self._drawings = drawings

    def get_drawings(self):
        return self._drawings

    def get_text(self, _mode):
        return []


def _line(a, b):
    return ("l", fitz.Point(*a), fitz.Point(*b))


def test_the_diagnostic_path_carries_item_identity_into_strip_pairing():
    sides = [_line((100.0, 200.0), (134.0, 200.0)), ("c", fitz.Point(134.0, 200.0), fitz.Point(134.1, 200.1), fitz.Point(134.1, 200.2), fitz.Point(134.0, 200.3)),
             _line((134.0, 200.3), (100.0, 200.3))]                       # side, a curved end the edge reader skips, side: items 0 and 2
    rects = page_primitives(_StubPage([{"fill": FILL, "items": sides}]))[1]
    assert [tuple(round(v, 2) for v in r[:4]) for r in rects] == [(100.0, 200.0, 134.0, 200.3)]
    adjacent = [_line((100.0, 200.0), (134.0, 200.0)), _line((134.0, 200.3), (100.0, 200.3))]       # items 0 and 1: two open strokes
    assert page_primitives(_StubPage([{"fill": FILL, "items": adjacent}]))[1] == []


def test_the_diagnostic_path_drops_line_edges_below_the_producer_floor_as_the_producer_does():
    tiny_square = [_line((100.0, 200.0), (100.3, 200.0)), _line((100.3, 200.0), (100.3, 200.3)),
                   _line((100.3, 200.3), (100.0, 200.3)), _line((100.0, 200.3), (100.0, 200.0))]
    assert page_primitives(_StubPage([{"fill": FILL, "items": tiny_square}]))[1] == []          # every side is under the floor: nothing was drawn
    at_floor = [_line((100.0, 200.0), (100.5, 200.0)), _line((100.5, 200.0), (100.5, 100.5)),
                _line((100.5, 100.5), (100.0, 100.5)), _line((100.0, 100.5), (100.0, 200.0))]
    assert len(page_primitives(_StubPage([{"fill": FILL, "items": at_floor}]))[1]) == 1       # a side of exactly the floor is kept
