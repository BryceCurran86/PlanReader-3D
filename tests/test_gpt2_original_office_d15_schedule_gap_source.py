"""D15 on an OFFICE painted original gap is not a measured floor threshold."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_room_door_schedule_gap_shadow import (
    audit_original_room_ink_door_schedule_gap_candidate as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
ORIGINAL_SIDES={
    "left":("d52239i0","d2657i0"),
    "right":("d66220i0","d3062i0"),
    "bottom":("d53725i0","d2931i0"),
    "top_partial":("d52625i0","d2845i0"),
}
SIDES={
    role:(f"d{i}i0",f"d{i}i0")
    for i,role in enumerate(("left","right","bottom","top_partial"))
}


def _synthetic(*,two_inside=False,only_elsewhere=False):
    doc=fitz.open()
    for offset in (0.,78.):
        page=doc.new_page(width=340,height=220)
        for a,b in (
            ((20,30),(20,150)),
            ((130,30),(130,150)),
            ((20,150),(129.52,150)),
            ((65,30),(129.52,30)),
        ):
            page.draw_line((a[0]+offset,a[1]),
                           (b[0]+offset,b[1]),
                           color=(0,0,0),width=.48)
        if offset == 0.:
            if not only_elsewhere:
                page.insert_text((41,31),"D15",fontsize=10)
            if two_inside:
                page.insert_text((21,32),"D15",fontsize=10)
            page.insert_text((230,80),"D15",fontsize=10)
    page=doc.new_page(width=340,height=220)
    page.insert_text((20,40),"D15 OFFICE SINGLE SWING 920 2040 40")
    raw=doc.tobytes()
    doc.close()
    return raw


def _run(raw,**changes):
    opts={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "floor_page_1_based":1,
        "finish_page_1_based":2,
        "original_side_pairs":SIDES,
        "source_translation_pdf_pts":(78.,0.),
        "door_schedule_page_1_based":3,
        "door_schedule_native_block":0,
        "source_door_code":"D15",
    }
    opts.update(changes)
    return audit(raw,**opts)


def test_original_door_mark_exact_gap_and_independent_schedule_source():
    row=_run(_synthetic())
    assert row["status"]=="one_original_room_door_word_on_painted_gap_candidate"
    assert len(row["source_original_plan_door_word_candidates_crossing_gap"])==1
    assert len(row["source_original_same_code_door_words_elsewhere"])==1
    assert row["source_door_schedule_leaf_width_not_floor_threshold_width"] is True
    assert row["source_finished_door_threshold_authenticated"] is False
    assert row["source_original_finish_floor_area_issued"] is False
    assert row["new_firm_quantities"]==0


@pytest.mark.parametrize("extra",[
    {"two_inside":True},
    {"only_elsewhere":True},
])
def test_two_or_no_printed_door_marks_never_elect_gap_owner(extra):
    row=_run(_synthetic(**extra))
    assert row["status"]=="original_room_door_gap_schedule_source_abstained"
    assert row["first_unclosed_gate"]=="original_door_word_not_unique_on_this_ink_gap"
    assert row["new_firm_quantities"]==0


@pytest.mark.parametrize("changed",[
    {"expected_sha256":"0"*64},
    {"source_translation_pdf_pts":(77.,0.)},
    {"door_schedule_native_block":1},
    {"source_door_code":"D17"},
    {"original_side_pairs":{
        "left":("d0i0","d0i0"),
        "right":("d0i0","d1i0"),
        "bottom":("d2i0","d2i0"),
        "top_partial":("d3i0","d3i0"),
    }},
])
def test_wrong_original_schedule_or_wall_source_never_authenticates_door(changed):
    with pytest.raises(ValueError):
        _run(_synthetic(),**changed)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original not provisioned")
def test_original_office_d15_p7_source_gap_and_p28_a600_schedule_are_independent():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    row=audit(
        raw,expected_sha256=SHA,
        floor_page_1_based=7,finish_page_1_based=11,
        original_side_pairs=ORIGINAL_SIDES,
        source_translation_pdf_pts=(78.,0.),
        door_schedule_page_1_based=28,
        door_schedule_native_block=112,
        source_door_code="D15",
    )
    assert row["status"]=="one_original_room_door_word_on_painted_gap_candidate"
    assert row["source_original_plan_door_word_candidates_crossing_gap"][0][
        "original_native_word_address"]==(7,183,0,0)
    assert row["source_door_gap_original_pdf_pts"]==(
        (173.52,1383.2),(233.76,1383.2))
    schedule=row["original_door_schedule_source"]["original_schedule_row_lines"]
    assert ("OFFICE",) in schedule
    assert ("SINGLE","SWING") in schedule
    assert ("920",) in schedule
    assert row["source_door_leaf_to_wall_gap_metric_correspondence_proven"] is False
    assert row["source_finished_door_threshold_authenticated"] is False
    assert row["new_firm_quantities"]==0
