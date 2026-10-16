"""Exact native source-line registrations are evidence, not room identity."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_original_crosssheet_native_ink_registration_shadow import (
    audit_original_cross_sheet_source_translation as audit,
    _translation_pairs,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
BBOX=(100.,450.,900.,1955.)


def test_original_p7_p11_many_source_ink_witnesses_and_competing_transforms():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as d:
        result=audit(d[6],d[10],native_candidate_bbox_a=BBOX,
                     native_candidate_bbox_b=BBOX)
        assert result["source_candidate_universe_complete"]
        assert result["source_a_native_line_count"]>200
        assert result["source_b_native_line_count"]>200
        transforms=result["all_competing_translation_groups"]
        assert transforms
        assert transforms[0]["original_source_translation_pdf_pts"]==[78.,0.]
        assert transforms[0]["original_source_pair_count"]>=100
        assert transforms[0]["locally_unique_source_ink_pair_count"]>=100
        assert any(t["original_source_translation_pdf_pts"]==[83.76,0.]
                   for t in transforms)
        originals={
            (r["source_original_a_path_item_id"],r["source_original_b_path_item_id"])
            for r in transforms[0]["all_original_candidate_pairs"]
        }
        assert ("d52236i0","d2654i0") in originals
        assert ("d52240i0","d2658i0") in originals
        assert ("d52158i0","d2617i0") in originals
        assert not transforms[0]["global_source_registration_authority_granted"]
        assert not transforms[0]["page7_to_page11_physical_room_join_granted"]
        assert result["new_floor_finish_quantities"]==result["new_quantities"]==0
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_two_independent_synthetic_pages_prove_exact_translation_without_words():
    doc=fitz.open()
    p=doc.new_page(width=300,height=300)
    for (a,b) in [((20,40),(20,150)),((30,40),(140,40)),
                  ((20,150),(140,150)),((140,40),(140,150))]:
        p.draw_line(a,b,color=(0,0,0),width=.48)
    doc.new_page(width=300,height=300)
    q=doc[1]
    for (a,b) in [((98,40),(98,150)),((108,40),(218,40)),
                  ((98,150),(218,150)),((218,40),(218,150))]:
        q.draw_line(a,b,color=(0,0,0),width=.48)
    r=audit(doc[0],q,native_candidate_bbox_a=(0,0,300,300),
            native_candidate_bbox_b=(0,0,300,300))
    assert any(z["original_source_translation_pdf_pts"]==[78.,0.]
               and z["original_source_pair_count"]==4
               for z in r["all_competing_translation_groups"])
    assert not r["newly_authenticated_room_matches"]
    doc.close()


def test_reverse_native_strokes_remain_equal_when_matching_exact_endpoints():
    doc=fitz.open()
    doc.new_page(width=300,height=300)
    p=doc[0]
    p.draw_line((20,50),(20,120))
    doc.new_page(width=300,height=300)
    q=doc[1]
    q.draw_line((98,120),(98,50))
    r=audit(doc[0],q,native_candidate_bbox_a=(0,0,300,300),
            native_candidate_bbox_b=(0,0,300,300))
    assert any(g["original_source_translation_pdf_pts"]==[78.,0.]
               for g in r["all_competing_translation_groups"])
    doc.close()


def test_repeated_ink_origins_keep_both_competing_source_parents():
    doc=fitz.open()
    doc.new_page(width=300,height=300)
    p=doc[0]
    p.draw_line((20,50),(20,120))
    p.draw_line((20,50),(20,120))
    doc.new_page(width=300,height=300)
    q=doc[1]
    q.draw_line((98,50),(98,120))
    r=audit(doc[0],q,native_candidate_bbox_a=(0,0,300,300),
            native_candidate_bbox_b=(0,0,300,300))
    group=next(g for g in r["all_competing_translation_groups"]
               if g["original_source_translation_pdf_pts"]==[78.,0.])
    assert group["original_source_pair_count"]==2
    assert group["locally_unique_source_ink_pair_count"]==0
    assert not group["global_source_registration_authority_granted"]
    doc.close()


def test_mismatched_stroke_style_or_length_is_not_crosssheet_match():
    doc=fitz.open()
    doc.new_page(width=300,height=300)
    p=doc[0]
    p.draw_line((20,50),(20,120),color=(0,0,0),width=.48)
    doc.new_page(width=300,height=300)
    q=doc[1]
    q.draw_line((98,50),(98,120),color=(.5,.5,.5),width=.24)
    r=audit(doc[0],q,native_candidate_bbox_a=(0,0,300,300),
            native_candidate_bbox_b=(0,0,300,300))
    assert r["all_competing_translation_groups"]==[]
    doc.close()


def test_bbox_and_pair_caps_fail_closed_without_partial_election():
    doc=fitz.open()
    doc.new_page(width=300,height=300)
    p=doc[0]
    for y in (20,40,60):
        p.draw_line((20,y),(120,y))
    doc.new_page(width=300,height=300)
    q=doc[1]
    for y in (20,40,60):
        q.draw_line((98,y),(198,y))
    r=audit(doc[0],q,native_candidate_bbox_a=(0,0,300,300),
            native_candidate_bbox_b=(0,0,300,300),max_selected_lines=1)
    assert r["status"]=="original_source_scope_cap_exceeded"
    r=audit(doc[0],q,native_candidate_bbox_a=(0,0,300,300),
            native_candidate_bbox_b=(0,0,300,300),max_matched_pairs=1)
    assert r["status"]=="original_source_pair_scope_cap_exceeded"
    with pytest.raises(ValueError):
        audit(p,q,native_candidate_bbox_a=(0,0,0,300),
              native_candidate_bbox_b=(0,0,300,300))
    doc.close()
