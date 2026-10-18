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
        assert receipt["original_nonclipping_text_render_mode_count"]==78
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



def test_original_rotated_text_raw_authority_avoids_full_clip_graph(monkeypatch):
    """Real production bottleneck: no redundant 27,537-path graph build."""
    import pb_pdf_text_integrity_authority as authority
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[10]
        word=next(w for w in page.get_text("words") if w[4]=="FT3")
        native=_native_word(word)
        def fail_eager_clip_model(_page):
            raise AssertionError("eager_full_CAD_clip_model_not_allowed")
        monkeypatch.setattr(authority,"_clip_model",fail_eager_clip_model)
        # Native/trace/paint checks happen elsewhere; the raw clip check is
        # an independently bounded first gate with direct source ancestry.
        result=authority._text_clip_reasons(
            page,native["bbox"],seqno=None,native_word=native,
            source_raw_no_active_text_clip_shadow=True,
        )
        assert result==()
        # Original default-off rule has NOT been converted to shortcut.
        with pytest.raises(AssertionError,match="eager_full_CAD_clip_model_not_allowed"):
            authority._text_clip_reasons(
                page,native["bbox"],seqno=None,native_word=native,
                source_raw_no_active_text_clip_shadow=False,
            )


def test_raw_clip_source_cache_invalidates_when_pdf_content_changes(monkeypatch):
    import pb_pdf_text_integrity_authority as authority
    d=fitz.open()
    p=d.new_page(width=250,height=200)
    p.insert_text((60,60),"FT3",fontsize=12)
    p.set_rotation(90)
    with fitz.open(stream=d.tobytes(),filetype="pdf") as doc:
        page=doc[0]
        word=next(w for w in page.get_text("words") if w[4]=="FT3")
        native=_native_word(word)
        ok=authority._text_clip_reasons(
            page,native["bbox"],seqno=None,native_word=native,
            source_raw_no_active_text_clip_shadow=True,
        )
        assert ok==()
        stream=page.read_contents()
        xref=page.get_contents()[0]
        changed=stream.replace(b"BT",b"q 0 0 5 5 re W n BT",1).replace(
            b"ET",b"ET Q",1)
        doc.update_stream(xref,changed)
        page=doc[0]
        blocked=authority._text_clip_reasons(
            page,native["bbox"],seqno=None,native_word=native,
            source_raw_no_active_text_clip_shadow=True,
        )
        assert blocked==(TEXT_CLIP_STATE_UNRESOLVED,)
    d.close()



@pytest.mark.parametrize("text_mode", [3,4,5,6,7,8,-1])
def test_text_clip_or_invisible_render_mode_never_grants_source_visibility(text_mode):
    # Text clipping modes are independent of W/W* clip-path operators.
    stream=(
        b"q BT /F1 10 Tf "+str(text_mode).encode()+b" Tr "
        b"(FT3) Tj ET BT (FT2) Tj ET Q"
    )
    operators=_original_source_operators(stream)
    assert b"Tr_unsupported" in operators
    assert not original_content_has_unclipped_text_blocks(stream)[0]


def test_safe_original_tr0_tr2_retained_but_not_render_source_authority():
    content=b"q BT /F1 10 Tf 0 Tr (FT2) Tj ET BT 2 Tr (FT3) Tj ET Q"
    op=_original_source_operators(content)
    assert op.count(b"Tr_safe")==2
    okay,proof=original_content_has_unclipped_text_blocks(content)
    assert okay
    assert proof["original_nonclipping_text_render_mode_count"]==2
    assert proof["source_text_semantic_or_quantity_authority"] is False


def test_render_mode_inside_string_comment_hex_or_name_is_never_executed():
    content=(
        b"q BT /Tr (7 Tr) Tj <34205472> Tj "
        b"% 5 Tr is comment\n"
        b"2 Tr (FT3) Tj ET Q"
    )
    ops=_original_source_operators(content)
    assert ops.count(b"Tr_safe")==1
    assert b"Tr_unsupported" not in ops
    assert original_content_has_unclipped_text_blocks(content)[0]


def test_unbound_or_outside_text_rendering_operator_fails_closed():
    for content in (
        b"q 2 Tr BT (FT2) Tj ET Q",
        b"q BT unknown Tr (FT3) Tj ET Q",
        b"q BT Tr (FT3) Tj ET Q",
    ):
        assert not original_content_has_unclipped_text_blocks(content)[0]
