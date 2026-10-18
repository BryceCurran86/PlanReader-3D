"""Pure synthetic native arrowhead-chain tests, no owner PDF required."""
import hashlib

import fitz
import pytest

from tools.diag_gpt2_original_native_dimension_chain_shadow import (
    audit_original_native_orthogonal_dimension_chains as audit,
)


def _make_source():
    doc=fitz.open()
    page=doc.new_page(width=380,height=300)
    # Six independent axis strokes; the short strokes deliberately overrun.
    for a,b in (
        ((40,14),(40,35)), ((40,35),(40,150)),
        ((40,150),(40,174)),
        ((14,215),(36,215)), ((36,215),(160,215)),
        ((160,215),(184,215)),
    ):
        page.draw_line(a,b,color=(0,0,0),width=.48)
    points_v=(20,35,150,168)
    points_h=(20,36,160,178)
    tip_ids={}
    for role,points,axis in (("vertical",points_v,"v"),
                             ("horizontal",points_h,"h")):
        for index,pt in enumerate(points):
            name=f"{role}_{index}"
            before=len(page.get_drawings())
            if axis=="v":
                end=(40,pt)
                for change in (2,-2):
                    page.draw_line(end,(40+change,pt+change),
                                   color=(0,0,0),width=.96)
            else:
                end=(pt,215)
                for change in (2,-2):
                    page.draw_line(end,(pt+change,215+change),
                                   color=(0,0,0),width=.96)
            tip_ids[name]=(f"d{before}i0",f"d{before+1}i0")
    for text,point in (
        ("50",(25,29)),("200",(25,97)),("60",(25,162)),
        ("70",(23,209)),("300",(93,209)),("80",(166,209)),
    ):
        page.insert_text(point,text,fontsize=7)
    words={word[4]:tuple(word[5:8]) for word in page.get_text("words")}
    assert len(words)==6
    vertical={}
    horizontal={}
    for axis,line0,labels,tips,out in (
        ("vertical",0,("50","200","60"),"vertical",vertical),
        ("horizontal",3,("70","300","80"),"horizontal",horizontal),
    ):
        for i,role in enumerate(("short_before","main","short_after")):
            out[role]={
                "line_id":f"d{line0+i}i0",
                "word_address":words[labels[i]],
                "first_ticks":tip_ids[f"{tips}_{i}"],
                "last_ticks":tip_ids[f"{tips}_{i+1}"],
            }
    raw=doc.tobytes()
    doc.close()
    return raw,vertical,horizontal


def test_each_native_wall_note_uses_printed_arrows_not_full_stroke_length():
    raw,vertical,horizontal=_make_source()
    result=audit(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),
                 page_1_based=1,vertical=vertical,horizontal=horizontal)
    assert result["status"]=="source_orthogonal_native_figured_chains_candidate_only"
    v=result["native_printed_dimension_chains"]["vertical"]
    h=result["native_printed_dimension_chains"]["horizontal"]
    assert v["original_dimension_chain_mm"]==[50,200,60]
    assert h["original_dimension_chain_mm"]==[70,300,80]
    assert v["original_arrowhead_connected_chain_pdf_pts"]==[
        20.,35.,150.,168.]
    assert h["original_arrowhead_connected_chain_pdf_pts"]==[
        20.,36.,160.,178.]
    assert v["original_source_records"]["short_before"][
        "source_original_line_overhangs_pdf_pts"]==[6.,0.]
    assert not result["source_finished_net_area_m2"]
    assert result["new_firm_quantities"]==0


def test_wrong_arrows_or_shared_source_swaps_do_not_repair_a_chain():
    raw,vertical,horizontal=_make_source()
    wrong={**vertical["short_before"],
           "last_ticks":vertical["short_after"]["last_ticks"]}
    with pytest.raises(ValueError,match="original_dimension_tip_outside_own_source_line"):
        audit(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),
              page_1_based=1,vertical={**vertical,"short_before":wrong},
              horizontal=horizontal)
    # Original mutation is a top-level source trust failure.
    with pytest.raises(ValueError,match="original_dimension_chain_source_sha_mismatch"):
        audit(raw+b"rewritten",expected_sha256=hashlib.sha256(raw).hexdigest(),
              page_1_based=1,vertical=vertical,horizontal=horizontal)
