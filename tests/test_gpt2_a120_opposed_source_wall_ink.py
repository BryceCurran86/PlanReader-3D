"""Original A120 double face continuity is source ink, not a ceiling area."""
import hashlib
from pathlib import Path

import fitz
import pytest
from tools.diag_native_opposed_source_wall_ink_shadow import (
    source_parallel_face_candidates as audit,
    union_source_intervals,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_original_a120_black_native_top_double_wall_is_exact_contiguous_source():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as document:
        page=document[8]
        a=audit(page,
                native_side_a=("d1798i0","d9776i0"),
                native_side_b=("d1796i0","d9774i0"))
        assert a["status"]=="source_paint_consistent_parallel_candidate_pair"
        assert a["original_native_axis"]=="native_x"
        assert abs(a["source_parallel_face_separation_pdf_pts"]-8.64)<.001
        assert a["source_shared_opposed_intervals_pdf_pts"]==[[266.64,1222.08]]
        assert a["source_complete_opposed_intervals_without_added_ink"]
        assert abs(a["source_shared_opposed_length_pdf_pt"]-955.44)<1e-6
        assert len(a["original_candidate_rows"])==4
        assert not a["original_structural_wall_role_authenticated"]
        assert not a["ceiling_plan_metric_area_authority_granted"]
        assert a["new_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


def test_original_a120_left_continuous_double_wall_has_four_independent_segments():
    raw=PDF.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as d:
        a=audit(d[8],
                native_side_a=("d9741i0","d9745i0","d9749i0","d1127i0"),
                native_side_b=("d9739i0","d9743i0","d9747i0","d1125i0"))
        assert a["status"]=="source_paint_consistent_parallel_candidate_pair"
        assert a["original_native_axis"]=="native_y"
        assert a["source_shared_opposed_intervals_pdf_pts"]==[[465.92,1951.52]]
        assert abs(a["source_parallel_face_separation_pdf_pts"]-8.40)<.001
        assert a["source_complete_opposed_intervals_without_added_ink"]
        assert not a["physical_room_ring_source_closed"]


def test_original_bottom_window_gaps_are_not_cleared_by_other_wall_segments():
    raw=PDF.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as d:
        a=audit(d[8],
                native_side_a=("d9783i0","d9782i0","d9781i0","d9780i0"),
                native_side_b=("d1798i0","d9776i0"))
        assert a["status"]=="source_parallel_ink_separation_not_wall_scale"
        assert not a["source_wall_aspect_ratio_candidate_only"]
        assert a["source_shared_opposed_length_pdf_pt"]>0
        assert a["source_parallel_face_separation_pdf_pts"]>1000
        assert a["new_wall_authority"]==0


def test_synthetic_collinear_source_gap_can_not_be_closed_by_stroke_width():
    doc=fitz.open()
    page=doc.new_page(width=300,height=300)
    page.draw_line((20,20),(80,20),color=(0,0,0),width=.96)
    page.draw_line((82,20),(140,20),color=(0,0,0),width=.96)
    page.draw_line((20,30),(140,30),color=(0,0,0),width=.96)
    r=audit(page,native_side_a=("d0i0","d1i0"),native_side_b=("d2i0",))
    assert r["source_unbridged_side_intervals_pdf_pts"][0]==[[20.,80.],[82.,140.]]
    assert not r["source_complete_opposed_intervals_without_added_ink"]
    assert r["new_wall_authority"]==0
    doc.close()


def test_thin_grid_line_style_mismatch_is_not_structural_support():
    doc=fitz.open()
    page=doc.new_page(width=300,height=300)
    page.draw_line((20,20),(200,20),color=(0,0,0),width=.96)
    page.draw_line((20,30),(200,30),color=(.5,.5,.5),width=.24)
    r=audit(page,native_side_a=("d0i0",),native_side_b=("d1i0",))
    assert r["status"]=="source_paint_mismatch_competing_parallel_lines"
    assert not r["source_ink_style_consistent_not_wall_role"]
    assert r["new_quantities"]==0
    doc.close()


def test_metameric_reverse_interval_order_keeps_actual_breaks():
    src=[[40.,80.],[20.,40.],[100.,150.]]
    assert union_source_intervals(src)==union_source_intervals(list(reversed(src)))==[[20.,80.],[100.,150.]]
    doc=fitz.open();p=doc.new_page()
    p.draw_line((20,20),(100,20))
    p.draw_line((20,20),(100,20))
    with pytest.raises(ValueError,match="distinct_explicit_competing"):
        audit(p,native_side_a=("d0i0",),native_side_b=("d0i0",))
    doc.close()
