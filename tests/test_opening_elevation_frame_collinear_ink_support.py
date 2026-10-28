"""A fill-only frame edge is drawn where source-painted strokes already ink its whole extent.

#3997 refuses a frame whose supports are not source-painted strokes, and identifies a support by the id of the
extracted edge. A frame drawn as a white fill plus a coincident stroked outline therefore had its fill edges
rejected although the outline inks exactly those coordinates. A support edge is accepted when source-painted strokes
(opaque, solid, visible, never erased by later paint) of the same axis-aligned line already cover its whole extent,
by exact coordinate identity. A shorter, parallel, gapped, dashed, translucent or later-erased stroke never supports it.
Synthetic drawings only.
"""
from __future__ import annotations

import fitz
import pytest

import pb_opening_elevation_frame_area_authority as module
from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_opening_elevation_frame_area_authority import _source_painted_geometry_ids
from test_opening_elevation_frame_painted_support import _payload, _resolve

FRAME = (150.0, 120.0, 300.0, 240.0)


def _with_outline(*, rotation=0, base="white-fill", draw=None):
    """The painted-support fixture with extra strokes drawn on the unrotated page, then rotated."""
    doc = fitz.open(stream=_payload(base), filetype="pdf")
    page = doc[0]
    (draw or _full_outline)(page)
    page.set_rotation(rotation)
    payload = doc.tobytes()
    doc.close()
    return payload


def _full_outline(page, *, dx=0.0, dy=0.0, **kw):
    x0, y0, x1, y1 = FRAME
    page.draw_rect(fitz.Rect(x0 + dx, y0 + dy, x1 + dx, y1 + dy), color=(0, 0, 0), width=1.0, **kw)


def _segments(page, segments, **kw):
    for a, b in segments:
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1.0, **kw)


def _outline_edges(drop=None, split=None, gap=0.0):
    x0, y0, x1, y1 = FRAME
    edges = {"top": ((x0, y0), (x1, y0)), "right": ((x1, y0), (x1, y1)), "bottom": ((x1, y1), (x0, y1)),
             "left": ((x0, y1), (x0, y0))}
    out = []
    for name, (a, b) in edges.items():
        if name == drop:
            continue
        if split == name:
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            h = gap / 2.0
            ux = (b[0] - a[0]) / max(abs(b[0] - a[0]) + abs(b[1] - a[1]), 1e-9)
            uy = (b[1] - a[1]) / max(abs(b[0] - a[0]) + abs(b[1] - a[1]), 1e-9)
            out += [(a, (mid[0] - h * ux, mid[1] - h * uy)), ((mid[0] + h * ux, mid[1] + h * uy), b)]
        else:
            out.append((a, b))
    return out


def _ok(result):
    return result.status is S.CORROBORATED and abs(result.record.area_m2 - 7.2) < 1e-9


# ------------------------------------------------------------------------------------------------ positives

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_a_white_fill_frame_with_a_coincident_painted_outline_is_supported(rotation):
    _, _, result = _resolve(_with_outline(rotation=rotation))
    assert _ok(result), result.reason_codes


def test_the_same_fill_without_any_outline_stays_unproved():
    _, _, result = _resolve(_payload("white-fill"))
    assert result.status is S.ABSTAINED and result.record is None


def test_an_outline_split_into_touching_collinear_pieces_still_supports_the_edge():
    _, _, result = _resolve(_with_outline(draw=lambda page: _segments(page, _outline_edges(split="top", gap=0.0))))
    assert _ok(result), result.reason_codes


@pytest.mark.parametrize("offset,scale", [((40, 20), 1.0), ((0, 0), 1.2), ((30, 30), 0.75)])
def test_translation_and_uniform_scale_preserve_the_supported_frame(offset, scale):
    with fitz.open(stream=_with_outline(), filetype="pdf") as original:
        doc = fitz.open()
        page = doc.new_page(width=700, height=600)
        dx, dy = offset
        page.show_pdf_page(fitz.Rect(dx, dy, dx + 500 * scale, dy + 400 * scale), original, 0)
        payload = doc.tobytes()
        doc.close()
    _, _, result = _resolve(payload)
    assert _ok(result), result.reason_codes


