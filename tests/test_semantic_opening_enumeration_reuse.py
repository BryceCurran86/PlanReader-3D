from __future__ import annotations

import fitz
import pytest

import pb_semantic_opening_enumeration_authority as semantic
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _two_page_pdf() -> bytes:
    doc = fitz.open()
    try:
        first = doc.new_page(width=320.0, height=240.0)
        first.draw_line((20.0, 60.0), (280.0, 60.0))
        second = doc.new_page(width=320.0, height=240.0)
        second.draw_line((20.0, 100.0), (280.0, 100.0))
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _ingest(document_id: str) -> tuple[SourceVisibilityProducer, str]:
    source = SourceVisibilityProducer(
        producer_method="semantic-opening-reuse-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=_two_page_pdf(),
        source_locator=f"memory://{document_id}.pdf",
    )
    return source, published.revision.revision_id


def test_semantic_producer_reuses_snapshot_bound_physical_authority(
    monkeypatch,
) -> None:
    source, revision_id = _ingest("semantic-reuse")
    original = semantic.PhysicalOpeningAuthority
    constructions = 0

    def counted(authority):
        nonlocal constructions
        constructions += 1
        return original(authority)

    monkeypatch.setattr(semantic, "PhysicalOpeningAuthority", counted)

    producer = semantic.SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    first = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="all-pages",
        page_ids=("1", "2"),
    )
    page_one = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="page-1",
        page_ids=("1",),
    )
    page_two = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="page-2",
        page_ids=("2",),
    )

    assert first is not None
    assert page_one is not None
    assert page_two is not None
    assert constructions == 1


def test_semantic_scope_result_is_returned_from_exact_snapshot_cache(
    monkeypatch,
) -> None:
    source, revision_id = _ingest("semantic-result-cache")
    producer = semantic.SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    first = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="cached-scope",
        page_ids=("1", "2"),
    )

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("physical opening disposition was recomputed")

    monkeypatch.setattr(
        semantic.PhysicalOpeningAuthority,
        "classify_disposition",
        fail_if_recomputed,
    )

    second = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="cached-scope",
        page_ids=("1", "2"),
    )
    assert second == first


def test_completeness_adapter_rejects_semantic_producer_from_other_source() -> None:
    first_source, first_revision = _ingest("semantic-source-a")
    second_source, _ = _ingest("semantic-source-b")
    foreign = semantic.SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        second_source
    )

    with pytest.raises(ValueError):
        build_semantic_opening_inventory_completeness(
            source_visibility_producer=first_source,
            revision_id=first_revision,
            decision_scope_id="foreign-producer",
            page_ids=("1",),
            _semantic_opening_producer=foreign,
        )
