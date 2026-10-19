"""Original FREEZER D18/D19 right face does not borrow D17 door dimensions."""
from __future__ import annotations
import hashlib
from pathlib import Path

import fitz
import pytest
from tools.diag_gpt2_original_right_wall_door_schedule_candidates import (
    audit_original_wall_side_door_code_source_candidates as audit,
)

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _sample():
    doc=fitz.open()
    p=doc.new_page()
    p.insert_text((50,40),"D18")
    p.insert_text((50,70),"D19")
    p.insert_text((50,110),"D20")
    p=doc.new_page()
    p.insert_text((20,20),"D18 FREEZER AS PER MANUFACTURER")
    p.insert_text((20,40),"D19 FREEZER AS PER MANUFACTURER")
    p.insert_text((20,60),"D20 COLD ROOM AS PER MANUFACTURER")
    raw=doc.tobytes()
    doc.close()
    return raw


def _run(source,**override):
    kw={
        "expected_sha256":hashlib.sha256(source).hexdigest(),
        "plan_page_1_based":1,
        "schedule_page_1_based":2,
        "candidate_right_face_x_pdf_pts":50.,
        "candidate_wall_y_span_pdf_pts":(20.,90.),
        "explicit_door_code_schedule_blocks":(
            ("D18",0),("D19",1),("D20",2)
        ),
    }
    kw.update(override)
    return audit(source,**kw)


def test_distinct_door_sources_at_selected_wall_vs_outside_are_unissued():
    result=_run(_sample())
    a,b,c=result["all_explicit_door_schedule_candidates"]
    assert len(a["original_plan_same_code_at_candidate_right_face"])==1
    assert len(b["original_plan_same_code_at_candidate_right_face"])==1
    assert c["original_plan_same_code_at_candidate_right_face"]==()
    assert len(c["original_plan_same_code_outside_candidate_right_face"])==1
    assert all(x["door_area_or_count_authority_proven"] is False for x in (a,b,c))
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("bad",[
    {"expected_sha256":"0"*64},
    {"explicit_door_code_schedule_blocks":(("D18",0),("D19",0))},
    {"explicit_door_code_schedule_blocks":(("D18",1),)},
    {"candidate_wall_y_span_pdf_pts":(20,20)},
    {"candidate_right_face_x_pdf_pts":float("nan")},
])
def test_forged_source_or_schedule_row_does_not_issue_doors(bad):
    with pytest.raises(ValueError):
        _run(_sample(),**bad)


@pytest.mark.skipif(not SOURCE.exists(),reason="private source not available")
def test_original_freezer_d18_d19_are_right_side_and_d20_elsewhere():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(
        raw,expected_sha256=SHA,
        plan_page_1_based=7,schedule_page_1_based=28,
        candidate_right_face_x_pdf_pts=588.24,
        candidate_wall_y_span_pdf_pts=(1179.44,1275.92),
        explicit_door_code_schedule_blocks=(
            ("D18",115),("D19",116),("D20",117)),
    )
    first,second,third=result["all_explicit_door_schedule_candidates"]
    assert first["original_plan_same_code_at_candidate_right_face"][0][
        "native_source_word_address"]==(7,186,0,0)
    assert second["original_plan_same_code_at_candidate_right_face"][0][
        "native_source_word_address"]==(7,186,1,0)
    assert third["original_plan_same_code_at_candidate_right_face"]==()
    assert "MANUFACTURER" in first["all_original_schedule_row_text"]
    assert "MANUFACTURER" in second["all_original_schedule_row_text"]
    assert result["new_firm_quantities"]==0
