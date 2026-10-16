"""Direct raw original PDF clipping-operator source ancestry, not handle parity."""
import hashlib
from pathlib import Path

import fitz
import pytest

from pb_pdf_text_integrity_authority import (
    classify_native_word_integrity,
    TEXT_CLIP_STATE_UNRESOLVED,
)
from tools.diag_original_pdf_active_clip_operator_authority import (
    _original_source_operators,
    original_content_has_unclipped_text_blocks,
    source_page_all_native_text_unclipped,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _native_word(w):
    return {
        "text":str(w[4]),"bbox":tuple(float(x) for x in w[:4]),
        "block_no":int(w[5]),"line_no":int(w[6]),"word_no":int(w[7]),
    }


def test_exact_original_p11_raw_clipped_drawing_not_text_no_guessed_rotation():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[10]
        source=page.read_contents()
        ok,receipt=original_content_has_unclipped_text_blocks(source)
        assert ok
        assert receipt["original_source_text_object_count"]==257
        assert receipt["original_raw_clipping_operator_count"]==93
        assert source_page_all_native_text_unclipped(page)
        assert not receipt["source_text_semantic_or_quantity_authority"]
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SOURCE_SHA


def test_original_five_ft3_source_words_only_have_positive_glyph_and_raw_clip_when_opted():
    pytest.importorskip("fontTools")
    with fitz.open(stream=ORIGINAL.read_bytes(),filetype="pdf") as doc:
        page=doc[10]
        physical=[w for w in page.get_text("words")
                  if w[4]=="FT3" and float(w[0])<1200]
        assert len(physical)==5
        for w in physical:
            native=_native_word(w)
            before=classify_native_word_integrity(page,native)
            source=classify_native_word_integrity(
                page,native,source_symbol_font_chain_shadow=True,
                source_raw_no_active_text_clip_shadow=True,
            )
            assert TEXT_CLIP_STATE_UNRESOLVED in before.reason_codes
            assert source.trusted and source.reason_codes==()
            assert source.raw_text=="FT3"
            assert source.visibility_status=="proven_visible"
            # Native text does not publish an FT3 physical floor-finish area.


def test_original_ft2_inplan_tokens_use_same_source_clip_predicate():
    with fitz.open(stream=ORIGINAL.read_bytes(),filetype="pdf") as doc:
        page=doc[10]
        original=[w for w in page.get_text("words")
                  if w[4]=="FT2" and float(w[0])<1200]
        assert len(original)==8
        assert source_page_all_native_text_unclipped(page)
        for w in original:
            unresolved=classify_native_word_integrity(page,_native_word(w))
            assert TEXT_CLIP_STATE_UNRESOLVED in unresolved.reason_codes


def test_literal_strings_hex_names_and_comments_do_not_become_graphics_operators():
    content=(b"q\nBT /q (literal q Q BT ET W*\\\\(x\\\\)) Tj "
             b"<7151572a4254> Tj % Q W* BT\nET\nQ\n")
    ops=_original_source_operators(content)
    assert ops==(b"q",b"BT",b"ET",b"Q")
    assert original_content_has_unclipped_text_blocks(content)[0]


def test_true_clip_scope_and_clipped_text_inside_nested_q_are_rejected():
    examples=(
        b"q 0 0 10 10 re W n BT (FT3) Tj ET Q",
        b"q q 0 0 10 10 re W* n BT (FT3) Tj ET Q Q",
        b"0 0 10 10 re W n BT (FT3) Tj ET",
        b"q 0 0 10 10 re W n q BT (FT3) Tj ET Q Q",
    )
    for stream in examples:
        okay,receipt=original_content_has_unclipped_text_blocks(stream)
        assert not okay
        assert receipt["reason"] in {
            "text_during_original_active_source_clip",
            "unclosed_original_page_clip",
        }


def test_inline_images_unknown_state_unbalanced_stream_and_unclosed_strings_abstain():
    for stream in (
        b"q BI /W 2 /H 2 ID stuff EI Q BT (FT2) Tj ET",
        b"Q BT (FT2) Tj ET",
        b"q BT (FT2) Tj ET",
        b"q BT (FT2 Tj ET Q",
        b"BT (FT2) Tj ET ET",
        b"BT (FT2) Tj BT ET",
        b"q BX BT (FT2) Tj ET EX Q",
    ):
        ok,_=original_content_has_unclipped_text_blocks(stream)
        assert not ok


def test_absent_source_word_and_wrong_optin_value_never_bypass_clip():
    with fitz.open(stream=ORIGINAL.read_bytes(),filetype="pdf") as doc:
        p=doc[10]
        w=next(w for w in p.get_text("words") if w[4]=="FT3")
        word=_native_word(w)
        invalid={**word,"text":"NOT_SOURCE_WORD"}
        out=classify_native_word_integrity(
            p,invalid,source_symbol_font_chain_shadow=True,
            source_raw_no_active_text_clip_shadow=True)
        assert not out.trusted
        with pytest.raises(ValueError,match="source_raw_clip_shadow_requires_explicit_bool"):
            classify_native_word_integrity(
                p,word,source_raw_no_active_text_clip_shadow=1)


def test_real_source_text_clipped_by_inserted_operator_fails_raw_ancestry():
    doc=fitz.open()
    p=doc.new_page(width=240,height=180)
    p.insert_text((70,70),"FT2",fontsize=11)
    original=p.read_contents()
    assert b"BT" in original and b"ET" in original
    poisoned=original.replace(
        b"BT",b"q 0 0 5 5 re W n BT",1,
    ).replace(b"ET",b"ET Q",1)
    xrefs=p.get_contents()
    assert len(xrefs)==1
    doc.update_stream(xrefs[0],poisoned)
    p=doc[0]
    assert not source_page_all_native_text_unclipped(p)
    doc.close()
