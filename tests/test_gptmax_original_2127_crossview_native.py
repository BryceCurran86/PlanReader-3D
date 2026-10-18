"""Cross-sheet 2127 native label proof; no host/quantity promotion."""
from pathlib import Path

import fitz
import pytest

from tools.diag_gptmax_original_2127_crossview_native import (
    LOT16_ORIGINAL_SHA,
    paired_native_2127_tokens,
    original_2127_crossview_receipt,
)


def _synthetic_page(*, word="STACKER", duplicate=False):
    doc=fitz.open()
    page=doc.new_page(width=600,height=300)
    page.insert_text((100,100),"2127 "+word,fontsize=10)
    if duplicate:
        page.insert_text((100,140),"2127 "+word,fontsize=10)
    return doc


def test_native_pair_requires_adjacent_words_on_same_line():
    doc=_synthetic_page()
    assert len(paired_native_2127_tokens(doc[0]))==1
    doc.close()
    doc=_synthetic_page(duplicate=True)
    assert len(paired_native_2127_tokens(doc[0]))==2
    doc.close()
    doc=_synthetic_page(word="SLIDER")
    assert paired_native_2127_tokens(doc[0])==()
    doc.close()


def test_other_drawing_or_untrusted_bytes_cannot_claim_crossview():
    doc=_synthetic_page()
    payload=doc.tobytes()
    doc.close()
    with pytest.raises(ValueError,match="SHA-verified"):
        original_2127_crossview_receipt(payload)
    with pytest.raises(ValueError,match="SHA-verified"):
        original_2127_crossview_receipt("not native bytes")


def test_exact_original_crossview_only_with_sha_verified_source():
    path=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
    if not path.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: original-source proof NOT passed")
    data=path.read_bytes()
    from hashlib import sha256
    assert sha256(data).hexdigest()==LOT16_ORIGINAL_SHA
    receipt=original_2127_crossview_receipt(data)
    assert [r["page_number"] for r in receipt["native_marks"]]==[3,5]
    assert all(r["source_authentic"] is True for r in receipt["native_marks"])
    assert receipt["unique_structural_host_proven"] is False
    assert receipt["exact_cross_page_physical_identity_proven"] is False
    assert receipt["quantity_promotion_granted"] is False
    with pytest.raises(ValueError,match="SHA-verified"):
        original_2127_crossview_receipt(data+b"altered")
