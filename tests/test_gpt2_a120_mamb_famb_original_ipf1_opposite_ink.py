"""Original M-AMB and F-AMB IPF1 RCP words: source, not FIRM ceiling."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_rcp_two_amenity_ipf1_source_shadow import (
    audit_original_rcp_two_rooms_opposed_mark_words as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
REAL=(
    ("M-AMB",(29,0,0),(85,5,0)),
    ("F-AMB",(36,0,0),(87,0,0)),
)


def _source():
    doc=fitz.open()
    p=doc.new_page(width=350,height=230)
    p.draw_line((140,30),(140,65),color=(0,0,0),width=.48)
    p.draw_line((140,80),(140,175),color=(0,0,0),width=.48)
    p.insert_text((25,140),"M-AMB")
    p.insert_text((205,140),"F-AMB")
    p.insert_text((30,60),"IPF1")
    p.insert_text((210,60),"IPF1")
    p.insert_text((230,190),"IPF1")  # a competing schedule source word
    labels={}
    marks=[]
    for w in p.get_text("words",sort=False):
        address=(w[5],w[6],w[7])
        if w[4] in ("M-AMB","F-AMB"):
            labels[w[4]]=address
        elif w[4]=="IPF1":
            marks.append((w[0],address))
    marks.sort()
    data=doc.tobytes()
    doc.close()
    return data,(
        ("M-AMB",labels["M-AMB"],marks[0][1]),
        ("F-AMB",labels["F-AMB"],marks[1][1]),
    )


def _run(data,receipts,**changes):
    fields={
        "expected_sha256":hashlib.sha256(data).hexdigest(),
        "rcp_page_1_based":1,
        "source_room_mark_receipts":receipts,
        "original_source_partition_ink_path_ids":("d0i0","d1i0"),
        "expected_finish_code":"IPF1",
    }
    fields.update(changes)
    return audit(data,**fields)


def test_two_independent_ipf1_room_words_retained_with_competing_schedule_mark():
    raw,receipts=_source()
    result=_run(raw,receipts)
    assert result["status"]=="two_original_printed_rcp_room_finish_candidates_opposite_ink"
    assert len(result["all_original_same_code_native_words_including_schedule"])==3
    assert result["source_original_partition_ink_intervals_pdf_pts"]==(
        (30.,65.),(80.,175.))
    assert result["source_source_original_partition_closed_wall_verified"] is False
    assert result["source_rcp_viewport_ownership_authenticated"] is False
    assert result["source_rcp_physical_ceiling_zone_geometry_authenticated"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("bad",[
    "forged_sha","same_mark","same_room","swapped_marks",
    "foreign_partition_path","one_partition_path","wrong_code",
])
def test_source_ink_or_lexical_reuse_cannot_create_false_rcp_zone(bad):
    raw,receipts=_source()
    args={}
    a,b=receipts
    if bad=="forged_sha":
        args["expected_sha256"]="0"*64
    if bad=="same_mark":
        args["source_room_mark_receipts"]=(a,(b[0],b[1],a[2]))
    if bad=="same_room":
        args["source_room_mark_receipts"]=(a,a)
    if bad=="swapped_marks":
        args["source_room_mark_receipts"]=(
            (a[0],a[1],b[2]),(b[0],b[1],a[2]))
    if bad=="foreign_partition_path":
        args["original_source_partition_ink_path_ids"]=("d0i0","d999i0")
    if bad=="one_partition_path":
        args["original_source_partition_ink_path_ids"]=("d0i0","d0i0")
    if bad=="wrong_code":
        args["expected_finish_code"]="FT3"
    with pytest.raises((ValueError,IndexError)):
        _run(raw,receipts,**args)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original RCP PDF missing")
def test_original_amenities_a120_has_separate_ambulant_ipf1_source_marks():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(
        raw,expected_sha256=SHA,rcp_page_1_based=9,
        source_room_mark_receipts=REAL,
        original_source_partition_ink_path_ids=("d6501i0","d6460i0"),
        expected_finish_code="IPF1",
    )
    assert result["status"]=="two_original_printed_rcp_room_finish_candidates_opposite_ink"
    assert result["source_original_partition_ink_axis_x_pdf_pts"]==642.
    assert result["source_original_partition_ink_intervals_pdf_pts"]==(
        (1436.48,1496.24),(1502.,1584.56))
    m,f=result["source_original_room_finish_receipts"]
    assert m["original_room_word_address"]==(9,29,0,0)
    assert f["original_room_word_address"]==(9,36,0,0)
    assert m["original_finish_word_address"]==(9,85,5,0)
    assert f["original_finish_word_address"]==(9,87,0,0)
    assert m["source_original_ink_side"]=="left"
    assert f["source_original_ink_side"]=="right"
    assert len(result["all_original_same_code_native_words_including_schedule"])==12
    assert result["source_material_definition_and_occurrence_authenticated"] is False
    assert result["new_firm_quantities"]==0