# ------------------------------------------------------------------------------------------------ negatives

def test_a_parallel_but_not_coincident_outline_does_not_support_the_fill_edges():
    _, _, result = _resolve(_with_outline(draw=lambda page: _full_outline(page, dx=0.5)))
    assert result.status is S.ABSTAINED and result.record is None


def test_an_outline_missing_one_edge_leaves_that_edge_unsupported():
    for drop in ("top", "right", "bottom", "left"):
        _, _, result = _resolve(_with_outline(draw=lambda page, d=drop: _segments(page, _outline_edges(drop=d))))
        assert result.status is S.ABSTAINED and result.record is None, drop


def test_an_outline_with_a_gap_does_not_support_the_edge_it_interrupts():
    _, _, result = _resolve(_with_outline(draw=lambda page: _segments(page, _outline_edges(split="top", gap=2.0))))
    assert result.status is S.ABSTAINED and result.record is None


def test_a_dashed_outline_does_not_support_the_fill_edges():
    _, _, result = _resolve(_with_outline(draw=lambda page: _full_outline(page, dashes="[4 4] 0")))
    assert result.status is S.ABSTAINED and result.record is None


def test_a_translucent_outline_does_not_support_the_fill_edges():
    def draw(page):
        _full_outline(page, stroke_opacity=0.5)
    _, _, result = _resolve(_with_outline(draw=draw))
    assert result.status is S.ABSTAINED and result.record is None


def test_an_outline_that_a_later_white_mask_erases_does_not_support_the_fill_edges():
    def draw(page):
        _full_outline(page)
        page.draw_rect(fitz.Rect(149.0, 119.0, 151.0, 241.0), color=None, fill=(1, 1, 1))
    _, _, result = _resolve(_with_outline(draw=draw))
    assert result.status is S.ABSTAINED and result.record is None


def test_a_white_outline_does_not_support_the_fill_edges():
    def draw(page):
        page.draw_rect(fitz.Rect(*FRAME), color=(1, 1, 1), width=1.0)
    _, _, result = _resolve(_with_outline(draw=draw))
    assert result.status is S.ABSTAINED and result.record is None


# ------------------------------------------------------------------------------------------------ helpers, ids

def _page_of(payload):
    doc = fitz.open(stream=payload, filetype="pdf")
    return doc, doc[0]


def test_only_edges_inked_in_full_by_painted_strokes_gain_support():
    doc, page = _page_of(_with_outline())
    with_outline = _source_painted_geometry_ids(page, "1")
    doc.close()
    doc, page = _page_of(_payload("white-fill"))
    without = _source_painted_geometry_ids(page, "1")
    fill_ids = {i for i in with_outline if i.startswith("vec_p1_0_")}
    doc.close()
    assert not any(i.startswith("vec_p1_0_0_e") for i in without)
    assert fill_ids and fill_ids <= with_outline and len(with_outline) > len(without)


def test_replay_is_identical_and_the_page_is_not_mutated():
    doc, page = _page_of(_with_outline())
    first = _source_painted_geometry_ids(page, "1")
    again = _source_painted_geometry_ids(page, "1")
    doc.close()
    assert first == again


@pytest.mark.parametrize("segment,expected", [
    ({"x1": 0.0, "y1": 5.0, "x2": 10.0, "y2": 5.0}, ("h", 5.0, 0.0, 10.0)),
    ({"x1": 10.0, "y1": 5.0, "x2": 0.0, "y2": 5.0}, ("h", 5.0, 0.0, 10.0)),
    ({"x1": 3.0, "y1": 9.0, "x2": 3.0, "y2": 1.0}, ("v", 3.0, 1.0, 9.0)),
    ({"x1": 0.0, "y1": 0.0, "x2": 5.0, "y2": 5.0}, None),
    ({"x1": 1.0, "y1": 1.0, "x2": 1.0, "y2": 1.0}, None),
    ({"x1": float("nan"), "y1": 0.0, "x2": 1.0, "y2": 0.0}, None),
    ({"x1": 0.0, "y1": 0.0, "x2": float("inf"), "y2": 0.0}, None),
    ({"x1": "a", "y1": 0.0, "x2": 1.0, "y2": 0.0}, None),
    ({"y1": 0.0, "x2": 1.0, "y2": 0.0}, None),
])
def test_axis_span_reads_only_finite_axis_aligned_non_degenerate_edges(segment, expected):
    assert module._axis_span(segment) == expected


def test_merge_spans_joins_only_overlapping_or_touching_intervals():
    assert module._merge_spans([(5.0, 8.0), (0.0, 5.0), (7.0, 9.0)]) == [(0.0, 9.0)]
    assert module._merge_spans([(0.0, 4.0), (4.5, 9.0)]) == [(0.0, 4.0), (4.5, 9.0)]
    assert module._merge_spans([]) == []


def test_the_identity_tolerance_is_float_identity_not_a_measurement():
    assert module._COLLINEAR_IDENTITY_TOL <= 1e-6


# Direct source-coordinate tests retain sub-micro-point offsets that PyMuPDF
# may quantise when serialising synthetic PDF drawing commands.
def _indexed_ink(*strokes):
    indexed = {}
    for axis, offset, lo, hi, *endpoints in strokes:
        indexed.setdefault(
            (axis, round(offset / module._COLLINEAR_IDENTITY_TOL)), []
        ).append((offset, lo, hi, *endpoints))
    return indexed


def test_neighbour_bucket_at_1_49_micro_points_is_not_same_painted_line():
    painted = _indexed_ink(("h", 1.49e-6, 0.0, 10.0))
    assert not module._collinear_painted_coverage(("h", 0.0, 0.0, 10.0), painted)


def test_exact_tolerance_near_half_bucket_boundary_is_not_falsely_rejected():
    # Python round() uses ties-to-even: the candidate and truly coincident stroke
    # can occupy buckets TWO indices apart, even though their actual distance is <= 1e-6.
    candidate, painted = 100.0000005, 100.0000015
    assert abs(painted - candidate) <= module._COLLINEAR_IDENTITY_TOL
    assert abs(round(painted / module._COLLINEAR_IDENTITY_TOL)
               - round(candidate / module._COLLINEAR_IDENTITY_TOL)) == 2
    assert module._collinear_painted_coverage(
        ("h", candidate, 0.0, 10.0), _indexed_ink(("h", painted, 0.0, 10.0))
    )


def test_sub_micro_point_translation_does_not_change_actual_collinear_coverage():
    for translation in (0.0, 1e-7, 10.0, -10.0):
        candidate = 100.0000005 + translation
        painted = 100.0000015 + translation
        assert abs(painted - candidate) <= module._COLLINEAR_IDENTITY_TOL
        assert module._collinear_painted_coverage(
            ("v", candidate, 0.0, 10.0), _indexed_ink(("v", painted, 0.0, 10.0))
        )


def test_two_bucket_retrieval_never_weakens_actual_offset_veto():
    candidate = 100.0000005
    out_of_tolerance = 100.00000151
    assert abs(out_of_tolerance - candidate) > module._COLLINEAR_IDENTITY_TOL
    assert not module._collinear_painted_coverage(
        ("h", candidate, 0.0, 10.0),
        _indexed_ink(("h", out_of_tolerance, 0.0, 10.0))
    )
    # A foreign second half cannot complete a genuinely painted first half.
    assert not module._collinear_painted_coverage(
        ("h", candidate, 0.0, 10.0),
        _indexed_ink(
            ("h", 100.0000015, 0.0, 5.0),
            ("h", out_of_tolerance, 5.0, 10.0),
        )
    )


def test_only_actual_coincident_strokes_may_complete_a_split_edge():
    mixed = _indexed_ink(
        ("h", 0.2e-6, 0.0, 5.0),
        ("h", 1.49e-6, 5.0, 10.0),
    )
    assert not module._collinear_painted_coverage(("h", 0.0, 0.0, 10.0), mixed)
    matching = _indexed_ink(
        ("h", 0.2e-6, 0.0, 5.0),
        ("h", -0.3e-6, 5.0, 10.0),
    )
    assert module._collinear_painted_coverage(("h", 0.0, 0.0, 10.0), matching)


