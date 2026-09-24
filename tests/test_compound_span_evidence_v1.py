"""Synthetic tests for pb_compound_span_evidence (shadow-only, not wired).

All geometry and values are arbitrary and synthetic -- none reuse Lamu's
real 200/6100/200/1500/200/8200mm chain. No benchmark ground truth is used.

This module is not wired into any live extraction path; these tests only
exercise resolve_compound_span() directly against real fitz-drawn pages.
"""
from __future__ import annotations

from typing import Sequence

import fitz
import pytest

from pb_compound_span_evidence import (
    CompoundSpanEvidence,
    SpanRole,
    _find_contiguous_runs,
    resolve_compound_span,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_viewport_segmentation import segment_page_viewports


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _draw_chain_ticks_vertical(page: fitz.Page, *, x: float, ys: Sequence[float], tick: float = 6.0) -> None:
    # One tick per break point, shared by the segments on either side of it
    # -- matches real drafting convention (a junction has one tick, not one
    # per adjoining segment) and avoids two coincident tick lines creating
    # a spurious line-vs-tick binding tie at shared chain junctions.
    for y in ys:
        page.draw_line((x - tick, y), (x + tick, y))


def _draw_chain_ticks_horizontal(page: fitz.Page, *, y: float, xs: Sequence[float], tick: float = 6.0) -> None:
    for x in xs:
        page.draw_line((x, y - tick), (x, y + tick))


def _draw_vertical_segment_line_and_text(page: fitz.Page, *, x: float, y0: float, y1: float, text: str) -> None:
    page.draw_line((x, y0), (x, y1))
    page.insert_text((x + 5.0, (y0 + y1) / 2.0), text, fontsize=9, rotate=90)


def _draw_horizontal_segment_line_and_text(page: fitz.Page, *, y: float, x0: float, x1: float, text: str) -> None:
    page.draw_line((x0, y), (x1, y))
    # Offset toward increasing y (away from the outer overall track, which
    # sits at a smaller y) so the caption stays unambiguously closer to its
    # own inner-track line than to the parallel outer one.
    page.insert_text(((x0 + x1) / 2.0 - 8, y + 14.0), text, fontsize=9)


def _compound_chain_pdf(
    *,
    axis: str = "vertical",
    primary_text: str = "4000",
    boundary_text: str = "200",
    secondary_text: str = "1200",
    label: str | None = "VERANDAH",
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    scale: float = 1.0,
    include_overall: bool = True,
    include_boundary: bool = True,
    missing_segment: bool = False,
    duplicate_overall: bool = False,
    overall_text_override: str | None = None,
    second_label: str | None = None,
    unrelated_dims: bool = False,
) -> bytes:
    """One primary+boundary+secondary run on an inner track, with an outer
    overall dimension on a parallel offset track, inside a drawn (RESOLVED)
    floor-plan frame.
    """
    extent = 4200.0 * scale
    page_size = extent + 700.0 + max(0.0, offset_x, offset_y)
    doc = fitz.open()
    page = doc.new_page(width=page_size, height=page_size)

    fx0, fy0 = 80.0 + offset_x, 80.0 + offset_y
    fx1, fy1 = fx0 + extent, fy0 + extent
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    page.insert_text((fx0 + 10, fy1 - 10), "GROUND FLOOR PLAN", fontsize=10)

    primary_mm = float(primary_text)
    boundary_mm = float(boundary_text) if include_boundary else 0.0
    secondary_mm = float(secondary_text)
    total_mm = primary_mm + (2 * boundary_mm if include_boundary else 0.0) + secondary_mm
    scale_pt_per_mm = extent / total_mm

    segs = [("boundary1", boundary_mm, boundary_text)] if include_boundary else []
    segs.append(("primary", primary_mm, primary_text))
    if include_boundary:
        segs.append(("boundary2", boundary_mm, boundary_text))
    segs.append(("secondary", secondary_mm, secondary_text))

    if axis == "vertical":
        inner_x = fx0 + 40.0 * scale
        outer_x = inner_x - 25.0 * scale
        y = fy0

        breaks = [y]
        cursor = y
        for _role, mm, _text in segs:
            cursor += mm * scale_pt_per_mm
            breaks.append(cursor)
        _draw_chain_ticks_vertical(page, x=inner_x, ys=breaks)
        if include_overall:
            _draw_chain_ticks_vertical(page, x=outer_x, ys=(y, cursor))

        cursor = y
        for _role, mm, text in segs:
            seg_y0, seg_y1 = cursor, cursor + mm * scale_pt_per_mm
            if not (missing_segment and _role == "boundary2"):
                _draw_vertical_segment_line_and_text(page, x=inner_x, y0=seg_y0, y1=seg_y1, text=text)
            cursor = seg_y1

        overall_val = overall_text_override or str(int(round(total_mm)))
        if include_overall:
            page.draw_line((outer_x, y), (outer_x, cursor))
            page.insert_text((outer_x - 20.0, (y + cursor) / 2.0), overall_val, fontsize=9, rotate=90)
        if duplicate_overall:
            outer_x2 = outer_x - 45.0 * scale
            page.draw_line((outer_x2, y), (outer_x2, cursor))
            page.draw_line((outer_x2 - 6, y), (outer_x2 + 6, y))
            page.draw_line((outer_x2 - 6, cursor), (outer_x2 + 6, cursor))
            page.insert_text((outer_x2 - 20.0, (y + cursor) / 2.0), overall_val, fontsize=9, rotate=90)

        if label:
            label_x = inner_x + 15
            label_y = cursor - 5
            page.insert_text((label_x, label_y), label, fontsize=9)
        if second_label:
            page.insert_text((inner_x + 15, y + 20), second_label, fontsize=9)
    else:
        inner_y = fy0 + 40.0 * scale
        outer_y = inner_y - 25.0 * scale
        x = fx0

        breaks = [x]
        cursor = x
        for _role, mm, _text in segs:
            cursor += mm * scale_pt_per_mm
            breaks.append(cursor)
        _draw_chain_ticks_horizontal(page, y=inner_y, xs=breaks)
        if include_overall:
            _draw_chain_ticks_horizontal(page, y=outer_y, xs=(x, cursor))

        cursor = x
        for _role, mm, text in segs:
            seg_x0, seg_x1 = cursor, cursor + mm * scale_pt_per_mm
            if not (missing_segment and _role == "boundary2"):
                _draw_horizontal_segment_line_and_text(page, y=inner_y, x0=seg_x0, x1=seg_x1, text=text)
            cursor = seg_x1

        overall_val = overall_text_override or str(int(round(total_mm)))
        if include_overall:
            page.draw_line((x, outer_y), (cursor, outer_y))
            page.insert_text(((x + cursor) / 2.0 - 8, outer_y - 15.0), overall_val, fontsize=9)

        if label:
            page.insert_text((cursor - 60, inner_y + 15), label, fontsize=9)
        if second_label:
            page.insert_text((x + 10, inner_y + 15), second_label, fontsize=9)

    if unrelated_dims:
        ux = page_size - 250.0
        page.draw_line((ux, ux), (ux + 100, ux))
        page.draw_line((ux, ux - 6), (ux, ux + 6))
        page.draw_line((ux + 100, ux - 6), (ux + 100, ux + 6))
        page.insert_text((ux + 35, ux - 5), "999", fontsize=9)

    data = doc.tobytes()
    doc.close()
    return data


def _resolve(pdf_bytes: bytes, *, axis: str = "vertical") -> CompoundSpanEvidence:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    viewports = segment_page_viewports(page, page_number=1)
    plan_vps = [v for v in viewports if v.view_type == "floor_plan"]
    assert plan_vps, "no floor_plan viewport found in synthetic fixture"
    return resolve_compound_span(page, page_num=1, viewport=plan_vps[0], axis=axis)


class TestCompoundSpanResolution:
    def test_full_chain_resolves_corroborated_with_roles(self):
        pdf = _compound_chain_pdf()
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value, res.reason_codes
        roles = {c.role for c in res.components}
        assert SpanRole.PRIMARY_ENCLOSED.value in roles
        assert SpanRole.SECONDARY_STRIP.value in roles
        assert SpanRole.BOUNDARY_THICKNESS.value in roles
        primary = res.primary_component
        secondary = res.secondary_component
        assert primary is not None and abs(primary.value_m - 4.0) < 0.01
        assert secondary is not None and abs(secondary.value_m - 1.2) < 0.01

    def test_horizontal_axis_secondary_strip_left(self):
        pdf = _compound_chain_pdf(axis="horizontal")
        res = _resolve(pdf, axis="horizontal")
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value, res.reason_codes
        assert res.secondary_component is not None

    def test_missing_segment_abstains(self):
        pdf = _compound_chain_pdf(missing_segment=True)
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.ABSTAINED.value

    def test_overall_unrelated_to_chain_abstains(self):
        # Overall dimension present but placed with a value/extent that
        # cannot bracket the inner run's own endpoints.
        pdf = _compound_chain_pdf(overall_text_override="9999")
        res = _resolve(pdf)
        # Endpoints still coincide (only the printed value differs) so this
        # exercises the independent value-sum cross-check specifically.
        assert res.status == EvidenceResolutionStatus.ABSTAINED.value
        assert "member_sum_does_not_match_overall_value" in res.reason_codes

    def test_enclosed_room_label_not_treated_as_secondary_strip(self):
        pdf = _compound_chain_pdf(label="STORE")
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value
        assert res.secondary_component is None
        roles = {c.role for c in res.components}
        assert SpanRole.SECONDARY_STRIP.value not in roles

    def test_two_labels_leave_secondary_unassigned(self):
        pdf = _compound_chain_pdf(label="VERANDAH", second_label="VERANDAH")
        res = _resolve(pdf)
        # Ambiguous label ownership (two labels in one viewport) must not
        # force a secondary-strip assignment.
        assert res.secondary_component is None

    def test_no_boundary_still_resolves_when_sum_matches(self):
        pdf = _compound_chain_pdf(include_boundary=False)
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value
        roles = {c.role for c in res.components}
        assert SpanRole.BOUNDARY_THICKNESS.value not in roles

    def test_translation_invariance(self):
        pdf = _compound_chain_pdf(offset_x=53.0, offset_y=-27.0)
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value

    def test_scale_invariance(self):
        pdf = _compound_chain_pdf(scale=1.8, primary_text="6000", boundary_text="150", secondary_text="1800")
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value
        assert abs(res.primary_component.value_m - 6.0) < 0.01

    def test_unrelated_dimensions_do_not_interfere(self):
        pdf = _compound_chain_pdf(unrelated_dims=True)
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value
        ids = {c.dimension_id for c in res.components}
        assert len(res.components) == 4  # boundary, primary, boundary, secondary -- not the unrelated "999"

    def test_stable_evidence_id_across_reruns(self):
        pdf = _compound_chain_pdf()
        res1 = _resolve(pdf)
        res2 = _resolve(pdf)
        assert res1.evidence_id == res2.evidence_id
        assert res1.status == res2.status == EvidenceResolutionStatus.CORROBORATED.value

    def test_no_secondary_label_no_secondary_role(self):
        pdf = _compound_chain_pdf(label=None)
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value
        assert res.secondary_component is None

    def test_two_distinct_overall_candidates_conflict(self):
        pdf = _compound_chain_pdf(duplicate_overall=True)
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CONFLICT.value

    def test_no_wall_or_dpc_authority_in_model(self):
        # Structural guarantee, not just a behavioral one: the evidence
        # model this module returns has no field that could be mistaken
        # for wall or DPC authority. A SECONDARY_STRIP role proves
        # footprint/floor-area geometry only (see module docstring) --
        # an open colonnade boundary must never be reinterpreted as a wall.
        pdf = _compound_chain_pdf()
        res = _resolve(pdf)
        assert res.status == EvidenceResolutionStatus.CORROBORATED.value
        component_fields = set(res.components[0].__dataclass_fields__)
        forbidden = {"is_wall", "wall_id", "dpc", "dpc_eligible", "masonry", "wall_bearing"}
        assert not (component_fields & forbidden)
        role_values = {r.value for r in SpanRole}
        assert not any("wall" in r or "dpc" in r for r in role_values)


class TestFindContiguousRunsDirect:
    """Direct unit tests of the run-grouping helper, including input-order
    invariance which is awkward to control via fitz draw order."""

    class _FakeObs:
        def __init__(self, dimension_id, endpoints):
            self.dimension_id = dimension_id
            self.endpoints = endpoints

    def test_input_order_invariance(self):
        a = self._FakeObs("a", ((100.0, 0.0), (100.0, 50.0)))
        b = self._FakeObs("b", ((100.0, 50.0), (100.0, 90.0)))
        c = self._FakeObs("c", ((100.0, 90.0), (100.0, 140.0)))
        runs_forward = _find_contiguous_runs([a, b, c], axis="vertical", axis_tolerance_pt=1.0, contiguity_tolerance_pt=1.0)
        runs_reversed = _find_contiguous_runs([c, b, a], axis="vertical", axis_tolerance_pt=1.0, contiguity_tolerance_pt=1.0)
        ids_forward = [[m.dimension_id for m in r] for r in runs_forward]
        ids_reversed = [[m.dimension_id for m in r] for r in runs_reversed]
        assert ids_forward == ids_reversed == [["a", "b", "c"]]

    def test_gap_breaks_run(self):
        a = self._FakeObs("a", ((100.0, 0.0), (100.0, 50.0)))
        b = self._FakeObs("b", ((100.0, 90.0), (100.0, 140.0)))
        runs = _find_contiguous_runs([a, b], axis="vertical", axis_tolerance_pt=1.0, contiguity_tolerance_pt=1.0)
        assert runs == []

    def test_different_axis_coordinate_not_grouped(self):
        a = self._FakeObs("a", ((100.0, 0.0), (100.0, 50.0)))
        b = self._FakeObs("b", ((140.0, 50.0), (140.0, 90.0)))
        runs = _find_contiguous_runs([a, b], axis="vertical", axis_tolerance_pt=1.0, contiguity_tolerance_pt=1.0)
        assert runs == []
