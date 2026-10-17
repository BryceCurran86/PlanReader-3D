"""Readers that need the native page decode after visibility publication released it.

Publication drops its page decodes once the records are stored (the memory bound). A later reader that needs
source graphic state (the raster dimension tie-break reads line width and colour) decodes the producer's own
retained source bytes again, only when their hash is the revision's source hash, and does not re-cache it.
"""
from __future__ import annotations

from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_raster_source_visibility_v1 import _hybrid_pdf


def _published():
    source = SourceVisibilityProducer(
        producer_method="native-page-read-after-release", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id="native-page-read-doc",
        source_bytes=_hybrid_pdf(),
        source_locator="memory://native-page-read.pdf",
        page_ids=("1",),
    )
    return source, published


def test_publication_releases_the_decode_and_a_reader_decodes_the_retained_bytes_once():
    source, published = _published()
    writer = source._producer
    assert not writer._native_page_decode_cache

    entry = writer._native_page_for_read(
        published.revision.revision_id, published.revision.source_sha256, 1
    )

    assert entry is not None and not entry.failed
    assert entry.native_page["segments"]
    # The fresh decode is not cached again: the release stays the memory bound.
    assert not writer._native_page_decode_cache


def test_a_hash_mismatch_or_missing_bytes_or_page_returns_no_decode():
    source, published = _published()
    writer = source._producer
    revision_id = published.revision.revision_id

    assert writer._native_page_for_read(revision_id, "0" * 64, 1) is None
    assert writer._native_page_for_read("unknown-revision", published.revision.source_sha256, 1) is None
    assert writer._native_page_for_read(revision_id, published.revision.source_sha256, 2) is None
    assert writer._native_page_for_read(revision_id, published.revision.source_sha256, 0) is None

    writer._store.source_bytes_by_revision[revision_id] = b"%PDF-1.7 tampered"
    assert writer._native_page_for_read(revision_id, published.revision.source_sha256, 1) is None