def test_collinear_coverage_is_order_independent_and_axis_scoped():
    strokes = (
        ("h", 0.2e-6, 0.0, 5.0),
        ("h", -0.3e-6, 5.0, 10.0),
        ("h", 1.49e-6, 0.0, 10.0),
        ("v", 0.0, 0.0, 10.0),
    )
    expected = module._collinear_painted_coverage(
        ("h", 0.0, 0.0, 10.0), _indexed_ink(*strokes)
    )
    assert expected is True
    assert module._collinear_painted_coverage(
        ("h", 0.0, 0.0, 10.0), _indexed_ink(*reversed(strokes))
    ) is expected
    assert not module._collinear_painted_coverage(
        ("v", 3.0, 0.0, 10.0), _indexed_ink(*strokes)
    )


# The midpoint alone is not coordinate identity for a near-axis line. Two
# opposite sub-micro-point slopes can agree at the midpoint but be separated
# by more than the identity tolerance at one end of their shared extent.
def test_crossed_near_horizontal_strokes_cannot_paint_an_unmatched_endpoint():
    edge = ("h", 0.0, 0.0, 10.0)
    edge_ends = (-0.49e-6, 0.49e-6)
    foreign = _indexed_ink(("h", 0.21e-6, 0.0, 10.0, 0.70e-6, -0.28e-6))
    assert abs(0.21e-6) < module._COLLINEAR_IDENTITY_TOL
    assert abs(edge_ends[0] - 0.70e-6) > module._COLLINEAR_IDENTITY_TOL
    assert not module._collinear_painted_coverage(edge, foreign, edge_endpoints=edge_ends)
    authentic = _indexed_ink(("h", 0.0, 0.0, 10.0, *edge_ends))
    assert module._collinear_painted_coverage(edge, authentic, edge_endpoints=edge_ends)


def test_crossed_near_vertical_strokes_are_equally_vetoed():
    edge = ("v", 0.0, 0.0, 10.0)
    edge_ends = (-0.49e-6, 0.49e-6)
    foreign = _indexed_ink(("v", 0.21e-6, 0.0, 10.0, 0.70e-6, -0.28e-6))
    assert not module._collinear_painted_coverage(edge, foreign, edge_endpoints=edge_ends)
    assert module._collinear_painted_coverage(
        edge, _indexed_ink(("v", 0.0, 0.0, 10.0, *edge_ends)), edge_endpoints=edge_ends
    )


def test_genuinely_coincident_near_axis_split_ink_remains_order_invariant():
    edge = ("h", 0.0, 0.0, 10.0)
    ends = (-0.49e-6, 0.49e-6)
    strokes = (
        ("h", -0.245e-6, 0.0, 5.0, -0.49e-6, 0.0),
        ("h", 0.245e-6, 5.0, 10.0, 0.0, 0.49e-6),
    )
    assert module._collinear_painted_coverage(edge, _indexed_ink(*strokes), edge_endpoints=ends)
    assert module._collinear_painted_coverage(edge, _indexed_ink(*reversed(strokes)), edge_endpoints=ends)
    wrong_second = ("h", 0.71e-6, 5.0, 10.0, 1.20e-6, 0.22e-6)
    assert not module._collinear_painted_coverage(
        edge, _indexed_ink(strokes[0], wrong_second), edge_endpoints=ends
    )


def test_transverse_endpoint_order_follows_axis_span_direction():
    horizontal = {"x1": 10.0, "y1": 0.49e-6, "x2": 0.0, "y2": -0.49e-6}
    vertical = {"x1": 0.49e-6, "y1": 10.0, "x2": -0.49e-6, "y2": 0.0}
    assert module._transverse_endpoints(horizontal, "h") == (-0.49e-6, 0.49e-6)
    assert module._transverse_endpoints(vertical, "v") == (-0.49e-6, 0.49e-6)
