"""The existing source PDF issuer, not a new publisher, controls native text."""
import hashlib
from pathlib import Path

import fitz
import pytest

from pb_source_visibility_authority import (
    SourceVisibilityProducer,
    _derive_visibility_page,
)
from pb_pdf_text_integrity_authority import TEXT_CLIP_STATE_UNRESOLVED

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _raw_ft3(words):
    return [w for w in words if w.raw_text=="FT3"
            and float(w.geometry[0])<1200]


def _raw_ft2(words):
    return [w for w in words if w.raw_text=="FT2"
            and float(w.geometry[0])<1200]


def test_original_page11_source_issuer_optin_yields_native_words_not_material_areas():
    pytest.importorskip("fontTools")
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as document:
        page=document[10]
        baseline=_derive_visibility_page(page)
        assert len(_raw_ft3(baseline.words))==5
        assert len(_raw_ft2(baseline.words))==8
        assert all(not w.decision.trusted for w in _raw_ft3(baseline.words))
        assert all(TEXT_CLIP_STATE_UNRESOLVED in w.decision.reason_codes
                   for w in _raw_ft3(baseline.words))

        positive=_derive_visibility_page(
            page,source_native_finish_text_shadow=True,
        )
        assert len(_raw_ft3(positive.words))==5
        assert len(_raw_ft2(positive.words))==8
        assert all(w.decision.trusted for w in _raw_ft3(positive.words))
        assert all(w.decision.trusted for w in _raw_ft2(positive.words))
        assert {w.primitive_ref for w in _raw_ft3(positive.words)}=={
            w.primitive_ref for w in _raw_ft3(baseline.words)
        }
        assert all(w.decision.raw_text==w.raw_text
                   for w in positive.words if w.raw_text in ("FT2","FT3"))
        assert positive.visible_segments==baseline.visible_segments
        assert any(not w.decision.trusted for w in positive.words)
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_full_source_visibility_producer_uses_own_original_word_receipts():
    pytest.importorskip("fontTools")
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    producer=SourceVisibilityProducer(
        producer_method="source-test-readonly",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    pub=producer.ingest_native_pdf_bytes(
        document_id="document_with_actual_original_source_bytes",
        source_bytes=raw,
        source_locator="memory://gpt2-immutable-original.pdf",
        page_ids=("11",),
    )
    assert pub.revision.source_sha256==SHA
    assert pub.text_observation_ids
    # Producer uses the same native source observation and
    # PdfTextIntegrityReceipt ownership seams, not a caller-made mapping.
    text=producer._text_integrity_receipts
    visible_ft3=[
        row for (snapshot,id),row in text.items()
        if snapshot==pub.snapshot.snapshot_id and row.raw_text=="FT3"
        and row.page_id=="11" and row.trusted
    ]
    visible_ft2=[
        row for (snapshot,id),row in text.items()
        if snapshot==pub.snapshot.snapshot_id and row.raw_text=="FT2"
        and row.page_id=="11" and row.trusted
    ]
    assert len(visible_ft3)==6
    assert len(visible_ft2)==9
    for row in (*visible_ft3,*visible_ft2):
        assert row.source_sha256==SHA
        assert row.source_partition_id=="page:11"
        assert row.decode_status=="validated_tounicode"
    assert producer.published_snapshot_for_revision(
        pub.revision.revision_id
    )==pub


def test_default_off_has_no_raw_clip_or_symbol_optin_and_rejects_bogus_flag():
    producer=SourceVisibilityProducer(
        producer_method="default-off-original",
        producer_version="1",
    )
    assert producer._source_native_finish_text_shadow is False
    for invalid in (1,"true",None,[],{}):
        with pytest.raises(ValueError,match="source_finish_text_shadow_requires_explicit_bool"):
            SourceVisibilityProducer(
                producer_method="original-test",producer_version="1",
                source_native_finish_text_shadow=invalid,
            )
    with fitz.open(stream=ORIGINAL.read_bytes(),filetype="pdf") as doc:
        original=_derive_visibility_page(doc[10])
        false=_derive_visibility_page(doc[10],source_native_finish_text_shadow=False)
        assert original==false
        with pytest.raises(ValueError,match="source_finish_text_shadow_requires_explicit_bool"):
            _derive_visibility_page(doc[10],source_native_finish_text_shadow=1)
