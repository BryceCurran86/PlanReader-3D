"""Mutation/metamorphic/red-team tests for F.07 viewport segmentation.

All drawings are synthetic. No development-benchmark quantities, project names,
file names, or expected takeoff outputs are used.
"""
from __future__ import annotations

import uuid

import fitz
import pytest

from pb_drawing_evidence_binding import DrawingViewType
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_viewport_segmentation import (
    ViewportBoundarySource,
    ViewportSegmentationStatus,
    assign_bbox_to_viewport,
    is_authoritative_derived_viewport,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _two_framed_views(*, dx: float = 0.0, dy: float = 0.0, page_width: float = 640, page_height: float = 420) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=page_width, height=page_height)
    left = fitz.Rect(30 + dx, 30 + dy, 295 + dx, 350 + dy)
    right = fitz.Rect(330 + dx, 30 + dy, 595 + dx, 350 + dy)
    page.draw_rect(left)
    page.draw_rect(right)

    # View content exists independently of the title text.
    page.draw_line((65 + dx, 100 + dy), (255 + dx, 100 + dy))
    page.draw_line((65 + dx, 100 + dy), (65 + dx, 240 + dy))
    page.draw_line((365 + dx, 90 + dy), (555 + dx, 90 + dy))
    page.draw_line((460 + dx, 70 + dy), (460 + dx, 250 + dy))

    page.insert_text((80 + dx, 320 + dy), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((92 + dx, 338 + dy), "SCALE 1:100", fontsize=9)
    page.insert_text((390 + dx, 320 + dy), "NORTH ELEVATION", fontsize=11)
    page.insert_text((405 + dx, 338 + dy), "SCALE 1:50", fontsize=9)
    return _reopen(doc)


def _semantic_signature(viewports):
    return sorted(
        (
            v.view_type,
            v.status,
            v.boundary_source,
            v.scale_denominator,
            round(v.bounding_box[2] - v.bounding_box[0], 3) if v.bounding_box else None,
            round(v.bounding_box[3] - v.bounding_box[1], 3) if v.bounding_box else None,
        )
        for v in viewports
    )


def test_two_vector_frames_resolve_actual_viewport_regions_and_scales():
    doc = _two_framed_views()
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert len(viewports) == 2
    assert validate_non_overlapping_viewports(viewports)

    by_type = {v.view_type: v for v in viewports}
    plan = by_type[DrawingViewType.FLOOR_PLAN.value]
    elevation = by_type[DrawingViewType.ELEVATION.value]

    assert plan.status == ViewportSegmentationStatus.RESOLVED.value
    assert elevation.status == ViewportSegmentationStatus.RESOLVED.value
    assert plan.boundary_source == ViewportBoundarySource.VECTOR_FRAME.value
    assert elevation.boundary_source == ViewportBoundarySource.VECTOR_FRAME.value
    # The spatial bbox is the drawing frame, not the tiny title-text bbox.
    assert plan.bounding_box == pytest.approx((30, 30, 295, 350))
    assert elevation.bounding_box == pytest.approx((330, 30, 595, 350))
    assert plan.scale_denominator == pytest.approx(100.0)
    assert elevation.scale_denominator == pytest.approx(50.0)
    assert not plan.scale_conflict
    assert not elevation.scale_conflict
    doc.close()


def test_mutating_view_specific_scale_changes_only_that_viewport_scale():
    base = _two_framed_views()
    changed = fitz.open()
    page = changed.new_page(width=640, height=420)
    page.draw_rect(fitz.Rect(30, 30, 295, 350))
    page.draw_rect(fitz.Rect(330, 30, 595, 350))
    page.insert_text((80, 320), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((92, 338), "SCALE 1:200", fontsize=9)
    page.insert_text((390, 320), "NORTH ELEVATION", fontsize=11)
    page.insert_text((405, 338), "SCALE 1:50", fontsize=9)
    changed = _reopen(changed)

    before = {v.view_type: v for v in segment_page_viewports(base[0], page_number=1)}
    after = {v.view_type: v for v in segment_page_viewports(changed[0], page_number=1)}
    assert before[DrawingViewType.FLOOR_PLAN.value].scale_denominator == 100
    assert after[DrawingViewType.FLOOR_PLAN.value].scale_denominator == 200
    assert before[DrawingViewType.ELEVATION.value].scale_denominator == 50
    assert after[DrawingViewType.ELEVATION.value].scale_denominator == 50
    base.close(); changed.close()


def test_conflicting_scales_inside_one_viewport_remain_unresolved():
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.draw_rect(fitz.Rect(30, 30, 360, 260))
    page.insert_text((110, 220), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((80, 80), "SCALE 1:100", fontsize=9)
    page.insert_text((250, 80), "SCALE 1:50", fontsize=9)
    doc = _reopen(doc)
    viewport = segment_page_viewports(doc[0], page_number=1)[0]
    assert viewport.status == ViewportSegmentationStatus.RESOLVED.value
    assert viewport.scale_conflict
    assert viewport.scale_denominator is None
    assert viewport.scale_raw is None
    assert viewport.notes
    doc.close()


def test_shared_frame_for_two_view_titles_fails_closed_as_ambiguous():
    doc = fitz.open()
    page = doc.new_page(width=500, height=350)
    page.draw_rect(fitz.Rect(30, 30, 470, 300))
    page.insert_text((80, 270), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((300, 270), "WEST ELEVATION", fontsize=11)
    doc = _reopen(doc)
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert len(viewports) == 2
    assert all(v.status == ViewportSegmentationStatus.AMBIGUOUS.value for v in viewports)
    assert all(v.bounding_box is None for v in viewports)
    doc.close()


def test_prose_mention_of_elevation_does_not_create_a_viewport():
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 80), "NOTE: REFER TO NORTH ELEVATION FOR CLADDING SETOUT", fontsize=10)
    doc = _reopen(doc)
    assert segment_page_viewports(doc[0], page_number=1) == []
    doc.close()


def test_single_unframed_title_is_unsupported_not_whole_page_guessed():
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((120, 250), "GROUND FLOOR PLAN", fontsize=11)
    doc = _reopen(doc)
    viewport = segment_page_viewports(doc[0], page_number=1)[0]
    assert viewport.status == ViewportSegmentationStatus.UNSUPPORTED.value
    assert viewport.bounding_box is None
    doc.close()


def test_two_unframed_separated_titles_create_non_overlapping_derived_partition():
    doc = fitz.open()
    page = doc.new_page(width=600, height=360)
    page.insert_text((80, 320), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((390, 320), "EAST ELEVATION", fontsize=11)
    page.insert_text((85, 100), "SCALE 1:100", fontsize=9)
    page.insert_text((405, 100), "SCALE 1:50", fontsize=9)
    doc = _reopen(doc)
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert len(viewports) == 2
    assert all(v.status == ViewportSegmentationStatus.DERIVED.value for v in viewports)
    assert validate_non_overlapping_viewports(viewports)
    by_type = {v.view_type: v for v in viewports}
    assert by_type[DrawingViewType.FLOOR_PLAN.value].scale_denominator == 100
    assert by_type[DrawingViewType.ELEVATION.value].scale_denominator == 50
    # Ordinary one-axis title partitions remain diagnostic-only.
    assert not is_authoritative_derived_viewport(
        by_type[DrawingViewType.FLOOR_PLAN.value]
    )
    assert authoritative_floor_plan_viewports(doc[0], page_number=1) == []
    doc.close()


def _three_column_unframed_grid(*, conflicting_title: bool = False) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=900, height=700)

    # Left column.
    page.insert_text((80, 250), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((90, 620), "ROOF PLAN", fontsize=11)

    # Middle column.
    page.insert_text((380, 200), "ELEVATION E-01", fontsize=11)
    page.insert_text((380, 560), "SECTION S-01", fontsize=11)

    # Right column.
    page.insert_text((680, 200), "ELEVATION E-02", fontsize=11)
    page.insert_text((680, 560), "SECTION S-02", fontsize=11)

    if conflicting_title:
        # A distinct title inside the same minimum-height ownership band must
        # invalidate the grid rather than being collapsed as a duplicate.
        page.insert_text((382, 225), "WEST ELEVATION", fontsize=11)

    return _reopen(doc)


def test_columnar_title_grid_is_strict_derived_floor_plan_authority():
    doc = _three_column_unframed_grid()
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert validate_non_overlapping_viewports(viewports)

    plan = next(
        viewport for viewport in viewports
        if viewport.view_type == DrawingViewType.FLOOR_PLAN.value
    )
    assert plan.status == ViewportSegmentationStatus.DERIVED.value
    assert plan.boundary_source == ViewportBoundarySource.TITLE_PARTITION.value
    assert plan.bounding_box is not None
    assert plan.provenance["partition_mode"] == "columnar_title_grid"
    assert plan.provenance["grid_validated"] is True
    assert is_authoritative_derived_viewport(plan)

    authoritative = authoritative_floor_plan_viewports(doc[0], page_number=1)
    assert len(authoritative) == 1
    assert authoritative[0].label == "GROUND FLOOR PLAN"
    assert authoritative[0].bounding_box == pytest.approx(plan.bounding_box)
    doc.close()


def test_columnar_title_grid_distinct_close_titles_fail_closed():
    doc = _three_column_unframed_grid(conflicting_title=True)
    viewports = segment_page_viewports(doc[0], page_number=1)
    plan = next(
        viewport for viewport in viewports
        if viewport.view_type == DrawingViewType.FLOOR_PLAN.value
    )
    assert plan.status == ViewportSegmentationStatus.AMBIGUOUS.value
    assert plan.bounding_box is None
    assert not is_authoritative_derived_viewport(plan)
    assert authoritative_floor_plan_viewports(doc[0], page_number=1) == []
    doc.close()


def test_bbox_assignment_requires_unique_spatial_owner():
    doc = _two_framed_views()
    viewports = segment_page_viewports(doc[0], page_number=1)
    assert assign_bbox_to_viewport((100, 100, 120, 120), viewports).view_type == DrawingViewType.FLOOR_PLAN.value
    assert assign_bbox_to_viewport((400, 100, 420, 120), viewports).view_type == DrawingViewType.ELEVATION.value
    assert assign_bbox_to_viewport((300, 100, 310, 120), viewports) is None
    doc.close()


def test_translation_metamorphic_preserves_semantic_segmentation():
    base = _two_framed_views()
    moved = _two_framed_views(dx=20, dy=15, page_width=680, page_height=450)
    before = segment_page_viewports(base[0], page_number=1)
    after = segment_page_viewports(moved[0], page_number=1)
    assert _semantic_signature(before) == _semantic_signature(after)
    base.close(); moved.close()


def test_page_number_and_random_identity_do_not_change_view_semantics():
    doc = _two_framed_views()
    first = segment_page_viewports(doc[0], page_number=1)
    # Random identity is deliberately kept outside the segmenter API. Changing
    # provenance page number can change IDs, but not semantic partitioning.
    _ = str(uuid.uuid4())
    second = segment_page_viewports(doc[0], page_number=77)
    assert _semantic_signature(first) == _semantic_signature(second)
    assert [v.view_id for v in first] != [v.view_id for v in second]
    doc.close()


def test_schedule_and_detail_are_separate_from_plan_when_framed():
    doc = fitz.open()
    page = doc.new_page(width=900, height=420)
    frames = [fitz.Rect(20, 30, 280, 350), fitz.Rect(320, 30, 580, 350), fitz.Rect(620, 30, 880, 350)]
    for frame in frames:
        page.draw_rect(frame)
    page.insert_text((60, 320), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((360, 320), "WINDOW SCHEDULE", fontsize=11)
    page.insert_text((690, 320), "TYPICAL DETAIL D1", fontsize=11)
    doc = _reopen(doc)
    types = {v.view_type for v in segment_page_viewports(doc[0], page_number=1)}
    assert types == {
        DrawingViewType.FLOOR_PLAN.value,
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.DETAIL.value,
    }
    doc.close()


def test_plan_floor_layout_title_is_supported_without_relaxing_prose_guard():
    doc = fitz.open()
    page = doc.new_page(width=640, height=420)
    page.draw_rect(fitz.Rect(30, 30, 295, 350))
    page.draw_rect(fitz.Rect(330, 30, 595, 350))
    page.insert_text((80, 320), "PLAN : FLOOR LAYOUT", fontsize=11)
    page.insert_text((400, 320), "LEGEND", fontsize=11)
    doc = _reopen(doc)

    viewports = segment_page_viewports(doc[0], page_number=1)
    by_type = {v.view_type: v for v in viewports}
    assert DrawingViewType.FLOOR_PLAN.value in by_type
    assert by_type[DrawingViewType.FLOOR_PLAN.value].status == ViewportSegmentationStatus.RESOLVED.value
    assert by_type[DrawingViewType.FLOOR_PLAN.value].bounding_box == pytest.approx((30, 30, 295, 350))
    doc.close()

    prose = fitz.open()
    page = prose.new_page(width=400, height=300)
    page.insert_text((40, 80), "NOTE: PLAN : FLOOR LAYOUT REVISED - REFER TO ARCHITECT", fontsize=10)
    prose = _reopen(prose)
    assert segment_page_viewports(prose[0], page_number=1) == []
    prose.close()


def _unframed_plan_legend_columns(*, other_title: str = "LEGEND") -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=840, height=600)
    page.insert_text((150, 510), "PLAN : FLOOR LAYOUT", fontsize=11)
    page.insert_text((700, 330), other_title, fontsize=11)
    return _reopen(doc)


def test_unframed_plan_plus_legend_columns_are_scope_authoritative():
    doc = _unframed_plan_legend_columns()
    viewports = segment_page_viewports(doc[0], page_number=1)
    by_type = {v.view_type: v for v in viewports}
    plan = by_type[DrawingViewType.FLOOR_PLAN.value]
    legend = by_type[DrawingViewType.LEGEND.value]

    assert plan.status == ViewportSegmentationStatus.DERIVED.value
    assert legend.status == ViewportSegmentationStatus.DERIVED.value
    assert plan.provenance["partition_mode"] == "plan_legend_columns"
    assert plan.provenance["grid_validated"] is True
    assert plan.provenance["scope_only"] is True
    assert is_authoritative_derived_viewport(plan)
    assert is_authoritative_derived_viewport(legend)

    authoritative = authoritative_floor_plan_viewports(doc[0], page_number=1)
    assert len(authoritative) == 1
    assert authoritative[0].view_id == plan.view_id
    doc.close()


def test_two_drawing_columns_do_not_gain_plan_legend_scope_authority():
    doc = _unframed_plan_legend_columns(other_title="EAST ELEVATION")
    viewports = segment_page_viewports(doc[0], page_number=1)
    plan = next(v for v in viewports if v.view_type == DrawingViewType.FLOOR_PLAN.value)

    assert plan.status == ViewportSegmentationStatus.DERIVED.value
    assert plan.provenance.get("partition_mode") != "plan_legend_columns"
    assert not is_authoritative_derived_viewport(plan)
    assert authoritative_floor_plan_viewports(doc[0], page_number=1) == []
    doc.close()
