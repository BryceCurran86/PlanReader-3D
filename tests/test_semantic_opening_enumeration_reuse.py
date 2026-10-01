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


def test_semantic_producer_reuses_snapshot_bound_physical_authority() -> None:
    source, revision_id = _ingest("semantic-reuse")
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
    assert len(producer._physical_opening_authorities) == 1
    shared = next(iter(producer._physical_opening_authorities.values()))
    assert shared is source.physical_opening_authority()
    assert shared is source._physical_opening_authority_cache


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


def test_semantic_result_cache_does_not_hide_scope_equivocation() -> None:
    source, revision_id = _ingest("semantic-scope-equivocation")
    producer = semantic.SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="shared-scope-id",
        page_ids=("1",),
    )

    with pytest.raises(RuntimeError):
        producer.publish_page_scope(
            revision_id=revision_id,
            decision_scope_id="shared-scope-id",
            page_ids=("2",),
        )


def test_same_snapshot_pages_reuse_derivation_across_decision_scopes(
    monkeypatch,
) -> None:
    source, revision_id = _ingest("semantic-cross-scope-cache")
    producer = semantic.SemanticOpeningEnumerationProducer.from_source_visibility_producer(
        source
    )
    first = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="global-wrapper-scope",
        page_ids=("1", "2"),
    )
    assert first.record is not None

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("physical opening derivation was recomputed across scopes")

    monkeypatch.setattr(
        semantic.PhysicalOpeningAuthority,
        "classify_disposition",
        fail_if_recomputed,
    )
    monkeypatch.setattr(
        semantic.PhysicalOpeningAuthority,
        "assess_visible_candidate_closure",
        fail_if_recomputed,
    )

    second = producer.publish_page_scope(
        revision_id=revision_id,
        decision_scope_id="page-owned-wall-scope",
        page_ids=("1", "2"),
    )
    assert second.record is not None
    assert second.status == first.status
    assert second.reason_codes == first.reason_codes
    assert second.record.decision_scope_id == "page-owned-wall-scope"
    assert second.record.record_id != first.record.record_id
    assert (
        second.record.visible_observation_ids
        == first.record.visible_observation_ids
    )
    assert (
        second.record.physical_opening_record_ids
        == first.record.physical_opening_record_ids
    )
    assert (
        second.record.representative_observation_ids
        == first.record.representative_observation_ids
    )
    assert (
        second.record.opening_support_observation_ids
        == first.record.opening_support_observation_ids
    )
    assert (
        second.record.residual_visible_observation_ids
        == first.record.residual_visible_observation_ids
    )
    assert (
        second.record.conflict_observation_ids
        == first.record.conflict_observation_ids
    )
    assert (
        second.record.structural_enumeration_complete
        == first.record.structural_enumeration_complete
    )
    assert (
        second.record.physical_opening_universe_complete
        == first.record.physical_opening_universe_complete
    )
