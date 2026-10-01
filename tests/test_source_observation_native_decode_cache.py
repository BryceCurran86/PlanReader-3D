from __future__ import annotations

import fitz
import pytest

import pb_source_observation_authority as source_module
from pb_source_observation_authority import SourceObservationProducer


def _one_page_pdf() -> bytes:
    # Two physical pages let tests distinguish a strict page-1 ingest from a
    # full-document ingest while still exercising only page 1 in the cache.
    doc = fitz.open()
    try:
        page = doc.new_page(width=300.0, height=200.0)
        page.draw_line((20.0, 40.0), (280.0, 40.0))
        page.insert_text((40.0, 90.0), "ROOM 01")
        second = doc.new_page(width=300.0, height=200.0)
        second.insert_text((40.0, 90.0), "PAGE 02")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _clear_native_decode_cache() -> None:
    with source_module._NATIVE_PAGE_DECODE_CACHE_LOCK:
        source_module._NATIVE_PAGE_COUNT_CACHE.clear()
        source_module._NATIVE_PAGE_DECODE_CACHE.clear()


def test_native_decode_is_reused_across_producers_without_changing_provenance(
    monkeypatch,
) -> None:
    _clear_native_decode_cache()
    payload = _one_page_pdf()

    original = source_module.extract_native_page
    calls = 0

    def counted(page):
        nonlocal calls
        calls += 1
        return original(page)

    monkeypatch.setattr(source_module, "extract_native_page", counted)

    first = SourceObservationProducer(
        producer_method="decode-cache-first",
        producer_version="1",
    ).ingest_native_pdf_bytes(
        document_id="decode-cache-doc",
        source_bytes=payload,
        source_locator="memory://first.pdf",
        page_ids=("1",),
    )
    second = SourceObservationProducer(
        producer_method="decode-cache-second",
        producer_version="1",
    ).ingest_native_pdf_bytes(
        document_id="decode-cache-doc",
        source_bytes=payload,
        source_locator="memory://second.pdf",
        page_ids=("1",),
    )

    assert calls == 1
    assert first.revision.revision_id == second.revision.revision_id
    assert first.revision.source_sha256 == second.revision.source_sha256
    assert first.coverage == second.coverage
    assert first.snapshot.observation_ids == second.snapshot.observation_ids
    assert first.snapshot.snapshot_id != second.snapshot.snapshot_id
    assert first.snapshot.producer_method == "decode-cache-first"
    assert second.snapshot.producer_method == "decode-cache-second"


def test_decode_cache_does_not_weaken_fixed_scope_replay_guard() -> None:
    _clear_native_decode_cache()
    payload = _one_page_pdf()
    producer = SourceObservationProducer(
        producer_method="decode-cache-scope",
        producer_version="1",
    )
    first = producer.ingest_native_pdf_bytes(
        document_id="decode-cache-scope-doc",
        source_bytes=payload,
        source_locator="memory://scope.pdf",
        page_ids=("1",),
    )
    replay = producer.ingest_native_pdf_bytes(
        document_id="decode-cache-scope-doc",
        source_bytes=payload,
        source_locator="memory://scope.pdf",
        page_ids=("1",),
    )
    assert replay == first

    with pytest.raises(ValueError, match="snapshot_mismatch"):
        producer.ingest_native_pdf_bytes(
            document_id="decode-cache-scope-doc",
            source_bytes=payload,
            source_locator="memory://scope.pdf",
            page_ids=None,
        )
