"""Source-byte symbol cmap audit: no Unicode/glyph visual-trust promotion."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_pdf_symbol_byte_glyph_shadow import (
    _unique_source_tounicode, _source_truetype_symbol_subtables,
    audit_pdf_embedded_symbol_source,
)


ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_original_ft3_dash_and_both_quotes_source_byte_ttf_gid_proof():
    source=ORIGINAL.read_bytes()
    assert hashlib.sha256(source).hexdigest()==SHA
    # Original native text-block ordinal differs between supported MuPDF
    # extraction versions; authenticate one *complete original FT3 row* in
    # this test runtime instead of copying a foreign version's block index.
    with fitz.open(stream=source,filetype="pdf") as original:
        blocks={}
        for word in original[10].get_text("words",flags=fitz.TEXTFLAGS_WORDS):
            blocks.setdefault(word[5],[]).append(word)
        complete=[
            words for words in blocks.values()
            if {"FT3","-","“DURA","GREY”"}.issubset({w[4] for w in words})
        ]
        assert len(complete)==1
        candidates=complete[0]
        addresses=tuple(
            (w[5],w[6],w[7])
            for token in ("-","“DURA","GREY”")
            for w in candidates if w[4]==token
        )
        assert len(addresses)==3 and len(set(addresses))==3
    result=audit_pdf_embedded_symbol_source(
        source,expected_sha256=SHA,page_number=11,
        native_word_addresses=addresses,
    )
    assert [r["native_literal_word"] for r in result["source_word_candidates"]]==[
        "-", "“DURA","GREY”"
    ]
    assert result["source_font_inventory_status"]
    for row in result["source_word_candidates"]:
        candidates=row["all_competing_native_trace_word_candidates"]
        assert len(candidates)==1
        assert candidates[0]["all_code_mapping_candidates_agree"]
        assert all(x["unique_pdf_code_to_font_glyph_candidate_agrees"]
                   for x in candidates[0]["glyph_rows"])
        assert not candidates[0]["proves_text_or_material"]
        assert not row["source_clip_and_ink_proven"]
        assert not row["native_text_integrity_trusted_by_this_audit"]
    dash,opening,closing=result["source_word_candidates"]
    assert dash["all_competing_native_trace_word_candidates"][0]["glyph_rows"][0]["all_original_pdf_code_candidates"]==[
        {"original_pdf_character_byte":0x23,"true_type_symbol_gid":14}
    ]
    assert opening["all_competing_native_trace_word_candidates"][0]["glyph_rows"][0]["all_original_pdf_code_candidates"]==[
        {"original_pdf_character_byte":0x46,"true_type_symbol_gid":197}
    ]
    assert closing["all_competing_native_trace_word_candidates"][0]["glyph_rows"][-1]["all_original_pdf_code_candidates"]==[
        {"original_pdf_character_byte":0x47,"true_type_symbol_gid":198}
    ]
    assert result["new_trusted_native_words"]==0
    assert result["new_material_definition"]==0
    assert result["new_physical_room_correspondence"]==0
    assert result["new_customer_quantities"]==0
    assert not result["uses_frozen_benchmark_truth"]
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_exact_native_word_address_required_and_wrong_pdf_rejected():
    source=ORIGINAL.read_bytes()
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        audit_pdf_embedded_symbol_source(source,expected_sha256="0"*64,
            page_number=11,native_word_addresses=((244,2,2),))
    for malformed in [(), ((-1,2,3),), ((244,2),), ((244,2,"3"),)]:
        with pytest.raises(ValueError,match="explicit native source word addresses"):
            audit_pdf_embedded_symbol_source(source,expected_sha256=SHA,
                page_number=11,native_word_addresses=malformed)


def test_missing_original_native_word_does_not_retarget_nearest():
    source=ORIGINAL.read_bytes()
    result=audit_pdf_embedded_symbol_source(source,expected_sha256=SHA,
        page_number=11,native_word_addresses=((99999,1,0),))
    assert len(result["source_word_candidates"])==1
    assert result["source_word_candidates"][0]["first_gate"]=="native_word_unavailable"
    assert not result["source_word_candidates"][0]["text_verified_or_trusted"]


def test_truncated_or_fontless_tables_abstain():
    assert _source_truetype_symbol_subtables(b"")[1]=="embedded_font_program_unavailable"
    assert _source_truetype_symbol_subtables(b"garbled font binary")[0]=={}


class MockDoc:
    def __init__(self, payload):
        self.payload=payload
    def xref_get_key(self,*_):
        return ("xref","9 0 R")
    def xref_stream(self,*_):
        return self.payload


def test_competing_tounicode_bfchar_refused():
    payload=b"1 begincodespacerange\n<00><ff>\nendcodespacerange\n<46><46><201c>\n1 beginbfchar\n<47><201d>\nendbfchar"
    parsed,reason=_unique_source_tounicode(MockDoc(payload),293)
    assert parsed=={} and reason=="unhandled_tounicode_bfchar"


def test_conflicting_duplicate_pdf_code_fails_closed():
    payload=b"1 begincodespacerange\n<00><ff>\nendcodespacerange\n<46><46><201c>\n<46><46><0041>"
    parsed,reason=_unique_source_tounicode(MockDoc(payload),293)
    assert parsed=={} and reason=="conflicting_pdf_unicode"


def test_wrong_page_produces_no_false_positive_source_font():
    source=ORIGINAL.read_bytes()
    result=audit_pdf_embedded_symbol_source(source,expected_sha256=SHA,
        page_number=7,native_word_addresses=((244,2,2),))
    assert result["new_trusted_native_words"]==0
    assert result["new_material_definition"]==0
    assert not result["uses_frozen_benchmark_truth"]
