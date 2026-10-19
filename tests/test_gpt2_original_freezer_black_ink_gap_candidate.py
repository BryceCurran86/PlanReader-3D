"""Source-native FREEZER ink ring: candidate geometry, not a physical FIRM room."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_open_room_black_ink_ring_shadow import (
    audit_original_room_wall_ink_with_single_door_gap as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
FREEZER=(368.64,1179.44,588.24,1275.92)
SIDES={
    "left":("d62496i0",),
    "right":("d62609i0","d62621i0","d69324i0"),
    "bottom":("d62492i0",),
    "top":("d53738i0","d53736i0"),
}


def _synthetic():
    pdf=fitz.open()
    p=pdf.new_page(width=250,height=250)
    strokes=(
        ((20,20),(20,110)),
        ((140,20),(140,80)),
        ((140,80),(140,110)),
        ((20,110),(140,110)),
        ((20,20),(70,20)),
        ((90,20),(140,20)),
    )
    for start,end in strokes:
        p.draw_line(start,end,color=(0,0,0),width=.48)
    data=pdf.tobytes()
    pdf.close()
    return data


def _run(data,**kwargs):
    args={
        "expected_sha256":hashlib.sha256(data).hexdigest(),
        "page_1_based":1,
        "candidate_source_room_bbox_pdf_pts":(20.,20.,140.,110.),
        "original_side_source_path_ids":{
            "left":("d0i0",),
            "right":("d1i0","d2i0"),
            "bottom":("d3i0",),
            "top":("d4i0","d5i0"),
        },
    }
    args.update(kwargs)
    return audit(data,**args)


def test_real_source_black_wall_ink_supports_one_virtual_door_gap_not_wall():
    out=_run(_synthetic())
    assert out["status"]=="original_black_ink_room_ring_with_virtual_door_gap_candidate"
    assert out["original_source_top_ink_door_gap_pdf_pts"]==(
        (70.,20.),(90.,20.)
    )
    assert out["source_side_evidence"]["right"][
        "original_source_ink_intervals_pdf_pts"]==((20.,110.),)
    assert out["source_doorway_is_structural_wall"] is False
    assert out["source_doorway_finish_threshold_authenticated"] is False
    assert out["room_structural_wall_role_authenticated"] is False
    assert out["new_firm_quantities"]==0


def test_missing_one_wall_segment_must_abstain_not_connect_from_label():
    data=_synthetic()
    sides={
        "left":("d0i0",),
        "right":("d2i0",),
        "bottom":("d3i0",),
        "top":("d4i0","d5i0"),
    }
    row=_run(data,original_side_source_path_ids=sides)
    assert row["first_unclosed_gate"]=="original_black_source_perimeter_side_unclosed"
    assert row["new_firm_quantities"]==0


@pytest.mark.parametrize("bad",[
    {"expected_sha256":"0"*64},
    {"page_1_based":0},
    {"candidate_source_room_bbox_pdf_pts":(20,20,20,110)},
    {"original_side_source_path_ids":{"left":("d0i0",)}},
    {"original_side_source_path_ids":{
        "left":("d0i0",),"right":("d1i0","d2i0"),
        "bottom":("d3i0",),"top":("d3i0","d5i0")
    }},
    {"max_native_paths":1},
])
def test_bad_or_foreign_native_source_identity_never_grants_room(bad):
    with pytest.raises(ValueError):
        _run(_synthetic(),**bad)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original not provisioned")
def test_original_freezer_source_ring_retains_all_painted_walls_and_d17_opening():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    row=audit(
        raw,expected_sha256=SHA,page_1_based=7,
        candidate_source_room_bbox_pdf_pts=FREEZER,
        original_side_source_path_ids=SIDES,
    )
    assert row["status"]=="original_black_ink_room_ring_with_virtual_door_gap_candidate"
    assert row["original_source_top_ink_door_gap_pdf_pts"]==(
        (476.16,1179.44),(521.52,1179.44)
    )
    assert row["source_side_evidence"]["right"][
        "original_source_ink_intervals_pdf_pts"]==(
        (1179.44,1275.92),
    )
    assert row["original_room_source_candidate_only"] is True
    assert row["new_firm_quantities"]==0
