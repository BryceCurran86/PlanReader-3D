"""Semantic opening enumeration authority regression tests.

These tests use real fitz-authored PDFs and the real SourceVisibilityProducer /
PhysicalOpeningAuthority chain.  No caller-supplied candidate list or expected
opening count is used.
"""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_generic_opening_count_authority import (
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    SEMANTIC_ENUMERATION_INCOMPLETE,
    OpeningUniverseSelector,
)
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_semantic_opening_enumeration_authority import (
    SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE,
    SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE,
    SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
    SemanticOpeningEnumerationAuthority,
    SemanticOpeningEnumerationProducer,
    SemanticOpeningEnumerationSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


SCOPE = "semantic-opening-enumeration:document"


def _draw_opening(
    page: fitz.Page,
    *,
    x0: float = 20.0,
    gap0: float = 100.0,
    gap1: float = 140.0,
    x1: float = 220.0,
    y0: float = 100.0,
    y1: float = 110.0,
) -> None:
    for first, second in (
        ((x0, y0), (gap0, y0)),
        ((gap1, y0), (x1, y0)),
        ((x0, y1), (gap0, y1)),
        ((gap1, y1), (x1, y1)),
        ((gap0, y0), (gap0, y1)),
        ((gap1, y0), (gap1, y1)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )


def _pdf(*, extra_line: bool = False) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page)
    if extra_line:
        page.draw_line(
            fitz.Point(20.0, 300.0),
            fitz.Point(300.0, 300.0),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(
    producer: SourceVisibilityProducer,
    payload: bytes,
    document_id: str,
):
    return producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )


def _enumerate(src: SourceVisibilityProducer, revision_id: str):
    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(src)
    result = producer.publish_document_scope(
        revision_id=revision_id,
        decision_scope_id=SCOPE,
    )
    return producer, result


def test_producer_surface_cannot_accept_caller_candidate_universe() -> None:
    params = set(
        inspect.signature(
            SemanticOpeningEnumerationProducer.publish_document_scope
        ).parameters
    )
    assert params == {"self", "revision_id", "decision_scope_id"}
    forbidden = {
        "candidate_ids",
        "opening_ids",
        "observation_ids",
        "expected_count",
        "schedule_count",
        "tags",
        "radius",
        "complete",
    }
    assert not (params & forbidden)


def test_authority_is_producer_owned() -> None:
    with pytest.raises(TypeError):
        SemanticOpeningEnumerationAuthority({})


def test_real_g17_support_is_grouped_into_one_semantic_opening() -> None:
    src = SourceVisibilityProducer(
        producer_method="semantic-enum-test",
        producer_version="1.0",
    )
    ingested = _ingest(src, _pdf(), "semantic-one-opening")
    producer, result = _enumerate(src, ingested.revision.revision_id)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    record = result.record
    assert len(record.physical_opening_record_ids) == 1
    assert len(record.representative_observation_ids) == 1
    assert len(record.opening_support_observation_ids) == 6
    assert record.residual_visible_observation_ids == ()
    assert record.structural_enumeration_complete is True
    assert record.physical_opening_universe_complete is False
    assert SEMANTIC_OPENING_STRUCTURAL_ENUMERATION_COMPLETE in record.reason_codes
    assert SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN in record.reason_codes

    resolved = producer.authority().resolve(
        SemanticOpeningEnumerationSelector(
            document_id=record.document_id,
            revision_id=record.revision_id,
            source_sha256=record.source_sha256,
            snapshot_id=record.snapshot_id,
            decision_scope_id=record.decision_scope_id,
        )
    )
    assert resolved == result


def test_unclassified_visible_segment_remains_residual_and_blocks_structural_complete() -> None:
    src = SourceVisibilityProducer(
        producer_method="semantic-enum-test",
        producer_version="1.0",
    )
    ingested = _ingest(src, _pdf(extra_line=True), "semantic-extra-line")
    _producer, result = _enumerate(src, ingested.revision.revision_id)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    record = result.record
    assert len(record.physical_opening_record_ids) == 1
    assert len(record.opening_support_observation_ids) == 6
    assert len(record.residual_visible_observation_ids) == 1
    assert record.structural_enumeration_complete is False
    assert record.physical_opening_universe_complete is False
    assert SEMANTIC_OPENING_RESIDUAL_SOURCE_EVIDENCE in record.reason_codes
    assert SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN in record.reason_codes


def test_unknown_revision_abstains_without_inventing_inventory() -> None:
    src = SourceVisibilityProducer(
        producer_method="semantic-enum-test",
        producer_version="1.0",
    )
    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(src)
    result = producer.publish_document_scope(
        revision_id="revision-never-ingested",
        decision_scope_id=SCOPE,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None


def test_semantic_inventory_projects_representative_member_into_completeness_but_never_seals() -> None:
    src = SourceVisibilityProducer(
        producer_method="semantic-enum-test",
        producer_version="1.0",
    )
    ingested = _ingest(src, _pdf(), "semantic-completeness-seam")
    published = src.published_snapshot_for_revision(ingested.revision.revision_id)
    assert published is not None

    authority = build_semantic_opening_inventory_completeness(
        source_visibility_producer=src,
        revision_id=ingested.revision.revision_id,
        decision_scope_id=SCOPE,
        optional_content_known_visible=True,
    )

    # The new semantic inventory is real producer-owned evidence, but V1 still
    # does not prove universal physical-opening exhaustiveness.
    assert getattr(authority, "_source_authentication_seal", None) is not (
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )

    result = authority.resolve(
        OpeningUniverseSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=SCOPE,
        )
    )
    assert result.record is not None
    assert result.record.semantic_enumeration_complete is False
    assert result.record.decision_scope_complete is False
    assert SEMANTIC_ENUMERATION_INCOMPLETE in result.record.reason_codes
    # Six raw support segments have become exactly one semantic representative.
    assert len(result.record.accounted_member_ids) == 1


def test_geometry_mutation_changes_semantic_inventory_identity() -> None:
    src = SourceVisibilityProducer(
        producer_method="semantic-enum-test",
        producer_version="1.0",
    )
    first = _ingest(src, _pdf(), "semantic-mutation")

    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, gap0=100.0, gap1=150.0)
    mutated = doc.tobytes()
    doc.close()
    second = _ingest(src, mutated, "semantic-mutation")

    _, first_result = _enumerate(src, first.revision.revision_id)
    _, second_result = _enumerate(src, second.revision.revision_id)

    assert first_result.record is not None
    assert second_result.record is not None
    assert first_result.record.record_id != second_result.record.record_id
    assert (
        first_result.record.physical_opening_record_ids
        != second_result.record.physical_opening_record_ids
    )
