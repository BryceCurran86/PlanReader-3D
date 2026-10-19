"""Original A120 RCP height/code callouts are not physical ceiling m2."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_rcp_code_height_pairs_shadow import (
    audit_original_rcp_native_material_height_pairs as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _synthetic():
    doc=fitz.open()
    p=doc.new_page()
    p.insert_text((20,50),"2400\nGRID")
    p.insert_text((20,100),"2400\nWFPB")
    p.insert_text((20,150),"3000\nFPB")
    p.insert_text((20,200),"2400\nIP")
    p.insert_text((120,60),"GRID")  # No separate code/height line.
    p.insert_text((120,150),"2400\nCLD3") # Signage cladding is NOT a ceiling.
    data=doc.tobytes()
    doc.close()
    return data


def _run(data,**changes):
    fields={
        "expected_sha256":hashlib.sha256(data).hexdigest(),
        "page_1_based":1,
    }
    fields.update(changes)
    return audit(data,**fields)


def test_exact_source_native_height_and_material_code_pairs_remain_unissued():
    result=_run(_synthetic())
    records=result["all_exact_native_code_numeric_callout_pairs"]
    assert {x["source_material_code_untrusted"] for x in records}=={
        "GRID","WFPB","FPB","IP"
    }
    assert len(records)==4
    assert "CLD3" not in {x["source_material_code_untrusted"] for x in records}
    assert len(result["original_unpaired_or_schedule_code_words"])==1
    assert result["source_rcp_viewport_owner_authenticated"] is False
    assert result["source_code_height_unit_authenticated"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("changed",[
    {"expected_sha256":"0"*64},
    {"page_1_based":0},
    {"max_source_words":1},
    {"material_codes":("CLD3",)},
    {"material_codes":("GRID","GRID")},
    {"material_codes":()},
])
def test_original_wrong_source_or_signage_material_never_becomes_ceiling(changed):
    with pytest.raises(ValueError):
        _run(_synthetic(),**changed)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original source not provisioned")
def test_original_a120_native_grid_wfpb_fpb_ip_callouts_are_distinct():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(raw,expected_sha256=SHA,page_1_based=9)
    paired=result["all_exact_native_code_numeric_callout_pairs"]
    groups={}
    for row in paired:
        groups.setdefault(row["source_material_code_untrusted"],[]).append(row)
    assert {code:len(rows) for code,rows in groups.items()}=={
        "GRID":2,"WFPB":8,"FPB":5,"IP":2
    }
    assert {row["source_numeric_height_callout_uninterpreted"]
            for row in groups["WFPB"]}=={"2400"}
    assert {row["source_numeric_height_callout_uninterpreted"]
            for row in groups["FPB"]}=={"3000"}
    assert {(r["original_native_block"],r["source_numeric_height_callout_uninterpreted"])
            for r in groups["GRID"]}=={(10,"2400"),(114,"3000")}
    assert (9,10,1,0) in {
        r["source_material_code_native_word_id"] for r in groups["GRID"]
    }
    assert all(r["source_original_ceiling_zone_owned"] is False for r in paired)
    assert result["new_firm_quantities"]==0
