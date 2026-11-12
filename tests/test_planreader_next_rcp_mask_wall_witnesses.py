"""Source-painted A120 wall strips constrain WHITE fill-mask layout edges."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from planreader_next.engine import NativePage, NativeRectangle, load_native_page
from planreader_next.rcp_mask_wall_witnesses import report_rcp_mask_wall_witnesses
from tests.test_planreader_next_rcp_zone_scope import _rcp_fixture


def _source_painted_white_masks():
    page = _rcp_fixture()
    masks = tuple(
        NativeRectangle(
            rect.ref, rect.bbox, True,
            stroke_present=False, stroke_color=None,
            stroke_width=None, fill_color=(1.0, 1.0, 1.0),
        )
        for rect in page.rectangles
    )
    dark = NativeRectangle(
        "source-dark-wall", (59.0, 40.0, 64.0, 150.0), True,
        stroke_present=False, fill_color=(0.195, 0.195, 0.195),
    )
    return NativePage(
        page.source_sha256, page.page_index, page.words,
        masks + (dark,), page.segments,
    )


def test_white_mask_hints_survive_without_becoming_ceilings():
    page = _source_painted_white_masks()
    got = report_rcp_mask_wall_witnesses(page)
    assert got["layout_mask_count"] == 2
    assert got["strict_stroked_rectangle_count"] == 0
    assert got["height_material_callouts"] == 2
    assert got["metric_ceiling_area_count"] == 0
    assert not got["commercial_publishable"]
    assert got["official_score"] is None
    grid = next(
        row for row in got["layout_mask_candidates"]
        if row["material_code_candidate"] == "GRID"
    )
    assert grid["source_rectangle_ref"] == "zone:grid"
    assert grid["height_mm_source_candidate"] == "2400"
    assert grid["paint_role"] == "UNSTROKED_WHITE_LAYOUT_MASK_NOT_CEILING_BORDER"
    assert grid["edges"]["x_min"]["visible_dark_wall_ref_candidates"] == [
        "source-dark-wall",
    ]
    assert grid["edges"]["x_max"]["covered_fraction_by_dark_wall_ink"] == 0
    assert grid["metric_ceiling_area_m2"] is None
    assert grid["physical_ceiling_zone_authenticated"] is False


def test_bounding_white_rectangle_does_not_authenticate_its_own_four_edges():
    page = _source_painted_white_masks()
    masks_only = NativePage(
        page.source_sha256, page.page_index, page.words,
        tuple(
            rect for rect in page.rectangles if rect.ref != "source-dark-wall"
        ), page.segments,
    )
    got = report_rcp_mask_wall_witnesses(masks_only)
    assert got["layout_mask_count"] == 2
    assert got["dark_wall_ink_rect_count"] == 0
    for mask in got["layout_mask_candidates"]:
        assert all(
            side["covered_fraction_by_dark_wall_ink"] == 0
            for side in mask["edges"].values()
        )
        assert mask["metric_ceiling_area_m2"] is None


def _original_a120():
    path = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not path or not Path(path).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    return load_native_page(Path(path), 8)


def test_original_maryborough_a120_rectangle1_rectangle3_actual_wall_step():
    page = _original_a120()
    assert page.source_sha256 == (
        "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    )
    got = report_rcp_mask_wall_witnesses(page)
    assert got["height_material_callouts"] == 18
    assert got["layout_mask_count"] == 13
    assert got["strict_stroked_rectangle_count"] == 0
    by_ref = {
        row["source_rectangle_ref"]: row
        for row in got["layout_mask_candidates"]
    }
    one = by_ref["rect:p114:i0"]
    three = by_ref["rect:p116:i0"]
    assert one["material_code_candidate"] == "WFPB"
    assert one["height_mm_source_candidate"] == "2400"
    # An actual short source ink gap must remain visible, not rounded
    # into a fictitious perfectly closed ceiling edge.
    assert 0.97 < one["edges"]["y_max"]["covered_fraction_by_dark_wall_ink"] < 1
    assert three["material_code_candidate"] == "FPB"
    assert three["height_mm_source_candidate"] == "3000"
    assert three["edges"]["y_min"]["unsupported_intervals_pdf_pts"] == [
        [571.2, 702.48]
    ]
    assert "rect:p63:i0" in three["edges"]["y_min"][
        "visible_dark_wall_ref_candidates"
    ]
    assert any(
        x["unsupported_mask_side"] == "y_min"
        and x["source_dark_wall_ref"] == "rect:p73:i0"
        and x["parallel_wall_coverage_fraction"] == 1.0
        and x["physical_finished_face_authenticated"] is False
        for x in three["alternative_dark_wall_step_witnesses"]
    )
    junction = next(
        entry for entry in got["layout_mask_overlaps"]
        if set(entry["source_rectangle_refs"]) == {
            "rect:p114:i0", "rect:p116:i0"
        }
    )
    assert junction["intersection_bbox_pdf_pts"] == [
        571.2, 1556.96, 693.6, 1584.56
    ]
    assert junction["source_boundary_resolution_required"]
    assert "rect:p73:i0" in junction[
        "independently_painted_dark_wall_refs"
    ]
    assert got["metric_ceiling_area_count"] == 0


def test_original_maryborough_sales_false_vertical_line_is_not_wall():
    page = _original_a120()
    got = report_rcp_mask_wall_witnesses(page)
    fill = next(
        row for row in got["layout_mask_candidates"]
        if row["source_rectangle_ref"] == "rect:p141:i0"
    )
    assert fill["material_code_candidate"] == "FPB"
    assert fill["height_mm_source_candidate"] == "3000"
    assert fill["edges"]["y_max"]["unsupported_intervals_pdf_pts"] == [
        [694.08, 1217.04]
    ]
    assert fill["edges"]["y_max"][
        "covered_fraction_by_dark_wall_ink"
    ] < 0.5
    assert fill["edges"]["y_max"]["drawn_boundary_authenticated"] is False
    assert not fill["physical_ceiling_zone_authenticated"]
    assert fill["metric_ceiling_area_m2"] is None
