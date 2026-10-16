"""A600 scheduled door dimensions must not borrow fixture-setting dimensions."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_native_door_schedule_row_identity_shadow import (
    _row_candidates,
    audit_original_door_schedule_row_candidates as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _word(block,idx,value):
    return {
        "native_text_block":block,
        "original_native_text_address":[block,0,idx],
        "raw_literal_untrusted":value,
        "original_bbox_pdf_pts":[10.,20.,30.,40.],
        "native_text_integrity_authenticated":False,
    }


def test_unique_source_row_retains_width_height_and_page_ancestry_only():
    words=[_word(7,i,token) for i,token in
           enumerate(["D13","PWD","SINGLE","SWING","920","2040","40"])]
    result=_row_candidates(words)
    assert len(result)==1
    row=result[0]
    assert row["source_width_word_literal_untrusted"]=="920"
    assert row["source_height_word_literal_untrusted"]=="2040"
    assert row["source_width_word_address"]==[7,0,4]
    assert row["source_height_word_address"]==[7,0,5]
    assert not row["schedule_row_semantics_source_verified"]


def test_native_fixture_870_does_not_get_assigned_as_d13_width():
    rows=_row_candidates([
        *[_word(1,i,t) for i,t in enumerate(["870","450","PWD"])],
        *[_word(2,i,t) for i,t in
          enumerate(["D13","PWD","SINGLE","SWING","920","2040","40"])],
    ])
    assert len(rows)==1
    assert rows[0]["source_width_word_literal_untrusted"]=="920"


def test_misleading_missing_height_or_multiple_row_ids_abstains():
    assert not _row_candidates([
        _word(1,i,t) for i,t in enumerate(["D11","SINGLE","SWING","820"])
    ])
    assert not _row_candidates([
        _word(2,i,t) for i,t in enumerate(["D11","D12","SINGLE","SWING","820","2040"])
    ])
    assert not _row_candidates([
        _word(3,i,t) for i,t in enumerate(["D11","SINGLE","SITTING","820","2040"])
    ])


def test_original_a600_three_door_rows_distinguish_ambulant_and_pwd():
    source=PDF.read_bytes()
    assert hashlib.sha256(source).hexdigest()==SHA
    with fitz.open(stream=source,filetype="pdf") as doc:
        result=audit(doc[27],other_plan_pages=(doc[6],doc[25],doc[26]))
        by_code={row["schedule_door_code_literal_untrusted"]:row
                 for row in result["all_original_schedule_row_candidates"]}
        expected={"D11":("820","2040"),"D12":("820","2040"),
                  "D13":("920","2040")}
        for code,(width,height) in expected.items():
            assert code in by_code
            assert (by_code[code]["source_width_word_literal_untrusted"],
                    by_code[code]["source_height_word_literal_untrusted"]) == (width,height)
            assert not by_code[code]["schedule_row_semantics_source_verified"]
        comparison={r["original_door_label_literal_not_trusted"]:r
                    for r in result["original_plan_tag_and_schedule_comparisons"]}
        for code in expected:
            assert comparison[code]["unique_source_row_candidate_but_not_authority"]
            assert comparison[code]["original_plan_label_competitors"]
            assert not comparison[code]["source_width_height_signed_to_opening"]
            assert comparison[code]["default_count_1_not_permitted"]
        assert result["new_authoritative_opening_areas"]==0
        assert result["new_opening_counts"]==0
        assert result["new_customer_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


def test_plan_page_input_must_be_explicit_tuple():
    with fitz.open() as doc:
        page=doc.new_page()
        with pytest.raises(ValueError):
            audit(page,other_plan_pages=[page])
