"""Exact original-source multipath table linework without room/material election."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_native_multipath_cad_grid_source_shadow import (
    audit_native_multipath_orthogonal_grid_components as audit,
    _coverage_complete,
    _two_axis_outer_grid_source_witness,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _new_grid(*, incomplete=False, line_color=(0,0,0), split=False, offset=(0,0)):
    doc=fitz.open()
    page=doc.new_page(width=400,height=400)
    xs=[40,75,110,145]
    ys=[50,90,130,170]
    shiftx, shifty=offset
    for x in xs:
        if incomplete and x==145:
            continue
        if split:
            for lo,hi in zip(ys,ys[1:]):
                page.draw_line((x+shiftx,lo+shifty),(x+shiftx,hi+shifty),
                               color=line_color,width=.24)
        else:
            page.draw_line((x+shiftx,50+shifty),(x+shiftx,170+shifty),
                           color=line_color,width=.24)
    for y in ys:
        if split:
            for lo,hi in zip(xs,xs[1:]):
                page.draw_line((lo+shiftx,y+shifty),(hi+shiftx,y+shifty),
                               color=line_color,width=.24)
        else:
            page.draw_line((40+shiftx,y+shifty),(145+shiftx,y+shifty),
                           color=line_color,width=.24)
    return doc,page


def test_true_separate_native_line_paths_can_form_one_candidate_grid():
    doc,page=_new_grid(split=True)
    result=audit(page)
    grids=result["candidate_native_grids"]
    assert result["source_line_universe_complete"]
    assert any(
        tuple(g["native_component_witness"]["native_bbox_pdf_pts"])==(40,50,145,170)
        and g["native_component_witness"]["full_native_outer_grid_candidate"]
        for g in grids
    )
    assert all(not g["native_table_text_or_title_owner_proven"] for g in grids)
    assert all(not g["view_extent_or_ceiling_authority_granted"] for g in grids)
    assert result["new_authoritative_viewports"] == result["new_source_material_or_quantities"] == 0
    doc.close()


def test_single_gap_in_true_outer_border_blocks_grid():
    doc,page=_new_grid(incomplete=True,split=True)
    result=audit(page)
    # Two other ends may remain but a right-hand native wall edge is absent.
    assert not result["candidate_native_grids"]
    doc.close()


def test_transform_replay_and_split_invariant_without_project_rules():
    for split,offset in [(False,(0,0)),(True,(0,0)),
                         (False,(120,60)),(True,(120,60))]:
        doc,page=_new_grid(split=split,offset=offset)
        result=audit(page)
        assert len(result["candidate_native_grids"]) == 1
        grid=result["candidate_native_grids"][0]
        expect=(40+offset[0],50+offset[1],145+offset[0],170+offset[1])
        assert tuple(grid["native_component_witness"]["native_bbox_pdf_pts"]) == expect
        assert grid["native_component_witness"]["full_native_outer_grid_candidate"]
        doc.close()


def test_source_interval_union_does_not_bridge_printed_gaps():
    assert _coverage_complete([(10,20),(20,30)],lo=10,hi=30)
    assert not _coverage_complete([(10,19),(20,30)],lo=10,hi=30)
    assert not _coverage_complete([(11,20),(20,30)],lo=10,hi=30)
    assert not _coverage_complete([(10,20),(20,29)],lo=10,hi=30)


def test_misleading_broken_table_and_scope_cap_fail_closed():
    doc,page=_new_grid()
    with pytest.raises(ValueError):
        audit(page,max_source_line_candidates=0)
    result=audit(page,max_source_line_candidates=1)
    assert result["status"]=="original_axis_source_scope_exceeds_cap"
    assert not result["source_line_universe_complete"]
    assert not result["candidate_native_grids"]
    doc.close()


def test_original_a120_true_multipath_cad_schedule_component_survives():
    data=PDF.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    with fitz.open(stream=data,filetype="pdf") as document:
        page=document[8]
        result=audit(page)
        assert result["status"]=="read_only_original_native_multipath_grid_candidates"
        assert result["source_line_universe_complete"]
        matches=[
            grid for grid in result["candidate_native_grids"]
            if all(abs(v-w)<=.01 for v,w in zip(
                grid["native_component_witness"]["native_bbox_pdf_pts"],
                (1393.68,416.0,1496.4,991.04),
            ))
        ]
        assert len(matches)==1
        grid=matches[0]
        assert grid["original_source_primitive_count"]==25
        assert grid["native_component_witness"]["native_complete_outer_border"]
        assert len(grid["native_component_witness"]["original_full_height_internal_column_coordinates"])>=1
        assert len(grid["native_component_witness"]["original_partially_merged_internal_row_coordinates"])>=1
        assert len(set(grid["original_source_primitive_ids"]))==25
        assert not grid["native_table_text_or_title_owner_proven"]
        assert not grid["original_pdf_clip_paint_source_role_proven"]
        assert not grid["view_extent_or_ceiling_authority_granted"]
        assert not result["new_authoritative_viewports"]
        assert not result["new_source_material_or_quantities"]
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA
