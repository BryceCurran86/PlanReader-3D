"""Original LAUNDRY/D10/AIRLOCK source wall gap, not a finished threshold."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_two_room_door_ink_gap_shadow import (
    audit_original_two_room_source_wall_door_gap as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _synthetic(*, closed_wall=False, missing_door=False,
               schedule_room="LAUNDRY"):
    doc=fitz.open()
    p=doc.new_page(width=320,height=240)
    p.draw_line((10,100),(70 if not closed_wall else 170,100),
                color=(0,0,0),width=.48)
    p.draw_line((130,100),(260,100),
                color=(0,0,0),width=.48)
    p.insert_text((25,70),"LAUNDRY")
    p.insert_text((25,155),"AIRLOCK")
    if not missing_door:
        p.insert_text((90,103),"D10")
    labels={}
    for w in p.get_text("words",sort=False):
        if w[4] in ("LAUNDRY","AIRLOCK"):
            labels[w[4]]=(w[5],w[6],w[7])
    schedule=doc.new_page(width=320,height=240)
    schedule.insert_text((20,35),
                         "D10\n"+schedule_room+"\nSINGLE SWING\n920\n2040\n40")
    data=doc.tobytes()
    doc.close()
    return data,(
        ("LAUNDRY",labels["LAUNDRY"]),
        ("AIRLOCK",labels["AIRLOCK"]),
    )


def _run(raw,labels,**changes):
    args={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "original_plan_page_1_based":1,
        "original_door_schedule_page_1_based":2,
        "room_word_receipts":labels,
        "original_left_wall_ink_id":"d0i0",
        "original_right_wall_ink_id":"d1i0",
        "door_code":"D10",
        "original_schedule_native_block":0,
        "original_doorway_wall_axis_y_pdf_pts":100.,
    }
    args.update(changes)
    return audit(raw,**args)


def test_genuine_two_original_rooms_and_a_door_gap_are_only_source_candidates():
    raw,labels=_synthetic()
    result=_run(raw,labels)
    assert result["status"]=="two_original_room_labels_and_door_wall_gap_source_candidate"
    assert result["original_source_gap_pdf_pts"]==(
        (70.,100.),(130.,100.))
    assert [r["original_source_side_of_unproven_wall"] for r
            in result["original_source_room_label_candidates"]]==[
                "before_wall_axis","after_wall_axis"]
    assert result["original_structural_wall_or_door_host_authenticated"] is False
    assert result["original_finished_wall_face_or_threshold_authenticated"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("scenario",[
    "closed_wall","missing_door","wrong_schedule_room","foreign_sha",
    "same_wall","wrong_door_code","labels_same_source",
    "wrong_wall_axis","missing_wall",
])
def test_foreign_or_guessed_laundry_airlock_separator_cannot_publish(scenario):
    raw,labels=_synthetic(
        closed_wall=scenario=="closed_wall",
        missing_door=scenario=="missing_door",
        schedule_room="KITCHEN" if scenario=="wrong_schedule_room"
                          else "LAUNDRY",
    )
    args={}
    if scenario=="foreign_sha":
        args["expected_sha256"]="0"*64
    if scenario=="same_wall":
        args["original_right_wall_ink_id"]="d0i0"
    if scenario=="wrong_door_code":
        args["door_code"]="D14"
    if scenario=="labels_same_source":
        args["room_word_receipts"]=(labels[0],labels[0])
    if scenario=="wrong_wall_axis":
        args["original_doorway_wall_axis_y_pdf_pts"]=102.
    if scenario=="missing_wall":
        args["original_left_wall_ink_id"]="d900i0"
    with pytest.raises((ValueError, IndexError)):
        _run(raw,labels,**args)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original PDF unavailable")
def test_original_maryborough_laundry_airlock_d10_wall_stubs_and_native_mark():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(
        raw,expected_sha256=SHA,
        original_plan_page_1_based=7,
        original_door_schedule_page_1_based=28,
        room_word_receipts=(
            ("LAUNDRY",(134,0,0)),
            ("AIRLOCK",(153,0,0)),
        ),
        original_left_wall_ink_id="d84327i0",
        original_right_wall_ink_id="d69328i0",
        door_code="D10",
        original_schedule_native_block=107,
        original_doorway_wall_axis_y_pdf_pts=1683.44,
    )
    assert result["original_source_gap_pdf_pts"]==(
        (301.2,1683.44),(357.84,1683.44))
    assert result["source_door_mark_on_original_ink_gap"][
        "original_native_word_address"]==(7,178,0,0)
    assert result["source_independent_door_schedule"][
        "original_schedule_row_lines"][1]==("LAUNDRY",)
    assert result["original_structural_wall_or_door_host_authenticated"] is False
    assert result["original_source_metric_scale_authenticated"] is False
    assert result["new_firm_quantities"]==0
