"""Independent original 1215 SGW native semantic and crossview source evidence."""
import fitz
import pytest
from pathlib import Path
from tools.diag_gptmax_original_1215_sgw_legend import (
    original_1215_semantic_label_receipt, native_phrase_pairs, SOURCE_SHA,
)


def test_native_1215_phrase_requires_exact_adjacent_typed_words():
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((50,70),"1215 SGW obs",fontsize=9)
    assert len(native_phrase_pairs(page,("1215","SGW","obs")))==1
    assert native_phrase_pairs(page,("1215","SGD","obs"))==()
    page.insert_text((50,110),"1215 SGW obs",fontsize=9)
    assert len(native_phrase_pairs(page,("1215","SGW","obs")))==2
    doc.close()


def test_other_pdf_with_matching_words_cannot_issue_original_label_proof():
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((50,70),"1215 SGW obs",fontsize=9)
    with pytest.raises(ValueError,match="SHA-verified"):
        original_1215_semantic_label_receipt(doc.tobytes())
    doc.close()


def test_original_1215_legend_is_window_only_with_sha_verified_pdf():
    path=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
    if not path.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: exact source test NOT passed")
    payload=path.read_bytes()
    from hashlib import sha256
    assert sha256(payload).hexdigest()==SOURCE_SHA
    receipt=original_1215_semantic_label_receipt(payload)
    assert receipt["original_code_semantics_proven"] is True
    assert receipt["original_legend"]["semantic_kind"]=="window"
    assert [row["page_number"] for row in receipt["native_mark_receipts"]]==[3,5]
    assert receipt["cross_page_physical_same_proven"] is False
    assert receipt["signed_customer_quantity_promoted"] is False
    with pytest.raises(ValueError,match="SHA-verified"):
        original_1215_semantic_label_receipt(payload+b"changed")
