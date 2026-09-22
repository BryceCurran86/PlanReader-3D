from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE,
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_observation_authority import SourceObservationProducer
from pb_source_visibility_authority import SourceVisibilityProducer


def _rectangle_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=240, height=240)
    for a, b in (
        ((100, 100), (140, 100)),
        ((100, 110), (140, 110)),
        ((100, 100), (100, 110)),
        ((140, 100), (140, 110)),
    ):
        page.draw_line(a, b, color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _two_blank_pages() -> bytes:
    doc = fitz.open()
    doc.new_page(width=240, height=240)
    doc.new_page(width=240, height=240)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_native_visibility_uses_one_batch_not_repeated_snapshot_clones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original_batch = SourceObservationProducer.publish_derived_observations

    def wrapped_batch(self, **kwargs):
        calls.append(len(tuple(kwargs["observations"])))
        return original_batch(self, **kwargs)

    def forbidden_single(self, **kwargs):
        raise AssertionError("native visibility must not clone one snapshot per segment")

    monkeypatch.setattr(
        SourceObservationProducer,
        "publish_derived_observations",
        wrapped_batch,
    )
    monkeypatch.setattr(
        SourceObservationProducer,
        "publish_derived_observation",
        forbidden_single,
    )

    producer = SourceVisibilityProducer(
        producer_method="batch-native-visibility-test",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="batch-native-visibility",
        source_bytes=_rectangle_pdf(),
        source_locator="memory://batch-native-visibility.pdf",
    )

    assert len(published.visible_observation_ids) == 4
    assert calls == [4]
    authority = producer.authority()
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(
            __import__("pb_source_observation_authority").ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED


def test_page_scoped_wall_candidate_factory_exposes_only_addressed_page() -> None:
    source = SourceVisibilityProducer(
        producer_method="page-scoped-wall-factory-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="page-scoped-wall-factory",
        source_bytes=_two_blank_pages(),
        source_locator="memory://page-scoped-wall-factory.pdf",
    )

    authority = PhysicalWallCandidateProducer.from_source_visibility_producer_for_pages(
        source,
        page_ids=("2",),
    ).authority()

    selected = authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="2",
            decision_scope_id="wall-source:page-2",
        )
    )
    assert selected.status is EvidenceResolutionStatus.CORROBORATED
    assert selected.scope_complete is True

    unrequested = authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            decision_scope_id="wall-source:page-1",
        )
    )
    assert unrequested.status is EvidenceResolutionStatus.ABSTAINED
    assert unrequested.reason_codes == (PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE,)


def test_page_scoped_wall_candidate_factory_rejects_undecoded_page() -> None:
    source = SourceVisibilityProducer(
        producer_method="page-scoped-wall-factory-invalid-test",
        producer_version="1",
    )
    source.ingest_native_pdf_bytes(
        document_id="page-scoped-wall-factory-invalid",
        source_bytes=_two_blank_pages(),
        source_locator="memory://page-scoped-wall-factory-invalid.pdf",
    )
    with pytest.raises(ValueError, match=PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE):
        PhysicalWallCandidateProducer.from_source_visibility_producer_for_pages(
            source,
            page_ids=("3",),
        )
