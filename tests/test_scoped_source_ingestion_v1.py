"""Regression tests for immutable page-scoped source ingestion."""
from __future__ import annotations

import hashlib

import fitz
import pytest

from pb_live_ceiling_lining_integration import collect_live_ceiling_lining_claims
from pb_migration_contracts import stable_contract_id
from pb_source_observation_authority import (
    SNAPSHOT_MISMATCH,
    ObservationSelector,
    SourceObservationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _three_page_pdf() -> bytes:
    doc = fitz.open()
    try:
        for page_number in range(1, 4):
            page = doc.new_page(width=240.0, height=180.0)
            page.insert_text(
                fitz.Point(30.0, 35.0),
                f"PAGE {page_number}",
                fontsize=9.0,
            )
            page.draw_line(
                fitz.Point(30.0, 90.0),
                fitz.Point(200.0, 90.0),
                color=(0, 0, 0),
                width=1.0,
            )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _resolved_pages(producer: SourceObservationProducer, published) -> set[str]:
    authority = producer.authority()
    pages: set[str] = set()
    for observation_id in published.snapshot.observation_ids:
        result = authority.resolve(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.observation is not None
        pages.add(result.observation.page_id)
    return pages


def test_scoped_ingest_preserves_full_source_identity_and_partition_inventory() -> None:
    payload = _three_page_pdf()
    kwargs = dict(
        producer_method="scoped-source-test",
        producer_version="1.0",
    )
    full_producer = SourceObservationProducer(**kwargs)
    scoped_producer = SourceObservationProducer(**kwargs)

    full = full_producer.ingest_native_pdf_bytes(
        document_id="scope-doc",
        source_bytes=payload,
        source_locator="memory://scope-doc.pdf",
    )
    scoped = scoped_producer.ingest_native_pdf_bytes(
        document_id="scope-doc",
        source_bytes=payload,
        source_locator="memory://scope-doc.pdf",
        page_ids=("2",),
    )

    expected_sha = hashlib.sha256(payload).hexdigest()
    assert full.revision.source_sha256 == expected_sha
    assert scoped.revision.source_sha256 == expected_sha
    assert scoped.revision.revision_id == full.revision.revision_id
    assert scoped.revision.partition_ids == ("page:1", "page:2", "page:3")
    assert scoped.coverage.total_pages == 3
    assert scoped.coverage.decoded_pages == (2,)
    assert scoped.coverage.failed_pages == ()
    assert scoped.coverage.state == "partial"
    assert _resolved_pages(scoped_producer, scoped) == {"2"}
    assert scoped.snapshot.snapshot_id != full.snapshot.snapshot_id

    # Observation identity is source-derived, not changed merely because the
    # producer decoded a smaller immutable page scope.
    assert set(scoped.snapshot.observation_ids) <= set(full.snapshot.observation_ids)


def test_full_ingest_preserves_historical_snapshot_identity() -> None:
    payload = _three_page_pdf()
    producer = SourceObservationProducer(
        producer_method="historical-full-id",
        producer_version="1.0",
    )
    full = producer.ingest_native_pdf_bytes(
        document_id="full-id-doc",
        source_bytes=payload,
        source_locator="memory://full-id-doc.pdf",
    )
    expected = stable_contract_id(
        "source_snapshot",
        {
            "document_id": "full-id-doc",
            "revision_id": full.revision.revision_id,
            "source_sha256": full.revision.source_sha256,
            "producer_method": "historical-full-id",
            "producer_version": "1.0",
            "kind": "native_pdf_ingestion",
        },
        digest_chars=32,
    )
    assert full.snapshot.snapshot_id == expected
    assert full.coverage.decoded_pages == (1, 2, 3)
    assert full.coverage.state == "complete"


def test_explicit_all_pages_is_identical_to_unscoped_full_ingest() -> None:
    payload = _three_page_pdf()
    kwargs = dict(
        producer_method="explicit-all-pages",
        producer_version="1.0",
    )
    implicit = SourceObservationProducer(**kwargs).ingest_native_pdf_bytes(
        document_id="all-pages-doc",
        source_bytes=payload,
        source_locator="memory://all-pages-doc.pdf",
    )
    explicit = SourceObservationProducer(**kwargs).ingest_native_pdf_bytes(
        document_id="all-pages-doc",
        source_bytes=payload,
        source_locator="memory://all-pages-doc.pdf",
        page_ids=("3", "1", "2", "2"),
    )
    assert explicit == implicit


def test_same_scope_replays_but_scope_change_fails_closed() -> None:
    payload = _three_page_pdf()
    producer = SourceObservationProducer(
        producer_method="fixed-scope-test",
        producer_version="1.0",
    )
    first = producer.ingest_native_pdf_bytes(
        document_id="fixed-scope-doc",
        source_bytes=payload,
        source_locator="memory://fixed-scope-doc.pdf",
        page_ids=("2",),
    )
    replay = producer.ingest_native_pdf_bytes(
        document_id="fixed-scope-doc",
        source_bytes=payload,
        source_locator="memory://fixed-scope-doc.pdf",
        page_ids=("2", "2"),
    )
    assert replay == first

    with pytest.raises(ValueError, match=SNAPSHOT_MISMATCH):
        producer.ingest_native_pdf_bytes(
            document_id="fixed-scope-doc",
            source_bytes=payload,
            source_locator="memory://fixed-scope-doc.pdf",
            page_ids=("1",),
        )


@pytest.mark.parametrize("page_ids", [(), ("0",), ("4",), ("02",), ("x",)])
def test_invalid_or_empty_source_page_scope_fails_closed(page_ids) -> None:
    producer = SourceObservationProducer(
        producer_method="invalid-scope-test",
        producer_version="1.0",
    )
    with pytest.raises(ValueError):
        producer.ingest_native_pdf_bytes(
            document_id="invalid-scope-doc",
            source_bytes=_three_page_pdf(),
            source_locator="memory://invalid-scope-doc.pdf",
            page_ids=page_ids,
        )


def test_visibility_derives_receipts_only_from_decoded_source_pages() -> None:
    payload = _three_page_pdf()
    producer = SourceVisibilityProducer(
        producer_method="scoped-visibility-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="scoped-visibility-doc",
        source_bytes=payload,
        source_locator="memory://scoped-visibility-doc.pdf",
        page_ids=("2",),
    )

    assert published.coverage.total_pages == 3
    assert published.coverage.decoded_pages == (2,)
    assert published.coverage.state == "partial"
    assert published.visible_observation_ids
    assert published.text_observation_ids

    source = producer._producer.authority()  # test-only integrity inspection
    seen_pages: set[str] = set()
    for observation_id in published.snapshot.observation_ids:
        result = source.resolve(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.observation is not None
        seen_pages.add(result.observation.page_id)
    assert seen_pages == {"2"}

    assert (
        producer.optional_content_state_for_scope(
            published.revision.revision_id,
            page_ids=("2",),
        )
        == "known_visible"
    )
    assert (
        producer.optional_content_state_for_scope(
            published.revision.revision_id,
            page_ids=("1",),
        )
        == "unresolved"
    )


def test_live_ceiling_forwards_exact_selected_pages_to_source_ingest(
    tmp_path,
    monkeypatch,
) -> None:
    payload = _three_page_pdf()
    path = tmp_path / "three-pages.pdf"
    path.write_bytes(payload)

    seen: list[tuple[str, ...] | None] = []
    original = SourceVisibilityProducer.ingest_native_pdf_bytes

    def wrapped(self, **kwargs):
        page_ids = kwargs.get("page_ids")
        seen.append(None if page_ids is None else tuple(page_ids))
        return original(self, **kwargs)

    monkeypatch.setattr(
        SourceVisibilityProducer,
        "ingest_native_pdf_bytes",
        wrapped,
    )

    collect_live_ceiling_lining_claims(path, pages=(1,))

    assert seen == [("2",)]
