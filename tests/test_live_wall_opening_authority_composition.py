from __future__ import annotations

import fitz

from pb_live_wall_opening_authority_composition import (
    LIVE_WALL_OPENING_COMPOSITION_RESOLVED,
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import OpeningUniverseSelector
from pb_physical_opening_authority import PhysicalOpeningAuthority
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




def _two_page_host_pdf() -> bytes:
    doc = fitz.open()
    try:
        doc.new_page(width=320.0, height=240.0)
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


def test_composer_reuses_wall_producer_opening_authority_cache(monkeypatch) -> None:
    source, published = _ingest(_host_fixture_pdf(), "host-composition-cache-reuse")

    original = PhysicalOpeningAuthority.from_source_visibility_producer
    constructions = 0

    def counted(cls, source_visibility_producer):
        nonlocal constructions
        constructions += 1
        return original(source_visibility_producer)

    monkeypatch.setattr(
        PhysicalOpeningAuthority,
        "from_source_visibility_producer",
        classmethod(counted),
    )

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )

    assert composition.physical_opening_authority is not None
    assert constructions == 1


def test_composer_resolves_source_owned_opening_host_without_caller_geometry() -> None:
    source, published = _ingest(_host_fixture_pdf(), "host-composition-positive")

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )

    assert composition.status is EvidenceResolutionStatus.CORROBORATED
    assert LIVE_WALL_OPENING_COMPOSITION_RESOLVED in composition.reason_codes
    assert (
        composition.opening_universe_result.status
        is EvidenceResolutionStatus.CORROBORATED
    )
    assert composition.opening_universe_result.decision_scope_complete is True
    assert composition.opening_universe_result.record is not None
    universe_record = composition.opening_universe_result.record
    resolved_universe = composition.opening_universe_completeness_authority.resolve(
        OpeningUniverseSelector(
            document_id=universe_record.document_id,
            revision_id=universe_record.revision_id,
            source_sha256=universe_record.source_sha256,
            snapshot_id=universe_record.snapshot_id,
            decision_scope_id=universe_record.decision_scope_id,
        )
    )
    assert resolved_universe == composition.opening_universe_result

    page_universe = composition.opening_universe_results["1"]
    assert page_universe.status is EvidenceResolutionStatus.CORROBORATED
    assert page_universe.decision_scope_complete is True
    assert page_universe.record is not None
    assert page_universe.record.decision_scope_id == "wall-source:page-1"
    resolved_page_universe = (
        composition.opening_universe_completeness_authorities["1"].resolve(
            OpeningUniverseSelector(
                document_id=page_universe.record.document_id,
                revision_id=page_universe.record.revision_id,
                source_sha256=page_universe.record.source_sha256,
                snapshot_id=page_universe.record.snapshot_id,
                decision_scope_id="wall-source:page-1",
            )
        )
    )
    assert resolved_page_universe == page_universe
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
    assert composition.host_frames
    assert all(
        trace.status is EvidenceResolutionStatus.CORROBORATED
        and trace.record_id is not None
        and trace.host_wall_id is not None
        and trace.whole_wall_candidate_ids
        for trace in composition.host_frames
    )
    for trace in composition.host_frames:
        selector = composition.host_frame_selectors[trace.opening_identity_id]
        resolved = composition.opening_host_frame_authority.resolve(selector)
        assert resolved.status is EvidenceResolutionStatus.CORROBORATED
        assert resolved.evidence is not None
        assert resolved.evidence.record_id == trace.record_id

    for trace in composition.opening_bindings:
        selector = composition.binding_selectors[trace.opening_identity_id]
        assert selector.decision_scope_id == "wall-source:page-1"
        assert (
            composition.opening_universe_results[selector.page_id]
            .record.decision_scope_id
            == selector.decision_scope_id
        )
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
    if composition.opening_universe_result.record is not None:
        assert composition.opening_universe_result.record.page_ids == ("2",)
    assert set(composition.opening_universe_results) == {"2"}
    assert composition.opening_universe_results["2"].record is not None
    assert (
        composition.opening_universe_results["2"].record.decision_scope_id
        == "wall-source:page-2"
    )



def test_composer_refreshes_snapshot_after_wall_raster_augmentation(monkeypatch) -> None:
    source, published = _ingest(_host_fixture_pdf(), "host-composition-refresh")

    original_snapshot_id = published.snapshot.snapshot_id
    original_from_source = (
        __import__(
            "pb_live_wall_opening_authority_composition",
            fromlist=["PhysicalWallCandidateProducer"],
        ).PhysicalWallCandidateProducer.from_source_visibility_producer
    )
    seen: dict[str, str] = {}

    def wrapped_from_source_visibility_producer(
        source_visibility_producer,
        *,
        page_ids=None,
    ):
        producer = original_from_source(
            source_visibility_producer,
            page_ids=page_ids,
        )
        refreshed = source_visibility_producer.published_snapshot_for_revision(
            published.revision.revision_id
        )
        assert refreshed is not None
        seen["snapshot_id"] = refreshed.snapshot.snapshot_id
        return producer

    monkeypatch.setattr(
        "pb_live_wall_opening_authority_composition."
        "PhysicalWallCandidateProducer.from_source_visibility_producer",
        wrapped_from_source_visibility_producer,
    )

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )

    refreshed = source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert refreshed is not None
    assert seen["snapshot_id"] == refreshed.snapshot.snapshot_id
    assert composition.semantic_enumeration_result.record is not None
    assert composition.semantic_enumeration_result.record.snapshot_id == (
        refreshed.snapshot.snapshot_id
    )
    assert composition.opening_universe_result.record is not None
    assert composition.opening_universe_result.record.snapshot_id == (
        refreshed.snapshot.snapshot_id
    )
    for trace in composition.wall_scopes:
        selector = composition.physical_wall_candidate_authority.selector_for_decision_scope(
            document_id=refreshed.revision.document_id,
            revision_id=refreshed.revision.revision_id,
            source_sha256=refreshed.revision.source_sha256,
            snapshot_id=refreshed.snapshot.snapshot_id,
            page_id=trace.page_id,
            decision_scope_id=f"wall-source:page-{trace.page_id}",
        )
        assert selector is not None
    if refreshed.snapshot.snapshot_id != original_snapshot_id:
        assert (
            composition.opening_universe_result.record.snapshot_id
            != original_snapshot_id
        )



def test_composer_authorizes_successfully_decoded_scoped_page() -> None:
    source = SourceVisibilityProducer(
        producer_method="live-wall-opening-composition-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="host-composition-scoped-page",
        source_bytes=_two_page_host_pdf(),
        source_locator="memory://host-composition-scoped-page.pdf",
        page_ids=("2",),
    )
    assert published.coverage.state == "partial"
    assert published.coverage.decoded_pages == (2,)
    assert published.coverage.failed_pages == ()

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("2",),
    )

    assert len(composition.wall_scopes) == 1
    wall_scope = composition.wall_scopes[0]
    assert wall_scope.page_id == "2"
    assert wall_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert wall_scope.scope_complete is True
    assert wall_scope.wall_candidate_ids
