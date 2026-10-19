"""M-AMB/D12 and F-AMB/D11 are distinct ORIGINAL source door candidates."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_ambulant_separate_door_ink_shadow import (
    audit_original_adjacent_room_door_entrances as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
ORIGINAL_PAIRS=(
    ("M-AMB",(26,0,0),"D12",109),
    ("F-AMB",(39,0,0),"D11",108),
)


def _source(*,remove_left_door=False,right_schedule_room="F-AMB"):
    pdf=fitz.open()
    plan=pdf.new_page(width=320,height=240)
    plan.draw_line((120,30),(140,30),color=(0,0,0),width=.48)
    plan.insert_text((60,95),"M-AMB")
    plan.insert_text((205,95),"F-AMB")
    if not remove_left_door:
        plan.insert_text((65,34),"D12")
    plan.insert_text((210,34),"D11")
    native=plan.get_text("words",sort=False)
    labels={
        str(w[4]):(int(w[5]),int(w[6]),int(w[7]))
        for w in native if str(w[4]) in {"M-AMB","F-AMB"}
    }
    schedule=pdf.new_page(width=320,height=300)
    schedule.insert_text((20,40),"D12\nM-AMB\nSINGLE SWING\n820\n2040\n40")
    schedule.insert_text((20,155),
                         "D11\n"+right_schedule_room+"\nSINGLE SWING\n820\n2040\n40")
    data=pdf.tobytes()
    pdf.close()
    return data,(
        ("M-AMB",labels["M-AMB"],"D12",0),
        ("F-AMB",labels["F-AMB"],"D11",1),
    )


def _run(data,pairs,**changes):
    kwargs={
        "expected_sha256":hashlib.sha256(data).hexdigest(),
        "plan_page_1_based":1,
        "schedule_page_1_based":2,
        "original_room_door_word_pairs":pairs,
        "original_corridor_separating_ink_path_id":"d0i0",
        "source_corridor_axis_y_pdf_pts":30.,
    }
    kwargs.update(changes)
    return audit(data,**kwargs)


def test_distinct_ambulant_door_plan_marks_and_schedule_roles_not_cubicle_area():
    raw,pairs=_source()
    result=_run(raw,pairs)
    assert result["status"]=="two_distinct_original_cubicle_door_source_candidates_only"
    rows=result["all_original_distinct_room_door_candidates"]
    assert {x["source_original_door_code_untrusted"] for x in rows}=={"D11","D12"}
    assert rows[0]["original_schedule_source"]["original_schedule_row_lines"][1]==(
        "M-AMB",)
    assert rows[1]["original_schedule_source"]["original_schedule_row_lines"][1]==(
        "F-AMB",)
    assert result["original_complete_structural_cubicle_wall_ring_authenticated"] is False
    assert result["original_finished_face_or_door_threshold_authenticated"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("mutant",[
    "foreign_sha",
    "aliased_room",
    "aliased_door",
    "wrong_schedule_room",
    "missing_door",
    "unpainted_ink",
    "foreign_source_path",
])
def test_false_original_native_door_or_room_provenance_abstains(mutant):
    data,pairs=_source(
        remove_left_door=mutant=="missing_door",
        right_schedule_room="COLD ROOM" if mutant=="wrong_schedule_room"
                            else "F-AMB",
    )
    pairs=list(pairs)
    overrides={}
    if mutant=="foreign_sha":
        overrides["expected_sha256"]="0"*64
    elif mutant=="aliased_room":
        pairs[1]=("F-AMB",pairs[0][1],"D11",1)
    elif mutant=="aliased_door":
        pairs[1]=("F-AMB",pairs[1][1],"D12",1)
    elif mutant=="unpainted_ink":
        overrides["source_corridor_axis_y_pdf_pts"]=31.
    elif mutant=="foreign_source_path":
        overrides["original_corridor_separating_ink_path_id"]="d1000i0"
    with pytest.raises((ValueError,IndexError,KeyError)):
        _run(data,tuple(pairs),**overrides)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original PDF unavailable")
def test_original_maryborough_ambulant_labels_and_d11_d12_on_separate_entrances():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(
        raw,expected_sha256=SHA,
        plan_page_1_based=7,schedule_page_1_based=28,
        original_room_door_word_pairs=ORIGINAL_PAIRS,
        original_corridor_separating_ink_path_id="d52636i0",
        source_corridor_axis_y_pdf_pts=1383.2,
    )
    assert result["status"]=="two_distinct_original_cubicle_door_source_candidates_only"
    assert result["original_corridor_ink_endpoints_pdf_pts"]==[
        (510.48,1383.2),(535.92,1383.2)]
    left,right=result["all_original_distinct_room_door_candidates"]
    assert left["original_room_word_address"]==(7,26,0,0)
    assert right["original_room_word_address"]==(7,39,0,0)
    assert left["original_plan_door_word_on_corridor"][
        "original_native_word_address"]==(7,180,0,0)
    assert right["original_plan_door_word_on_corridor"][
        "original_native_word_address"]==(7,179,0,0)
    assert result["source_canonical_room_publisher_authority_granted"] is False
    assert result["new_firm_quantities"]==0
