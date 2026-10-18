"""Original-source A120 GRID ink candidates. No customer quantity authority."""
from __future__ import annotations

from pathlib import Path
import hashlib

import fitz
import pytest

from tools.diag_gpt2_a120_grid_ring_shadow import (
    original_stroked_grid_rectangles_shadow as find,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def synthetic(*, scale=1.0, dx=0.0, dy=0.0, missing_edge=False,
              white_mask=False, rival=False, duplicate=False, extra_grid=False,
              ink=(0,0,0), edge_shortfall=0.0, no_grid=False):
    pdf = fitz.open()
    page = pdf.new_page(width=1500,height=1700)
    def pt(x,y):
        return fitz.Point(x*scale+dx,y*scale+dy)
    points = ((100,200),(700,200),(700,900),(100,900))
    if white_mask:
        page.draw_rect(fitz.Rect(pt(100,200),pt(700,900)),color=None,fill=(1,1,1))
    else:
        edges = ((0,1),(1,2),(2,3),(3,0))
        for edge_number,(i,j) in enumerate(edges):
            if missing_edge and edge_number == 3:
                continue
            start,stop = points[i],points[j]
            if edge_number == 3 and edge_shortfall:
                start = (100,900-edge_shortfall)
            page.draw_line(pt(*start),pt(*stop),color=ink,width=0.48*scale)
            if duplicate and edge_number == 2:
                page.draw_line(pt(*start),pt(*stop),color=ink,width=0.48*scale)
        if not no_grid:
            for y in (300,400,500,600,700,800):
                page.draw_line(pt(120,y),pt(680,y),color=ink,width=0.30*scale)
            for x in (200,300,400,500,600):
                page.draw_line(pt(x,230),pt(x,870),color=ink,width=0.30*scale)
    page.insert_text(pt(350,550),"GRID",fontsize=13*scale,color=(0,0,0))
    if rival:
        page.insert_text(pt(300,580),"IPF1",fontsize=12*scale,color=(0,0,0))
    if extra_grid:
        page.insert_text(pt(500,520),"GRID",fontsize=12*scale,color=(0,0,0))
    return pdf,page


def test_four_independent_visible_strokes_and_grid_ink_are_only_candidates():
    pdf,page = synthetic()
    try:
        result = find(page)
        assert result["candidate_count"] == 1
        row = result["candidates"][0]
        assert row["bbox_pdf_pts"] == [100.,200.,700.,900.]
        assert len(set(row["source_path_ids"])) == 4
        assert row["source_interior_grid_h_positions"] >= 4
        assert row["source_interior_grid_v_positions"] >= 4
        assert row["physical_room_source_authority"] is False
        assert row["source_scale_authority"] is False
        assert row["firm_quantity_m2"] is None
        assert result["new_firm_quantities"] == 0
    finally:
        pdf.close()


@pytest.mark.parametrize("options",[
    {"missing_edge":True}, {"white_mask":True}, {"rival":True},
    {"extra_grid":True}, {"ink":(1,0,0)}, {"edge_shortfall":10},
    {"no_grid":True},
])
def test_missing_or_competing_original_ink_cannot_claim_ceiling(options):
    pdf,page = synthetic(**options)
    try:
        result = find(page)
        assert result["candidate_count"] == 0
        assert result["new_firm_quantities"] == 0
    finally:
        pdf.close()


def test_duplicate_source_paths_preserve_rivals_instead_of_first_wins():
    pdf,page = synthetic(duplicate=True)
    try:
        result = find(page)
        assert result["candidate_count"] == 2
        assert len({tuple(row["bbox_pdf_pts"]) for row in result["candidates"]}) == 1
        assert len({tuple(row["source_path_ids"]) for row in result["candidates"]}) == 2
        assert all(row["firm_quantity_m2"] is None for row in result["candidates"])
    finally:
        pdf.close()


@pytest.mark.parametrize("scale,dx,dy",[(1,0,0),(0.7,210,270),(1.2,50,40)])
def test_translation_and_scaling_do_not_grant_metric_authority(scale,dx,dy):
    pdf,page = synthetic(scale=scale,dx=dx,dy=dy)
    try:
        result = find(page,min_span_pt=100*scale)
        assert result["candidate_count"] == 1
        assert result["candidates"][0]["firm_quantity_m2"] is None
        assert result["candidates"][0]["bbox_pdf_pts"] == pytest.approx([
            100*scale+dx,200*scale+dy,700*scale+dx,900*scale+dy,
        ],abs=0.01)
    finally:
        pdf.close()


@pytest.mark.parametrize("native_rotation",[0,90,180,270])
def test_native_page_rotation_does_not_invent_an_area_or_change_ink_owners(native_rotation):
    pdf,page = synthetic()
    try:
        page.set_rotation(native_rotation)
        result = find(page)
        assert result["candidate_count"] == 1
        assert result["candidates"][0]["firm_quantity_m2"] is None
        assert result["candidates"][0]["source_scale_authority"] is False
    finally:
        pdf.close()


def test_bad_lexical_or_dimension_inputs_fail_before_source_interpretation():
    pdf,page = synthetic()
    try:
        with pytest.raises(ValueError,match="finite_positive"):
            find(page,min_span_pt=0)
        with pytest.raises(ValueError,match="literal_material_code"):
            find(page,code="grid")
    finally:
        pdf.close()


def test_original_office_grid_material_and_room_labels_require_physical_owner():
    """Same-room ceiling marks in different PDF blocks cannot bind by block ID."""
    if not ORIGINAL.is_file():
        pytest.skip("private source absent: crosssheet finish ownership not authenticated")
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    with fitz.open(stream=raw, filetype="pdf") as pdf:
        page = pdf[8]
        office = [w for w in page.get_text("words")
                  if w[4] == "OFFICE" and w[5] == 9 and w[6] == 0]
        grid = [w for w in page.get_text("words")
                if w[4] == "GRID" and w[5] == 10 and w[6] == 1]
        assert len(office) == len(grid) == 1
        assert office[0][5] != grid[0][5]
        assert len([w for w in page.get_text("words") if w[4] == "GRID"]) == 3
    # This test does not authorize jumping PDF block IDs by nearest label.
    # A source-owned closed physical ceiling zone is mandatory before binding.


def test_original_sha_verified_page9_sales_grid_has_two_source_path_owners():
    if not ORIGINAL.is_file():
        pytest.skip("private original absent from public CI: positive NOT executed")
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    with fitz.open(stream=raw,filetype="pdf") as document:
        assert len(document) == 31
        page = document[8]
        assert page.rotation == 90
        result = find(page)
        assert result["candidate_count"] == 2
        expected = [703.44,646.40002,1217.03992,1550.47998]
        assert all(row["bbox_pdf_pts"] == pytest.approx(expected,abs=0.001)
                   for row in result["candidates"])
        assert {tuple(row["source_path_ids"]) for row in result["candidates"]} == {
            (3897,3899,3898,3900),(3897,5135,3898,3900)
        }
        assert all(row["source_mark_address"] == (114,1,0)
                   for row in result["candidates"])
        assert all(row["source_interior_grid_h_positions"] >= 4
                   and row["source_interior_grid_v_positions"] >= 4
                   for row in result["candidates"])
        assert all(row["firm_quantity_m2"] is None for row in result["candidates"])
        assert result["new_firm_quantities"] == 0
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == SHA
