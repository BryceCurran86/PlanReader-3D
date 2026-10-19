"""FT2/FT3 source schedule word ancestry without trusting OCR or room labels."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_floor_material_schedule_rows_shadow import (
    audit_original_native_floor_finish_schedule_rows as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _sample():
    pdf=fitz.open()
    page=pdf.new_page()
    page.insert_text((20,25),"FT2 FLOOR TILE 800x400 STOCKTON WHITE")
    page.insert_text((20,75),"FT3 FLOOR TILE 600x600 DURA GREY")
    data=pdf.tobytes()
    pdf.close()
    return data


def _run(raw,**changes):
    kwargs={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "page_1_based":1,
        "requested_code_and_native_block":(("FT2",0),("FT3",1)),
    }
    kwargs.update(changes)
    return audit(raw,**kwargs)


def test_two_distinct_source_schedule_material_rows_retained_without_issuance():
    out=_run(_sample())
    rows=out["all_original_schedule_row_candidates"]
    assert [r["material_code_untrusted"] for r in rows]==["FT2","FT3"]
    assert all(len(r["all_original_block_word_candidates"])>=5 for r in rows)
    assert all(r["authenticated_source_material_definition"] is False
               for r in rows)
    assert out["new_firm_quantities"]==0


@pytest.mark.parametrize("bad",[
    {"expected_sha256":"0"*64},
    {"requested_code_and_native_block":(("FT2",0),("FT2",1))},
    {"requested_code_and_native_block":(("FT2",0),("FT3",0))},
    {"requested_code_and_native_block":(("FT2",1),)},
    {"requested_code_and_native_block":(("FT3",3),)},
    {"page_1_based":0},
])
def test_foreign_or_aliasing_original_material_schedule_rows_fail_closed(bad):
    with pytest.raises(ValueError):
        _run(_sample(),**bad)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original unavailable")
def test_original_ft2_ft3_schedule_rows_are_separate_complete_native_blocks():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    out=audit(
        raw,expected_sha256=SHA,page_1_based=11,
        requested_code_and_native_block=(("FT2",243),("FT3",244)),
    )
    a,b=out["all_original_schedule_row_candidates"]
    assert a["all_original_block_word_candidates"][0][
        "original_native_word_address"]==(11,243,0,0)
    assert b["all_original_block_word_candidates"][0][
        "original_native_word_address"]==(11,244,0,0)
    assert any("800x400" in t for line in a["native_original_printed_line_tokens"]
               for t in line)
    assert any("STOCKTON" in t for line in a["native_original_printed_line_tokens"]
               for t in line)
    assert any("600x600" in t for line in b["native_original_printed_line_tokens"]
               for t in line)
    assert any("DURA" in t for line in b["native_original_printed_line_tokens"]
               for t in line)
    assert any("R10" in t for line in a["native_original_printed_line_tokens"]
               for t in line)
    assert any("R12" in t for line in b["native_original_printed_line_tokens"]
               for t in line)
    assert out["source_glyph_raster_clip_and_material_issuer_proven"] is False
    assert out["new_firm_quantities"]==0
