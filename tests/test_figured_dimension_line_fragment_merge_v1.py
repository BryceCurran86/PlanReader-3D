"""Synthetic tests for text-split dimension-line fragment merging (F.13 follow-up).

A dimension line is frequently exported as two collinear vector fragments
split by the observation's own figured-dimension text sitting directly on
top of the line (the line is drawn up to the text bbox on each side). Before
this fix, ``bind_observation_to_vector_geometry`` treated the two halves as
two competing, equally-plausible dimension lines and abstained with
``AMBIGUOUS`` instead of resolving ``WITNESS_BOUND``.

All geometry and values here are synthetic and arbitrary -- none reuse the
real Lamu 1500mm veranda-depth figure that originally surfaced this gap.
No benchmark ground truth is used or referenced.
"""
from __future__ import annotations

import fitz
import pytest

from pb_figured_dimension_evidence import (
    BindingStatus,
    CoordinateSpace,
    ObservedGeometrySegment,
    _merge_text_split_line_fragments,
    bind_observation_to_vector_geometry,
    calibrate_dimension_layout,
    extract_dimension_evidence_bundle,
    extract_native_dimension_observations,
    extract_vector_segments,
)


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _split_dimension_page(
    value_text: str,
    *,
    vertical: bool,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    scale: float = 1.0,
    half_len: float = 60.0,
    gap_pad: float = 3.0,
    reverse_draw_order: bool = False,
) -> fitz.Document:
    """One dimension chain member: line split into two fragments by its own text."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    fontsize = 10.0 * scale
    text_half_w = (len(value_text) * fontsize * 0.5) / 2.0 + gap_pad
    text_half_h = fontsize * 0.6 + gap_pad

    if not vertical:
        y = 250 + offset_y
        x0 = 100 + offset_x
        x1 = x0 + 2 * half_len * scale
        gap0 = (x0 + x1) / 2.0 - text_half_w
        gap1 = (x0 + x1) / 2.0 + text_half_w
        witness_h = 20.0 * scale
        lines = [
            ((x0, y), (gap0, y)),
            ((gap1, y), (x1, y)),
            ((x0, y - witness_h), (x0, y + witness_h)),
            ((x1, y - witness_h), (x1, y + witness_h)),
        ]
        text_xy = ((gap0 + gap1) / 2.0 - fontsize * 0.5, y - 3)
    else:
        x = 250 + offset_x
        y0 = 100 + offset_y
        y1 = y0 + 2 * half_len * scale
        gap0 = (y0 + y1) / 2.0 - text_half_h
        gap1 = (y0 + y1) / 2.0 + text_half_h
        witness_w = 20.0 * scale
        lines = [
            ((x, y0), (x, gap0)),
            ((x, gap1), (x, y1)),
            ((x - witness_w, y0), (x + witness_w, y0)),
            ((x - witness_w, y1), (x + witness_w, y1)),
        ]
        text_xy = (x + 3, (gap0 + gap1) / 2.0 + fontsize * 0.4)

    draw_order = lines[::-1] if reverse_draw_order else lines
    for p0, p1 in draw_order:
        page.draw_line(p0, p1)
    page.insert_text(text_xy, value_text, fontsize=fontsize)
    return _reopen(doc)


def _unrelated_far_collinear_page(
    value_text: str, *, vertical: bool
) -> fitz.Document:
    """Two genuinely separate dimension lines sharing an axis coordinate far apart."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=800)
    if not vertical:
        y = 250
        page.draw_line((100, y), (180, y))
        page.insert_text((130, y - 3), value_text, fontsize=10)
        # a second, unrelated horizontal line far below at the same y-band
        # is not physically meaningful for a horizontal line (would be a
        # different y); emulate the "unrelated far collinear" horizontal
        # case as a second run on the same y but far to the right, well
        # beyond any plausible text-gap bracket.
        page.draw_line((400, y), (480, y))
    else:
        x = 250
        page.draw_line((x, 100), (x, 180))
        page.insert_text((x + 3, 140), value_text, fontsize=10, rotate=90)
        page.draw_line((x, 600), (x, 680))
    return _reopen(doc)


def _resolve(doc: fitz.Document, *, view_id: str = "V") -> tuple:
    page = doc[0]
    bundle = extract_dimension_evidence_bundle(page, page_num=1, view_id=view_id, view_type="floor_plan")
    return bundle


def _binding_for_value(bundle, value: float):
    for obs in bundle.observations:
        if abs(float(obs.value_m) * 1000.0 - value) < 0.5 or abs(float(obs.value) - value) < 0.5:
            for b in bundle.bindings:
                if b.observation_id == obs.dimension_id:
                    return obs, b
    return None, None


