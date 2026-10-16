"""A503 room partition is stepped and must not produce guessed rectangle areas."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_native_stepped_partition_source_shadow import (
    audit_native_stepped_partition_source_candidates as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_source_stepped_witness_retains_two_different_vertical_wall_offsets():
    doc=fitz.open()
    p=doc.new_page(width=400,height=350)
    p.draw_line((100,40),(100,120))
    p.draw_line((175,120),(175,230))
    p.draw_line((100,120),(175,120))
    result=audit(p,candidate_region_bbox=(90,30,200,240))
    assert result["source_native_multiple_parallel_axes_present"]
    assert len(result["competing_original_vertical_axes"])==2
    assert len(result["cross_axis_original_ink_source_ids"])==1
    assert not result["partition_closes_independent_rooms"]
    assert not result["source_physical_room_ring_complete"]
    assert result["new_published_room_areas"]==0
    doc.close()


def test_appearance_of_step_does_not_close_missing_room_doors():
    doc=fitz.open()
    p=doc.new_page(width=300,height=300)
    p.draw_line((100,40),(100,115))
    p.draw_line((180,160),(180,220))
    result=audit(p,candidate_region_bbox=(90,20,190,250))
    assert result["source_native_multiple_parallel_axes_present"]
    assert result["cross_axis_original_ink_source_ids"]==[]
    assert not result["source_stepped_structural_wall_identity_authenticated"]
    doc.close()


def test_misleading_fixture_cross_hatch_does_not_mint_room_area():
    doc=fitz.open()
    p=doc.new_page(width=300,height=300)
    for x in (120,160):
        p.draw_line((x,40),(x,180))
    p.draw_line((120,90),(160,90))
    result=audit(p,candidate_region_bbox=(110,30,170,200))
    assert result["source_native_multiple_parallel_axes_present"]
    assert not result["partition_closes_independent_rooms"]
    assert result["new_floor_finish_quantities"]==0
    doc.close()


def test_invalid_bounds_length_or_source_cap_are_explicit():
    doc=fitz.open()
    p=doc.new_page()
    p.draw_line((1,1),(1,100))
    with pytest.raises(ValueError,match="native_region"):
        audit(p,candidate_region_bbox=(0,0,0,10))
    with pytest.raises(ValueError,match="native_source_length"):
        audit(p,candidate_region_bbox=(0,0,200,200),min_source_stroke_length_pt=0)
    with pytest.raises(ValueError,match="source_stroke_cap"):
        audit(p,candidate_region_bbox=(0,0,200,200),max_native_strokes=0)
    result=audit(p,candidate_region_bbox=(0,0,200,200),max_native_strokes=1)
    assert result["source_physical_room_ring_complete"] is False
    doc.close()


def test_original_a503_m_amb_f_amb_divider_retains_multiple_competing_faces():
    source=PDF.read_bytes()
    assert hashlib.sha256(source).hexdigest()==SHA
    with fitz.open(stream=source,filetype="pdf") as doc:
        page=doc[26]
        r=audit(page,candidate_region_bbox=(330,1720,420,2150))
        assert r["status"]=="source_native_stepped_wall_and_recess_candidates_only"
        assert r["original_source_stroke_scope_complete"]
        assert r["source_native_multiple_parallel_axes_present"]
        names={w["original_source_primitive_id"]
               for w in r["original_axis_aligned_ink_candidates"]}
        assert {"d2078i0","d2106i0","d2079i0"} <= names
        xs=[x["source_vertical_axis_pdf_pt"] for x in r["competing_original_vertical_axes"]]
        assert any(abs(x-342.72)<.01 for x in xs)
        assert any(abs(x-407.76)<.01 for x in xs)
        assert len(r["cross_axis_original_ink_source_ids"])>=2
        assert not r["source_physical_room_ring_complete"]
        assert not r["source_stepped_structural_wall_identity_authenticated"]
        assert r["new_published_room_areas"]==r["new_floor_finish_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA
