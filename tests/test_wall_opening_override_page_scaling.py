"""Page addressing must not multiply document-wide opening proof work."""
from __future__ import annotations

from collections import Counter

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _source(page_count=8, *, reverse=False, offset=0.0):
    doc = fitz.open()
    try:
        for index in range(page_count):
            page = doc.new_page(width=500, height=500)
            y = 100.0 + index * 3.0 + offset
            lines = [
                ((40, y), (160, y)), ((200, y), (340, y)),
                ((40, y + 20), (160, y + 20)),
                ((200, y + 20), (340, y + 20)),
                ((160, y), (160, y + 20)),
                ((200, y), (200, y + 20)),
            ]
            shape = page.new_shape()
            for a, b in reversed(lines) if reverse else lines:
                shape.draw_line(a, b)
            shape.finish(width=1)
            shape.commit()
        payload = doc.tobytes(garbage=4, deflate=True)
    finally:
        doc.close()
    source = SourceVisibilityProducer(producer_method="page-scaling-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="page-scaling-test", source_bytes=payload,
        source_locator="memory://page-scaling-test.pdf")
    return source, published


def _resolve(authority, published, page):
    return authority.resolve_scope(PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=str(page), decision_scope_id=f"wall-source:page-{page}"))


@pytest.mark.parametrize("reverse,offset", [(False, 0.0), (True, 37.0)])
def test_each_source_observation_is_proven_on_its_own_page_once(monkeypatch, reverse, offset):
    source, published = _source(reverse=reverse, offset=offset)
    original = PhysicalOpeningAuthority.prove_existence
    calls = Counter()

    def counted(self, selector):
        calls[selector.observation_id] += 1
        return original(self, selector)

    monkeypatch.setattr(PhysicalOpeningAuthority, "prove_existence", counted)
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    refreshed = source.published_snapshot_for_revision(published.revision.revision_id)
    assert refreshed is not None
    assert set(calls) == set(refreshed.visible_observation_ids)
    assert set(calls.values()) == {1}
    for page in range(1, 9):
        result = _resolve(authority, refreshed, page)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert len(result.records) == 6
        # Two corroborated face pairs and two distinct jambs survive.
        assert len(result.equivalence.equivalence_groups) == 2
        assert len(result.equivalence.representative_wall_ids) == 4


def test_repeated_scoped_builds_preserve_the_complete_authority_result():
    source, published = _source(page_count=3)
    complete = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    refreshed = source.published_snapshot_for_revision(published.revision.revision_id)
    assert refreshed is not None
    for page in (3, 1, 2, 1):
        scoped = PhysicalWallCandidateProducer.from_source_visibility_producer(
            source, page_ids=(str(page),)).authority()
        assert _resolve(scoped, refreshed, page) == _resolve(complete, refreshed, page)


def test_new_revision_never_reuses_previous_opening_proofs():
    source, first = _source(page_count=2)
    first_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    other, other_published = _source(page_count=2, offset=43)
    store = other._producer._store
    payload = store.source_bytes_by_revision[other_published.revision.revision_id]
    second = source.ingest_native_pdf_bytes(
        document_id=first.revision.document_id, source_bytes=payload,
        source_locator="memory://page-scaling-test.pdf")
    with pytest.raises(ValueError, match="stale_revision"):
        PhysicalWallCandidateProducer.from_source_visibility_producer(source)
    second_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(other).authority()
    assert first.revision.revision_id != second.revision.revision_id
    assert _resolve(first_authority, second, 1).status is EvidenceResolutionStatus.ABSTAINED
    first_result = _resolve(first_authority, first, 1)
    second_result = _resolve(second_authority, other_published, 1)
    assert first_result.records != second_result.records
    assert len(first_result.records) == len(second_result.records) == 6
