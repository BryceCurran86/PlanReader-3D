"""Printed FREEZER and D17 source words do not by themselves issue a room."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_room_door_word_candidates_shadow import (
    audit_original_room_ring_word_candidates as audit,
)
from tools.diag_gpt2_original_open_room_black_ink_ring_shadow import (
    audit_original_room_wall_ink_with_single_door_gap as ring_census,
)
from tests.test_gpt2_original_freezer_black_ink_gap_candidate import (
    _synthetic as plain_source, FREEZER, SIDES
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _source(*,dupe_door=False,missing_door=False):
    d=fitz.open(stream=plain_source(),filetype="pdf")
    page=d[0]
    page.insert_text((40,55),"FREEZER",fontsize=10)
    page.insert_text((170,170),"FREEZER",fontsize=10)
    if not missing_door:
        page.insert_text((74,22),"D17",fontsize=10)
    if dupe_door:
        page.insert_text((74,19),"D17",fontsize=10)
    raw=d.tobytes()
    d.close()
    return raw


def _run(raw):
    sha=hashlib.sha256(raw).hexdigest()
    ring=ring_census(
        raw,expected_sha256=sha,page_1_based=1,
        candidate_source_room_bbox_pdf_pts=(20,20,140,110),
        original_side_source_path_ids={
            "left":("d0i0",),"right":("d1i0","d2i0"),
            "bottom":("d3i0",),"top":("d4i0","d5i0"),
        },
    )
    assert ring["status"]=="original_black_ink_room_ring_with_virtual_door_gap_candidate"
    return audit(
        raw,expected_sha256=sha,original_ring_source_candidate=ring,
        expected_original_room_text="FREEZER",
        expected_original_door_mark_text="D17",
    )


def test_one_source_room_text_and_one_gap_word_retains_outside_competitor():
    r=_run(_source())
    assert r["status"]=="one_original_room_text_and_door_gap_word_source_candidate"
    assert len(r["source_name_words_inside_candidate_ring"])==1
    assert len(r["other_original_same_room_word_competitors"])==1
    assert len(r["original_door_words_straddling_real_source_gap"])==1
    assert r["original_room_physical_wall_owner_authenticated"] is False
    assert r["original_door_opening_or_threshold_authenticated"] is False
    assert r["new_firm_quantities"]==0


@pytest.mark.parametrize("kwargs",[
    {"missing_door":True},
    {"dupe_door":True},
])
def test_missing_or_duplicate_source_door_word_fails_closed(kwargs):
    result=_run(_source(**kwargs))
    assert result["status"]=="source_room_and_door_word_candidate_abstained"
    assert result["first_unclosed_gate"]=="original_source_label_or_door_mark_not_unique"
    assert result["new_firm_quantities"]==0


def test_reconstructed_source_ring_with_foreign_sha_cannot_bind_source_words():
    raw=_source()
    ring={"status":"original_black_ink_room_ring_with_virtual_door_gap_candidate",
          "original_source_sha256":"0"*64}
    result=audit(
        raw,expected_sha256=hashlib.sha256(raw).hexdigest(),
        original_ring_source_candidate=ring,
        expected_original_room_text="FREEZER",
        expected_original_door_mark_text="D17",
    )
    assert result["first_unclosed_gate"]=="original_source_ink_ring_candidate_unproven"


@pytest.mark.skipif(not ORIGINAL.exists(),reason="private original unavailable")
def test_original_page7_freezer_d17_gap_word_and_other_schedule_freezer_competitor():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    ring=ring_census(
        raw,expected_sha256=SHA,page_1_based=7,
        candidate_source_room_bbox_pdf_pts=FREEZER,
        original_side_source_path_ids=SIDES,
    )
    r=audit(raw,expected_sha256=SHA,original_ring_source_candidate=ring,
            expected_original_room_text="FREEZER",
            expected_original_door_mark_text="D17")
    assert r["status"]=="one_original_room_text_and_door_gap_word_source_candidate"
    assert r["source_name_words_inside_candidate_ring"][0][
        "original_native_word_address"]==(7,28,0,0)
    assert r["original_door_words_straddling_real_source_gap"][0][
        "original_native_word_address"]==(7,185,0,0)
    assert len(r["other_original_same_room_word_competitors"])==1
    assert r["new_firm_quantities"]==0
