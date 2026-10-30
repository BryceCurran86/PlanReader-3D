"""Cached scale publication authenticates the same source gate as a fresh writer."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_scale_authority import (
    PHYSICAL_SCALE_SCOPE_UNAVAILABLE,
    PHYSICAL_SCALE_SOURCE_INTEGRITY_FAILURE,
    PhysicalScaleProducer,
)
from test_physical_scale_page_input_index import _multi_page_scale_pdf, _selector, _source


def _published_scale():
    source, published = _source(1)
    producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    selector = _selector(published, "1")
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    return source, published, producer, selector, result


def test_warm_scale_cannot_publish_an_old_revision_while_fresh_writer_abstains():
    source, published, producer, selector, historical = _published_scale()
    following = source.ingest_native_pdf_bytes(
        document_id=published.revision.document_id,
        source_bytes=_multi_page_scale_pdf(2), source_locator="memory://next-revision.pdf")
    assert following.revision.revision_id != published.revision.revision_id
    actual = producer.publish_scope(selector)
    fresh = PhysicalScaleProducer.from_source_visibility_producer(source).publish_scope(selector)
    assert actual == fresh
    assert actual.status is EvidenceResolutionStatus.ABSTAINED and actual.evidence is None
    assert actual.reason_codes == (PHYSICAL_SCALE_SCOPE_UNAVAILABLE,)
    # Source rejection does not rewrite historical signed evidence.
    assert producer._results[selector.key] == historical
    current = producer.publish_scope(_selector(following, "1"))
    assert current.status is EvidenceResolutionStatus.CORROBORATED
    assert current.evidence.selector.revision_id == following.revision.revision_id


@pytest.mark.parametrize("replacement", [None, b"changed original source"])
def test_missing_or_changed_original_bytes_cannot_reuse_positive_cache(replacement):
    source, published, producer, selector, historical = _published_scale()
    payloads = source._producer._store.source_bytes_by_revision
    original = payloads[published.revision.revision_id]
    if replacement is None:
        del payloads[published.revision.revision_id]
    else:
        payloads[published.revision.revision_id] = replacement
    with pytest.raises(RuntimeError, match=PHYSICAL_SCALE_SOURCE_INTEGRITY_FAILURE):
        producer.publish_scope(selector)
    with pytest.raises(RuntimeError, match=PHYSICAL_SCALE_SOURCE_INTEGRITY_FAILURE):
        PhysicalScaleProducer.from_source_visibility_producer(source).publish_scope(selector)
    assert producer._results[selector.key] == historical
    payloads[published.revision.revision_id] = original
    assert producer.publish_scope(selector) == historical


def test_failed_requested_page_blocks_warm_and_cold_publication_without_rewriting_history(monkeypatch):
    source, published, producer, selector, historical = _published_scale()
    failed = replace(published, coverage=replace(published.coverage, failed_pages=(1,)))
    with monkeypatch.context() as patch:
        patch.setattr(source, "published_snapshot_for_revision", lambda revision: failed)
        actual = producer.publish_scope(selector)
        fresh = PhysicalScaleProducer.from_source_visibility_producer(source).publish_scope(selector)
        assert actual == fresh and actual.status is EvidenceResolutionStatus.ABSTAINED
        assert actual.reason_codes == (PHYSICAL_SCALE_SCOPE_UNAVAILABLE,)
        assert actual.evidence is None
        assert producer._results[selector.key] == historical
    assert producer.publish_scope(selector) == historical


def test_healthy_cache_still_avoids_geometry_work_and_retains_original_lineage(monkeypatch):
    source, published, producer, selector, historical = _published_scale()
    original_inputs = producer._revision_inputs
    calls = []

    def checked(request):
        calls.append(request)
        return original_inputs(request)

    def forbidden(*args, **kwargs):
        raise AssertionError("healthy cached publication reparsed source geometry")

    monkeypatch.setattr(producer, "_revision_inputs", checked)
    for name in ("_scope_bbox", "_trusted_words", "_visible_segments"):
        monkeypatch.setattr(producer, name, forbidden)
    for _ in range(3):
        assert producer.publish_scope(selector) == historical
    assert calls == [selector] * 3
    evidence = historical.evidence
    assert evidence.selector.snapshot_id == published.snapshot.snapshot_id
    assert set(evidence.source_text_observation_ids) <= set(published.text_observation_ids)
    assert set(evidence.source_segment_observation_ids) <= set(published.visible_observation_ids)
    assert source.published_snapshot_for_revision(published.revision.revision_id) == published
