"""Actual source FT3 glyph GIDs verified against embedded PDF byte mappings only.

Source CI installs optional fontTools explicitly; the general matrix can skip
its positive original-font execution. No new trusted text or material authority:
the rotated original clip gate is unchanged and must independently pass.
"""
import hashlib
from pathlib import Path

import fitz
import pytest
from pb_pdf_text_integrity_authority import (
    _source_embedded_symbol_byte_glyph_reasons,
    classify_native_word_integrity,
    TEXT_GLYPH_UNICODE_MISMATCH,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    TEXT_CLIP_STATE_UNRESOLVED,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _word_native(word):
    return {
        "text":str(word[4]),"bbox":tuple(float(x) for x in word[:4]),
        "block_no":int(word[5]),"line_no":int(word[6]),
        "word_no":int(word[7]),
    }


def test_source_original_five_ft3_plan_words_recover_embedded_gids_not_clip():
    pytest.importorskip("fontTools")
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[10]
        words=[w for w in page.get_text("words")
               if w[4]=="FT3" and float(w[0])<1200]
        assert len(words)==5
        for word in words:
            before=classify_native_word_integrity(page,_word_native(word))
            after=classify_native_word_integrity(
                page,_word_native(word),
                source_symbol_font_chain_shadow=True,
            )
            assert TEXT_GLYPH_MAPPING_UNVERIFIED in before.reason_codes
            assert TEXT_GLYPH_MAPPING_UNVERIFIED not in after.reason_codes
            assert TEXT_GLYPH_UNICODE_MISMATCH not in after.reason_codes
            assert after.decode_status=="validated_tounicode"
            assert TEXT_CLIP_STATE_UNRESOLVED in after.reason_codes
            assert not after.trusted
            assert before.trusted is False
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_modified_renderer_glyph_id_is_detected_in_original_symbol_font():
    pytest.importorskip("fontTools")
    raw=ORIGINAL.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[10]
        font=[f for f in page.get_fonts(full=True)
              if str(f[3]).split("+")[-1]=="ISOCPEUR"]
        assert len(font)==1
        original_font=font[0]
        valid={"chars":((70,39,(0,0),(0,0,1,1)),
                        (84,53,(0,0),(0,0,1,1)),
                        (51,20,(0,0),(0,0,1,1)))}
        fake={"chars":((70,39,(0,0),(0,0,1,1)),
                       (84,999,(0,0),(0,0,1,1)),
                       (51,20,(0,0),(0,0,1,1)))}
        assert _source_embedded_symbol_byte_glyph_reasons(
            page,valid,original_font)==()
        assert _source_embedded_symbol_byte_glyph_reasons(
            page,fake,original_font)==(TEXT_GLYPH_UNICODE_MISMATCH,)


def test_non_true_type_missing_font_and_invalid_glyph_must_abstain():
    with fitz.open(stream=ORIGINAL.read_bytes(),filetype="pdf") as doc:
        p=doc[10]
        assert _source_embedded_symbol_byte_glyph_reasons(
            p,{"chars":((70,39,None,None),)},(293,"ttf","Type3")
        )==(TEXT_GLYPH_MAPPING_UNVERIFIED,)
        assert _source_embedded_symbol_byte_glyph_reasons(
            p,{"chars":((70,0,None,None),)},(293,"ttf","TrueType")
        )==(TEXT_GLYPH_MAPPING_UNVERIFIED,)
        assert _source_embedded_symbol_byte_glyph_reasons(
            p,{"chars":((70,-1,None,None),)},(293,"ttf","TrueType")
        )==(TEXT_GLYPH_MAPPING_UNVERIFIED,)


def test_default_classifier_unchanged_and_explicit_bool_required():
    raw=ORIGINAL.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as doc:
        p=doc[10]
        word=next(w for w in p.get_text("words") if w[4]=="FT3")
        v=_word_native(word)
        assert classify_native_word_integrity(p,v)==classify_native_word_integrity(
            p,v,source_symbol_font_chain_shadow=False
        )
        with pytest.raises(ValueError,match="symbol_source_glyph_shadow_requires_explicit_bool"):
            classify_native_word_integrity(p,v,source_symbol_font_chain_shadow=1)