class TestTextSplitLineMerge:
    def test_vertical_split_line_resolves_witness_bound(self):
        doc = _split_dimension_page("2400", vertical=True)
        bundle = _resolve(doc)
        obs, binding = _binding_for_value(bundle, 2400)
        assert obs is not None, "observation not extracted"
        assert binding.status == BindingStatus.WITNESS_BOUND.value, binding.notes
        assert binding.endpoints is not None
        assert len(binding.witness_line_ids) == 2

    def test_horizontal_split_line_resolves_witness_bound(self):
        doc = _split_dimension_page("4300", vertical=False)
        bundle = _resolve(doc)
        obs, binding = _binding_for_value(bundle, 4300)
        assert obs is not None
        assert binding.status == BindingStatus.WITNESS_BOUND.value, binding.notes

    def test_reverse_draw_order_still_resolves(self):
        doc = _split_dimension_page("2400", vertical=True, reverse_draw_order=True)
        bundle = _resolve(doc)
        obs, binding = _binding_for_value(bundle, 2400)
        assert obs is not None
        assert binding.status == BindingStatus.WITNESS_BOUND.value, binding.notes

    def test_translation_invariance(self):
        doc = _split_dimension_page("2400", vertical=True, offset_x=57.0, offset_y=-33.0)
        bundle = _resolve(doc)
        obs, binding = _binding_for_value(bundle, 2400)
        assert obs is not None
        assert binding.status == BindingStatus.WITNESS_BOUND.value, binding.notes

    def test_scale_invariance(self):
        doc = _split_dimension_page("6000", vertical=True, scale=2.5, half_len=90.0)
        bundle = _resolve(doc)
        obs, binding = _binding_for_value(bundle, 6000)
        assert obs is not None
        assert binding.status == BindingStatus.WITNESS_BOUND.value, binding.notes

    def test_far_unrelated_collinear_lines_not_merged(self):
        doc = _unrelated_far_collinear_page("1500", vertical=True)
        bundle = _resolve(doc)
        obs, binding = _binding_for_value(bundle, 1500)
        assert obs is not None
        # far apart (400pt gap) -- must not be silently stitched together
        assert binding.status != BindingStatus.WITNESS_BOUND.value or (
            binding.dimension_line_id is not None and "+" not in binding.dimension_line_id
        )

    def test_deterministic_replay(self):
        doc1 = _split_dimension_page("3100", vertical=True)
        doc2 = _split_dimension_page("3100", vertical=True)
        b1 = _resolve(doc1)
        b2 = _resolve(doc2)
        _, bind1 = _binding_for_value(b1, 3100)
        _, bind2 = _binding_for_value(b2, 3100)
        assert bind1.status == bind2.status
        assert bind1.endpoints == bind2.endpoints


class TestMergeHelperDirect:
    """Direct unit tests of _merge_text_split_line_fragments in isolation."""

    def _seg(self, seg_id, start, end):
        return ObservedGeometrySegment(
            segment_id=seg_id,
            source_page=1,
            start=start,
            end=end,
            coordinate_space=CoordinateSpace.PDF_POINTS.value,
            view_id="V",
        )

    def test_vertical_fragments_merge(self):
        a = self._seg("a", (100.0, 50.0), (100.0, 90.0))
        b = self._seg("b", (100.0, 110.0), (100.0, 150.0))
        merged = _merge_text_split_line_fragments(
            (95.0, 90.0, 120.0, 110.0), a, b, axis_tolerance=1.0, text_margin=3.0
        )
        assert merged is not None
        assert merged.orientation == "vertical"
        ys = sorted((merged.start[1], merged.end[1]))
        assert ys == [50.0, 150.0]

    def test_wrong_orientation_never_merges(self):
        a = self._seg("a", (100.0, 50.0), (100.0, 90.0))
        b = self._seg("b", (0.0, 100.0), (200.0, 100.0))
        merged = _merge_text_split_line_fragments(
            (95.0, 90.0, 120.0, 110.0), a, b, axis_tolerance=1.0, text_margin=3.0
        )
        assert merged is None

    def test_different_axis_coordinate_never_merges(self):
        a = self._seg("a", (100.0, 50.0), (100.0, 90.0))
        b = self._seg("b", (140.0, 110.0), (140.0, 150.0))
        merged = _merge_text_split_line_fragments(
            (95.0, 90.0, 120.0, 110.0), a, b, axis_tolerance=1.0, text_margin=3.0
        )
        assert merged is None

    def test_gap_not_bracketing_text_never_merges(self):
        a = self._seg("a", (100.0, 50.0), (100.0, 90.0))
        b = self._seg("b", (100.0, 500.0), (100.0, 540.0))
        merged = _merge_text_split_line_fragments(
            (95.0, 90.0, 120.0, 110.0), a, b, axis_tolerance=1.0, text_margin=3.0
        )
        assert merged is None

    def test_overlapping_fragments_never_merge(self):
        a = self._seg("a", (100.0, 50.0), (100.0, 120.0))
        b = self._seg("b", (100.0, 90.0), (100.0, 150.0))
        merged = _merge_text_split_line_fragments(
            (95.0, 90.0, 120.0, 110.0), a, b, axis_tolerance=1.0, text_margin=3.0
        )
        assert merged is None

    def test_no_mutation_of_inputs(self):
        a = self._seg("a", (100.0, 50.0), (100.0, 90.0))
        b = self._seg("b", (100.0, 110.0), (100.0, 150.0))
        a_before = (a.segment_id, a.start, a.end)
        b_before = (b.segment_id, b.start, b.end)
        _merge_text_split_line_fragments(
            (95.0, 90.0, 120.0, 110.0), a, b, axis_tolerance=1.0, text_margin=3.0
        )
        assert (a.segment_id, a.start, a.end) == a_before
        assert (b.segment_id, b.start, b.end) == b_before

    def test_input_order_symmetric(self):
        a = self._seg("a", (100.0, 50.0), (100.0, 90.0))
        b = self._seg("b", (100.0, 110.0), (100.0, 150.0))
        m1 = _merge_text_split_line_fragments((95.0, 90.0, 120.0, 110.0), a, b, axis_tolerance=1.0, text_margin=3.0)
        m2 = _merge_text_split_line_fragments((95.0, 90.0, 120.0, 110.0), b, a, axis_tolerance=1.0, text_margin=3.0)
        assert m1 is not None and m2 is not None
        assert sorted((m1.start, m1.end)) == sorted((m2.start, m2.end))
