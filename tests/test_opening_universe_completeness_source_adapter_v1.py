"""Fail-closed tests for authenticated primitive coverage.

The source adapter may authenticate raw visible PDF coverage, but it must not
claim that raw segments are a complete semantic physical-opening universe.
"""
from __future__ import annotations

import fitz

from pb_generic_opening_count_authority import (
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    SEMANTIC_ENUMERATION_INCOMPLETE,
    OpeningUniverseSelector,
)
from pb_opening_universe_completeness_source_adapter import (
    build_source_authenticated_opening_universe_completeness,
)
from pb_source_visibility_authority import SourceVisibilityProducer

SCOPE = "completeness-scope:page-1"


def _draw_opening(
    page: fitz.Page,
    *,
    x0: float,
    gap0: float,
    gap1: float,
    x1: float,
    y0: float,
    y1: float,
) -> None:
    """Draw one real six-segment G17 opening pattern."""
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


def _tag_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
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


def _resolve(authority, published, revision_id):
    return authority.resolve(
        OpeningUniverseSelector(
            document_id=published.revision.document_id,
            revision_id=revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=SCOPE,
        )
    )


def test_real_source_decode_does_not_claim_semantic_opening_completeness() -> None:
    """Six support segments for one opening are not six semantic openings."""
    src = SourceVisibilityProducer(
        producer_method="completeness-adapter-test",
        producer_version="1.0",
    )
    ingestion = _ingest(src, _tag_pdf(), "doc-real")
    published = src.published_snapshot_for_revision(ingestion.revision.revision_id)
    assert published is not None

    authority = build_source_authenticated_opening_universe_completeness(
        source_visibility_producer=src,
        revision_id=ingestion.revision.revision_id,
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        page_ids=("1",),
        optional_content_known_visible=True,
    )

    # Primitive coverage never earns the commercial semantic-completeness seal.
    assert getattr(authority, "_source_authentication_seal", None) is not (
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )

    result = _resolve(authority, published, ingestion.revision.revision_id)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.semantic_enumeration_complete is False
    assert result.record.decision_scope_complete is False
    assert SEMANTIC_ENUMERATION_INCOMPLETE in result.record.reason_codes
    assert result.record.accounted_member_ids == ()


def test_ordinary_non_opening_line_cannot_become_semantic_opening_member() -> None:
    src = SourceVisibilityProducer(
        producer_method="completeness-adapter-test",
        producer_version="1.0",
    )
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
    )
    # Unrelated visible line: authenticated primitive, not an opening.
    page.draw_line(
        fitz.Point(20.0, 300.0),
        fitz.Point(300.0, 300.0),
        color=(0, 0, 0),
        width=1,
    )
    payload = doc.tobytes()
    doc.close()

    ingestion = _ingest(src, payload, "doc-extra-line")
    published = src.published_snapshot_for_revision(ingestion.revision.revision_id)
    assert published is not None

    authority = build_source_authenticated_opening_universe_completeness(
        source_visibility_producer=src,
        revision_id=ingestion.revision.revision_id,
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        page_ids=("1",),
        optional_content_known_visible=True,
    )
    result = _resolve(authority, published, ingestion.revision.revision_id)
    assert result.record is not None
    assert result.record.semantic_enumeration_complete is False
    assert result.record.accounted_member_ids == ()


def test_optional_content_default_remains_fail_closed() -> None:
    src = SourceVisibilityProducer(
        producer_method="completeness-adapter-test",
        producer_version="1.0",
    )
    ingestion = _ingest(src, _tag_pdf(), "doc-default")
    published = src.published_snapshot_for_revision(ingestion.revision.revision_id)
    assert published is not None

    authority = build_source_authenticated_opening_universe_completeness(
        source_visibility_producer=src,
        revision_id=ingestion.revision.revision_id,
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        page_ids=("1",),
    )
    result = _resolve(authority, published, ingestion.revision.revision_id)
    assert result.record is not None
    assert result.record.decision_scope_complete is False
    assert "opening_universe_optional_content_unresolved" in result.record.reason_codes


def test_no_published_snapshot_resolves_unavailable_and_never_seals() -> None:
    src = SourceVisibilityProducer(
        producer_method="completeness-adapter-test",
        producer_version="1.0",
    )
    authority = build_source_authenticated_opening_universe_completeness(
        source_visibility_producer=src,
        revision_id="revision-never-ingested",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        page_ids=("1",),
        optional_content_known_visible=True,
    )
    assert getattr(authority, "_source_authentication_seal", None) is not (
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )
    result = authority.resolve(
        OpeningUniverseSelector(
            document_id="doc-x",
            revision_id="revision-never-ingested",
            source_sha256="s" * 64,
            snapshot_id="snap-x",
            decision_scope_id=SCOPE,
        )
    )
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.record is None
