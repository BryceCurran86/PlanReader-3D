"""Original native PDF rotation text-integrity proof with all clip gates intact."""
import hashlib
from pathlib import Path

import fitz
import pytest

from pb_pdf_text_integrity_authority import (
    classify_original_rotated_words_with_parity_source as source_classify,
    TEXT_CLIP_STATE_UNRESOLVED,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_original_all_five_physical_ft3_words_are_source_text_only_not_area():
    pytest.importorskip("fontTools")
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    with fitz.open(stream=raw,filetype="pdf") as document:
        words=document[10].get_text("words")
        original=[w for w in words if w[4]=="FT3" and w[0]<1200]
        assert len(original)==5
        addresses=tuple((w[5],w[6],w[7]) for w in original)
    receipts=source_classify(
        raw,expected_original_source_sha256=SOURCE_SHA,
        original_page_number=11,original_native_word_addresses=addresses,
        source_symbol_font_chain_shadow=True,
    )
    assert len(receipts)==5
    assert {a for a,d in receipts}==set(addresses)
    assert all(d.raw_text=="FT3" and not d.trusted for a,d in receipts)
    assert all(TEXT_CLIP_STATE_UNRESOLVED in d.reason_codes for a,d in receipts)
    # Identical native geometry under a page rotation is expected and does
    # not independently validate active PDF clips or the material issuer.
    # Integrity of native text does not itself bind a finish occurrence to
    # a room or issue any material definition/area/customer quantity.
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SOURCE_SHA


def test_original_default_false_keeps_glyph_unverified_and_clip_untrusted():
    raw=ORIGINAL.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as document:
        w=next(w for w in document[10].get_text("words") if w[4]=="FT3")
        address=(w[5],w[6],w[7])
    rows=source_classify(
        raw,expected_original_source_sha256=SOURCE_SHA,
        original_page_number=11,original_native_word_addresses=(address,),
    )
    assert len(rows)==1
    assert not rows[0][1].trusted
    assert rows[0][1].reason_codes


def test_source_foreign_hash_word_address_and_wrong_page_fail_closed():
    raw=ORIGINAL.read_bytes()
    one=(0,0,0)
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        source_classify(raw,expected_original_source_sha256="0"*64,
                        original_page_number=11,
                        original_native_word_addresses=(one,))
    with pytest.raises(ValueError,match="original_native_word_missing_or_ambiguous"):
        source_classify(raw,expected_original_source_sha256=SOURCE_SHA,
                        original_page_number=11,
                        original_native_word_addresses=((999999,0,0),))
    with pytest.raises(ValueError,match="original_source_page_out_of_range"):
        source_classify(raw,expected_original_source_sha256=SOURCE_SHA,
                        original_page_number=999,
                        original_native_word_addresses=(one,))
    with pytest.raises(ValueError,match="original_nonzero_native_rotation_required"):
        doc=fitz.open()
        page=doc.new_page()
        data=doc.tobytes()
        doc.close()
        source_classify(data,
            expected_original_source_sha256=hashlib.sha256(data).hexdigest(),
            original_page_number=1,original_native_word_addresses=(one,))


def test_invalid_bool_and_ambiguous_native_address_do_not_grant_trust():
    raw=ORIGINAL.read_bytes()
    for addresses in ((),((0,0,0),(0,0,0)),((-1,0,0),),([0,0,0],)):
        with pytest.raises((ValueError,TypeError)):
            source_classify(raw,expected_original_source_sha256=SOURCE_SHA,
                            original_page_number=11,
                            original_native_word_addresses=addresses)
    with pytest.raises(ValueError,match="explicit_symbol_source_shadow_bool"):
        source_classify(raw,expected_original_source_sha256=SOURCE_SHA,
                        original_page_number=11,
                        original_native_word_addresses=((0,0,0),),
                        source_symbol_font_chain_shadow=1)


@pytest.mark.parametrize("rotation",[90,180,270])
def test_synthetic_base14_rotated_source_decisions_preserve_true_visibility(rotation):
    doc=fitz.open()
    p=doc.new_page(width=300,height=200)
    p.insert_text((30,50),"ROOM A",fontsize=12)
    p.set_rotation(rotation)
    raw=doc.tobytes()
    doc.close()
    with fitz.open(stream=raw,filetype="pdf") as read:
        words=read[0].get_text("words")
        addresses=tuple((w[5],w[6],w[7]) for w in words)
        assert addresses
    receipts=source_classify(
        raw,expected_original_source_sha256=hashlib.sha256(raw).hexdigest(),
        original_page_number=1,original_native_word_addresses=addresses)
    assert len(receipts)==len(addresses)
    assert all(r.raw_text for _,r in receipts)
    assert all(not r.trusted or not r.reason_codes for _,r in receipts)
    # No synthetic test may compel trusted text from page rotation alone.


def test_renderer_native_paint_parity_conflict_cannot_issue_any_decision(monkeypatch):
    original_get_bboxlog=fitz.Page.get_bboxlog
    def tamper_only_zero_rotation(self,*args,**kwargs):
        rows=list(original_get_bboxlog(self,*args,**kwargs))
        if self.rotation==0:
            rows.append(("fill-text",(0,0,1,1)))
        return rows
    with fitz.open(stream=ORIGINAL.read_bytes(),filetype="pdf") as d:
        w=next(w for w in d[10].get_text("words") if w[4]=="FT3")
        address=(w[5],w[6],w[7])
    monkeypatch.setattr(fitz.Page,"get_bboxlog",tamper_only_zero_rotation)
    with pytest.raises(ValueError,match="native_rotation_source_parity_unresolved"):
        source_classify(ORIGINAL.read_bytes(),
            expected_original_source_sha256=SOURCE_SHA,
            original_page_number=11,
            original_native_word_addresses=(address,),
            source_symbol_font_chain_shadow=True)
