"""Reject original door-code detail labels as schedule rows.

Uses typed original native PDF room and leaf-kind fields. Code equality alone
cannot authenticate a construction door schedule or its physical opening.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_door_schedule_native_words_shadow import (
    census_original_door_schedule_native_source as census,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _fixture(malformed_leaf=None):
    pdf=fitz.open()
    page=pdf.new_page(width=400,height=340)
    page.insert_text((20,30),"D17 DETAIL LABEL")
    page.insert_text((20,100),"D17\nFREEZER\n"+
                     (malformed_leaf if malformed_leaf is not None else "SLIDING DOOR")+
                     "\n800\n2000\n75")
    plan=pdf.new_page()
    plan.insert_text((20,30),"D17")
    raw=pdf.tobytes()
    pdf.close()
    return raw


def _check(raw,block=1):
    return census(
        raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
        schedule_page_1_based=1,plan_page_1_based=2,
        requested_door_code="D17",schedule_native_block=block,
    )


def test_complete_original_style_source_schedule_accepts_one_sliding_row():
    row=_check(_fixture())
    assert row["status"]=="native_original_door_schedule_and_plan_words_only"
    assert row["original_schedule_row_lines"][2]==("SLIDING","DOOR")
    assert len(row["all_original_schedule_same_door_code_words"])==2
    assert row["door_schedule_semantic_issuer_authenticated"] is False
    assert row["doorway_gap_metric_width_proven"] is False
    assert row["new_firm_quantities"]==0


def test_detail_label_is_never_accepted_as_door_schedule_by_code_alone():
    with pytest.raises(ValueError,match="original_door_schedule_native_row_semantics_unproven"):
        _check(_fixture(),block=0)


@pytest.mark.parametrize("bad_leaf",["DETAIL LABEL","SLIDING","DOOR",""])
def test_missing_original_leaftype_fails_even_if_room_code_text_agree(bad_leaf):
    with pytest.raises(ValueError,match="original_door_schedule_native_row_semantics_unproven"):
        _check(_fixture(malformed_leaf=bad_leaf))


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original PDF unavailable")
@pytest.mark.parametrize("code,block,room,leaf",[
    ("D10",107,("LAUNDRY",),("SINGLE","SWING")),
    ("D11",108,("F-AMB",),("SINGLE","SWING")),
    ("D12",109,("M-AMB",),("SINGLE","SWING")),
    ("D13",110,("PWD",),("SINGLE","SWING")),
    ("D15",112,("OFFICE",),("SINGLE","SWING")),
    ("D17",114,("FREEZER",),("SLIDING","DOOR")),
    ("D18",115,("FREEZER",),("AS","PER","MANUFACTURER")),
    ("D19",116,("FREEZER",),("AS","PER","MANUFACTURER")),
])
def test_original_amenity_office_and_freezer_door_schedule_native_types(
    code,block,room,leaf,
):
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=census(
        raw,expected_sha256=SHA,
        schedule_page_1_based=28,plan_page_1_based=7,
        requested_door_code=code,schedule_native_block=block,
    )
    assert result["original_schedule_row_lines"][1]==room
    assert result["original_schedule_row_lines"][2]==leaf
    assert result["plan_doorway_physical_owner_authenticated"] is False
    assert result["new_firm_quantities"]==0
