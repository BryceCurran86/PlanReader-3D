"""Numeric bounds of the collinear painted-ink support: enormous or unresolvable source numbers never raise.

A source number that is too large to be a float, non-finite, or so large that a float cannot resolve the 1e-6
coordinate-identity tolerance at that magnitude cannot be proven identical to any other coordinate. The edge is then
UNSUPPORTED (a typed abstention for the frame), never an OverflowError, never a silently coarse bucket, and never a
widened tolerance. Synthetic segments only.
"""
from __future__ import annotations

import math

import fitz
import pytest

import pb_opening_elevation_frame_area_authority as module
from pb_opening_elevation_frame_area_authority import (
    _axis_span, _collinear_painted_coverage, _offset_bucket, _source_painted_geometry_ids, _transverse_endpoints,
)

LIMIT = module._RESOLVABLE_COORDINATE
HUGE_INT = 10 ** 1000


def _seg(x1, y1, x2, y2, **kw):
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, **kw}


UNRESOLVABLE = [
    HUGE_INT, -HUGE_INT, 10 ** 400, 1e308, -1e308, 1.7976931348623157e308, LIMIT, -LIMIT, LIMIT * 2.0,
    float("inf"), float("-inf"), float("nan"), True, None, "7", [1.0],
]


@pytest.mark.parametrize("bad", UNRESOLVABLE)
@pytest.mark.parametrize("slot", ["x1", "y1", "x2", "y2"])
def test_one_unresolvable_coordinate_makes_the_edge_unsupported_without_raising(bad, slot):
    segment = _seg(0.0, 5.0, 10.0, 5.0)
    segment[slot] = bad
    assert _axis_span(segment) is None
    for axis in ("h", "v"):
        assert _transverse_endpoints(segment, axis) is None


@pytest.mark.parametrize("magnitude", [1.0, 1e3, 1e6, 1e9, 4e9])
def test_every_resolvable_magnitude_still_yields_a_span_and_endpoints(magnitude):
    assert _axis_span(_seg(0.0, magnitude, 10.0, magnitude)) == ("h", magnitude, 0.0, 10.0)
    assert _axis_span(_seg(magnitude, 3.0, magnitude, -2.0)) == ("v", magnitude, -2.0, 3.0)
    assert _transverse_endpoints(_seg(0.0, magnitude, 10.0, magnitude), "h") == (magnitude, magnitude)
    assert _transverse_endpoints(_seg(magnitude, 3.0, magnitude, -2.0), "v") == (magnitude, magnitude)


def test_the_midpoint_of_two_large_coordinates_cannot_overflow():
    # (y0 + y1) / 2 would be inf for two finite 1.7e308 values; both are refused before any arithmetic
    assert _axis_span(_seg(0.0, 1.7e308, 10.0, 1.7e308)) is None
    assert _axis_span(_seg(-1.7e308, 5.0, 1.7e308, 5.0)) is None


@pytest.mark.parametrize("offset", [1e308, -1e308, HUGE_INT, float("inf"), float("nan"), LIMIT, None, True, "1.0"])
def test_an_offset_that_cannot_resolve_the_tolerance_has_no_bucket(offset):
    assert _offset_bucket(offset) is None


@pytest.mark.parametrize("offset", [0.0, -3.5, 120.25, 1e6])
def test_a_resolvable_offset_keeps_the_bucket_it_always_had(offset):
    assert _offset_bucket(offset) == round(offset / 1e-6)


@pytest.mark.parametrize("span", [
    ("h", 1e308, 0.0, 10.0), ("h", 5.0, -1e308, 10.0), ("h", 5.0, 0.0, 1e308), ("v", HUGE_INT, 0.0, 10.0),
    ("h", float("nan"), 0.0, 10.0), ("h", 5.0, float("-inf"), 10.0),
])
def test_coverage_of_an_unresolvable_candidate_span_is_false_and_never_raises(span):
    inked = {("h", 5000000): [(5.0, 0.0, 100.0, 5.0, 5.0)], ("v", 5000000): [(5.0, 0.0, 100.0, 5.0, 5.0)]}
    assert _collinear_painted_coverage(span, inked) is False
    assert _collinear_painted_coverage(span, inked, edge_endpoints=(5.0, 5.0)) is False


@pytest.mark.parametrize("ends", [(1e308, 1e308), (HUGE_INT, 5.0), (5.0, float("nan")), (float("inf"), 5.0)])
def test_coverage_with_unresolvable_candidate_endpoints_is_false_and_never_raises(ends):
    inked = {("h", 5000000): [(5.0, 0.0, 100.0, 5.0, 5.0)]}
    assert _collinear_painted_coverage(("h", 5.0, 10.0, 20.0), inked, edge_endpoints=ends) is False


def test_a_resolvable_coincident_stroke_still_covers_an_edge():
    inked = {("h", 5000000): [(5.0, 0.0, 100.0, 5.0, 5.0)]}
    assert _collinear_painted_coverage(("h", 5.0, 10.0, 20.0), inked, edge_endpoints=(5.0, 5.0)) is True
    assert _collinear_painted_coverage(("h", 5.0, 10.0, 200.0), inked, edge_endpoints=(5.0, 5.0)) is False


class _FakePage:
    """Just enough page for the painted-support gate: a native extraction and no paint log."""

    def __init__(self, drawings, bboxlog):
        self._drawings, self._bboxlog = drawings, bboxlog

    def get_drawings(self):
        return self._drawings

    def get_bboxlog(self):
        return self._bboxlog

    def get_texttrace(self):
        return []


def test_hostile_native_segments_never_raise_through_the_painted_gate(monkeypatch):
    drawing = {"type": "s", "seqno": 0, "stroke_opacity": 1.0, "color": (0.0, 0.0, 0.0)}
    base = {"path_index": 0, "item_index": 0, "width": 1.0, "stroke_present": True, "dashes": "[] 0",
            "sequence_number": 0}
    hostile = [
        dict(base, item_index=0, **_seg(0.0, 1e308, 10.0, 1e308)),
        dict(base, item_index=1, **_seg(0.0, HUGE_INT, 10.0, HUGE_INT)),
        dict(base, item_index=2, **_seg(-1e308, 5.0, 1e308, 5.0)),
        dict(base, item_index=3, **_seg(float("nan"), 5.0, 10.0, 5.0)),
        dict(base, item_index=4, **_seg(0.0, 5.0, 10.0, 5.0)),
    ]
    monkeypatch.setattr(module, "extract_native_page", lambda page: {"segments": hostile})
    page = _FakePage([drawing], [("stroke-path", (-1e9, -1e9, 1e9, 1e9))])
    ids = _source_painted_geometry_ids(page, "1")
    assert isinstance(ids, frozenset)
    # a hostile coordinate never produces a support id; every id that exists belongs to a resolvable edge
    assert not any(i.endswith(("_0_1", "_0_2", "_0_3")) or i == "vec_p1_0_0" for i in ids)


def test_the_resolvable_bound_is_about_float_resolution_not_a_page_size():
    assert math.isclose(LIMIT, 2.0 ** 52 * 1e-6)
    assert LIMIT > 1e9            # far beyond any page, so no real drawing is newly refused
    assert fitz.Rect(0, 0, 10, 10).width == 10
