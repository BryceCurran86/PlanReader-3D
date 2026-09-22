from __future__ import annotations

import fitz

from pb_live_wall_opening_authority_composition import (
    LIVE_WALL_OPENING_COMPOSITION_RESOLVED,
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer


def _host_fixture_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        shape = page.new_shape()
        for start, end in (
            ((20.0, 80.0), (120.0, 80.0)),
            ((160.0, 80.0), (280.0, 80.0)),
            ((20.0, 100.0), (120.0, 100.0)),
            ((160.0, 100.0), (280.0, 100.0)),
            ((120.0, 80.0), (120.0, 100.0)),
            ((160.0, 80.0), (160.0, 100.0)),
        ):
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


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


def _ingest(data: bytes, document_id: str):
    source = SourceVisibilityProducer(
        producer_method="live-wall-opening-composition-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=data,
        source_locator=f"memory://{document_id}.pdf",
    )
    return source, published


def test_composer_resolves_source_owned_opening_host_without_caller_geometry() -> None:
    source, published = _ingest(_host_fixture_pdf(), "host-composition-positive")

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )

    assert composition.status is EvidenceResolutionStatus.CORROBORATED
    assert LIVE_WALL_OPENING_COMPOSITION_RESOLVED in composition.reason_codes
    assert len(composition.wall_scopes) == 1
    assert composition.wall_scopes[0].scope_complete is True
    assert composition.wall_scopes[0].wall_candidate_ids
    assert composition.opening_bindings
    assert all(
        trace.status is EvidenceResolutionStatus.CORROBORATED
        and trace.record_id is not None
        and trace.host_wall_id is not None
        and trace.member_wall_candidate_ids
        for trace in composition.opening_bindings
    )

    for trace in composition.opening_bindings:
        selector = composition.binding_selectors[trace.opening_identity_id]
        resolved = composition.opening_host_binding_authority.resolve(selector)
        assert resolved.status is EvidenceResolutionStatus.CORROBORATED
        assert resolved.record is not None
        assert resolved.record.record_id == trace.record_id


def test_composer_does_not_materialize_unselected_wall_page() -> None:
    source, published = _ingest(_two_page_pdf(), "host-composition-page-scope")

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("2",),
    )

    assert composition.page_ids == ("2",)
    assert [trace.page_id for trace in composition.wall_scopes] == ["2"]
