from __future__ import annotations

import hashlib
from dataclasses import replace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    PRODUCER_INTEGRITY_FAILURE,
    ObservationSelector,
    SourceObservationProducer,
)


def _single_page_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=300.0, height=200.0)
        page.insert_text(fitz.Point(30.0, 60.0), "SOURCE INTEGRITY CACHE")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_resolve_reuses_verified_immutable_source_hash_but_detects_replacement(
    monkeypatch,
) -> None:
    payload = _single_page_pdf()
    producer = SourceObservationProducer(
        producer_method="test-source-hash-cache",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-source-hash-cache",
        source_bytes=payload,
        source_locator="memory://source-hash-cache.pdf",
        page_ids=("1",),
    )
    observation_id = published.snapshot.observation_ids[0]
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )

    stored = producer._store.source_bytes_by_revision[published.revision.revision_id]
    tampered = stored + b"tampered"
    source_hash_calls = 0
    real_sha256 = hashlib.sha256

    def counting_sha256(data=b"", *args, **kwargs):
        nonlocal source_hash_calls
        if data is stored or data is tampered:
            source_hash_calls += 1
        return real_sha256(data, *args, **kwargs)

    monkeypatch.setattr(
        "pb_source_observation_authority.hashlib.sha256",
        counting_sha256,
    )

    first = producer.authority().resolve(selector)
    second = producer.authority().resolve(selector)
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert second.status is EvidenceResolutionStatus.CORROBORATED
    assert source_hash_calls == 0

    producer._store.source_bytes_by_revision[
        published.revision.revision_id
    ] = tampered
    after_replacement = producer.authority().resolve(selector)

    assert source_hash_calls == 1
    assert after_replacement.status is EvidenceResolutionStatus.CONFLICT
    assert after_replacement.reason_codes == (PRODUCER_INTEGRITY_FAILURE,)


def test_snapshot_membership_index_rebuilds_if_store_snapshot_is_replaced() -> None:
    payload = _single_page_pdf()
    producer = SourceObservationProducer(
        producer_method="test-snapshot-membership-index",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-snapshot-membership-index",
        source_bytes=payload,
        source_locator="memory://snapshot-membership-index.pdf",
        page_ids=("1",),
    )
    observation_id = published.snapshot.observation_ids[0]
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )

    assert producer.authority().resolve(selector).status is EvidenceResolutionStatus.CORROBORATED

    stored = producer._store.snapshots[published.snapshot.snapshot_id]
    cached = producer._store.snapshot_observation_id_sets[stored.snapshot_id]
    assert cached[0] is stored
    assert observation_id in cached[1]

    replacement = replace(
        stored,
        observation_ids=tuple(
            item for item in stored.observation_ids if item != observation_id
        ),
    )
    producer._store.snapshots[stored.snapshot_id] = replacement

    result = producer.authority().resolve(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    refreshed = producer._store.snapshot_observation_id_sets[stored.snapshot_id]
    assert refreshed[0] is replacement
    assert observation_id not in refreshed[1]
