"""D17 scheduled sliding freezer door remains distinct from door detail label."""
from __future__ import annotations
import hashlib
from pathlib import Path

import fitz
import pytest
from tools.diag_gpt2_original_door_schedule_native_words_shadow import (
    census_original_door_schedule_native_source as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _source():
    pdf=fitz.open()
    p=pdf.new_page()
    p.insert_text((10,20),"D17 DETAIL LABEL")
    p.insert_text((10,60),"D17 FREEZER SLIDING DOOR 800 2000 75")
    p2=pdf.new_page()
    p2.insert_text((10,30),"D17 FREEZER")
    data=pdf.tobytes()
    pdf.close()
    return data


def _run(data,**kwargs):
    params={
        "expected_sha256":hashlib.sha256(data).hexdigest(),
        "schedule_page_1_based":1,
        "plan_page_1_based":2,
        "requested_door_code":"D17",
        "schedule_native_block":1,
    }
    params.update(kwargs)
    return audit(data,**params)


def test_one_native_schedule_row_preserves_other_same_code_detail_word():
    result=_run(_source())
    assert result["status"]=="native_original_door_schedule_and_plan_words_only"
    assert len(result["all_original_schedule_same_door_code_words"])==2
    assert len(result["all_original_plan_same_door_code_words"])==1
    assert result["doorway_gap_metric_width_proven"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("bad",[
    {"expected_sha256":"0"*64},
    {"requested_door_code":"D16"},
    {"schedule_native_block":0},
    {"schedule_native_block":3},
    {"plan_page_1_based":1},
    {"requested_door_code":"D17 "},
])
def test_foreign_or_wrong_original_schedule_candidate_fails_closed(bad):
    with pytest.raises(ValueError):
        _run(_source(),**bad)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="owner private source not provisioned")
def test_original_a600_d17_door_schedule_and_p7_plan_are_different_source_roles():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(raw,expected_sha256=SHA,schedule_page_1_based=28,
                 plan_page_1_based=7,requested_door_code="D17",
                 schedule_native_block=114)
    assert result["status"]=="native_original_door_schedule_and_plan_words_only"
    assert {row["original_native_word_address"] for row
            in result["all_original_schedule_same_door_code_words"]}=={
                (28,50,0,0),(28,114,0,0)
            }
    assert (7,185,0,0) in {row["original_native_word_address"] for row
            in result["all_original_plan_same_door_code_words"]}
    lines=result["original_schedule_row_lines"]
    assert lines[0]==("D17",)
    assert lines[1]==("FREEZER",)
    assert lines[2]==("SLIDING","DOOR")
    assert lines[3]==("800",)
    assert lines[4]==("2000",)
    assert lines[5]==("75",)
    assert lines[6]==("BY","COOLROOM","CONTRACTOR")
    assert result["plan_doorway_physical_owner_authenticated"] is False
    assert result["new_firm_quantities"]==0
