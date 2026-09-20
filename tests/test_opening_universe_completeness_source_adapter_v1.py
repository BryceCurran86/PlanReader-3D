"""Tests for pb_opening_universe_completeness_source_adapter.py.

build_source_authenticated_opening_universe_completeness() is the one lawful
production path to an OpeningUniverseCompletenessAuthority that
GenericOpeningCountAuthority will accept (it gates on a private
`_source_authentication_seal`). Real PDF ingestion (fitz-authored synthetic
drawing, real vector geometry -- not mocks) exercises the real
source-decode -> visibility-classification -> universe-enumeration chain.
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


def _draw_opening(page: fitz.Page, *, x0: float, gap0: float, gap1: float, x1: float, y0: float, y1: float) -> None:
    """One wall run with a jamb-bounded gap -- the real 6-segment G17
    VISIBLE existence pattern (two wall faces each continuing on both sides
    of one gap, plus two jambs)."""
    for first, second in (
        ((x0, y0), (gap0, y0)),
        ((gap1, y0), (x1, y0)),
        ((x0, y1), (gap0, y1)),
        ((gap1, y1), (x1, y1)),
        ((gap0, y0), (gap0, y1)),
        ((gap1, y0), (gap1, y1)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)


def _tag_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    _draw_opening(page, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest(producer: SourceVisibilityProducer, payload: bytes, document_id: str):
    return producer.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=payload, source_locator=f"memory://{document_id}.pdf",
    )


def test_real_source_decode_is_authenticated_but_semantically_incomplete() -> None:
    src = SourceVisibilityProducer(producer_method="completeness-adapter-test", producer_version="1.0")
    payload = _tag_pdf()
    ingestion = _ingest(src, payload, "doc-real")
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

    assert getattr(authority, "_source_authentication_seal", None) is (
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )

    res = authority.resolve(
        OpeningUniverseSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=SCOPE,
        )
    )
    # Six raw G17 support segments are authenticated source primitives, not
    # six semantic opening instances. Source authentication alone must never
    # turn raw primitive equality into commercial opening completeness.
    assert res.status is not EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.source_decode_complete is True
    assert res.record.semantic_enumeration_complete is False
    assert res.record.decision_scope_complete is False
    assert SEMANTIC_ENUMERATION_INCOMPLETE in res.record.reason_codes
    assert len(res.record.accounted_member_ids) == 6


def test_optional_content_defaults_to_unresolved_and_fails_closed() -> None:
    """Caller must explicitly assert optional_content_known_visible=True;
    the default must never silently claim completeness."""
    src = SourceVisibilityProducer(producer_method="completeness-adapter-test", producer_version="1.0")
    payload = _tag_pdf()
    ingestion = _ingest(src, payload, "doc-default")
    published = src.published_snapshot_for_revision(ingestion.revision.revision_id)
    assert published is not None

    authority = build_source_authenticated_opening_universe_completeness(
        source_visibility_producer=src,
        revision_id=ingestion.revision.revision_id,
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        page_ids=("1",),
        # optional_content_known_visible left at its False default.
    )
    res = authority.resolve(
        OpeningUniverseSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=SCOPE,
        )
    )
    assert res.record is not None
    assert res.record.decision_scope_complete is False
    assert "opening_universe_optional_content_unresolved" in res.record.reason_codes


def test_no_published_snapshot_still_seals_but_resolves_unavailable() -> None:
    """A revision_id with nothing published for it must fail closed when
    resolved -- the seal certifies the DERIVATION PATH was lawful, not that
    a complete universe was found."""
    src = SourceVisibilityProducer(producer_method="completeness-adapter-test", producer_version="1.0")
    authority = build_source_authenticated_opening_universe_completeness(
        source_visibility_producer=src,
        revision_id="revision-never-ingested",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        page_ids=("1",),
        optional_content_known_visible=True,
    )
    assert getattr(authority, "_source_authentication_seal", None) is (
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )
    res = authority.resolve(
        OpeningUniverseSelector(
            document_id="doc-x",
            revision_id="revision-never-ingested",
            source_sha256="s" * 64,
            snapshot_id="snap-x",
            decision_scope_id=SCOPE,
        )
    )
    assert res.status is not EvidenceResolutionStatus.CORROBORATED
    assert res.record is None


def test_page_scoping_excludes_geometry_on_other_pages() -> None:
    """Only observations on the requested page_ids are accounted for."""
    src = SourceVisibilityProducer(producer_method="completeness-adapter-test", producer_version="1.0")
    doc = fitz.open()
    page1 = doc.new_page(width=700, height=650)
    _draw_opening(page1, x0=20.0, gap0=100.0, gap1=140.0, x1=220.0, y0=100.0, y1=110.0)
    page2 = doc.new_page(width=700, height=650)
    _draw_opening(page2, x0=20.0, gap0=300.0, gap1=340.0, x1=420.0, y0=300.0, y1=310.0)
    payload = doc.tobytes()
    doc.close()

    ingestion = _ingest(src, payload, "doc-multipage")
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
    res = authority.resolve(
        OpeningUniverseSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            decision_scope_id=SCOPE,
        )
    )
    assert res.record is not None
    assert res.record.semantic_enumeration_complete is False
    assert res.record.decision_scope_complete is False
    assert SEMANTIC_ENUMERATION_INCOMPLETE in res.record.reason_codes
    assert len(res.record.accounted_member_ids) == 6
    for member_id in res.record.accounted_member_ids:
        assert member_id.strip()
