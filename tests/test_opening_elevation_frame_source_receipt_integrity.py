"""Foreign source wrappers cannot authorize a type-level elevation area."""
from dataclasses import asdict, replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_opening_elevation_frame_area_authority import OpeningElevationFrameAreaProducer
from pb_raster_text_corroboration_authority import RasterTextCorroborationProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from test_opening_elevation_frame_area_authority import (
    _elevation_pdf, _exact_word_backend, _glyph_unverified_elevation_pdf, _selector,
)


def _source(payload=None):
    source = SourceVisibilityProducer(producer_method="elevation-receipt-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="elevation", source_bytes=payload or _elevation_pdf(),
        source_locator="memory://elevation.pdf",
    )
    return source, published


def _resolve(source, published, *, backend=None):
    producer = (
        OpeningElevationFrameAreaProducer.from_source_visibility_producer(source)
        if backend is None else
        OpeningElevationFrameAreaProducer.from_source_visibility_producer_for_tests(source, backend)
    )
    return producer.authority().resolve(_selector(published, "W1"))


def _assert_unavailable(result):
    assert result.status is S.ABSTAINED
    assert result.record is None
    assert result.reason_codes == ("opening_elevation_frame_area_unavailable",)


@pytest.mark.parametrize("change", [
    {"document_id": "foreign"}, {"revision_id": "foreign"},
    {"source_sha256": "0" * 64}, {"parent_observation_id": "foreign"},
    {"page_id": "2"}, {"source_partition_id": "page:2"},
    {"raw_text": "WINDOW"}, {"trusted": False}, {"trusted": 1},
    {"geometry": (0., 0., 10., 10.)},
    {"block_no": "0"}, {"line_no": True}, {"word_no": 0.5},
    {"sequence_number": float("inf")}, {"word_no": -1},
])
def test_malformed_native_receipt_abstains_without_borrowing_raster(monkeypatch, change):
    source, published = _source()
    before = _resolve(source, published)
    assert before.status is S.CORROBORATED
    snapshot = source.published_snapshot_for_revision(published.revision.revision_id)
    authority_type = type(source.text_integrity_authority())
    original = authority_type.resolve_text
    injected = []

    def malformed(self, selector):
        result = original(self, selector)
        if result.status is S.CORROBORATED and result.trusted_text == "W1":
            injected.append(selector.observation_id)
            return replace(result, receipt=replace(result.receipt, **change))
        return result

    def no_fallback(*args, **kwargs):
        pytest.fail("a known-corrupt native channel must not be retried as raster authority")

    with monkeypatch.context() as patch:
        patch.setattr(authority_type, "resolve_text", malformed)
        patch.setattr(RasterTextCorroborationProducer, "publish", no_fallback)
        _assert_unavailable(_resolve(source, published))
    assert len(injected) == 1
    assert source.published_snapshot_for_revision(published.revision.revision_id) == snapshot
    assert _resolve(source, published) == before


@pytest.mark.parametrize("change", [
    {"receipt": None}, {"trusted_text": "W2"}, {"trusted_text": 1},
    {"proposition": "different_proposition"},
])
def test_positive_wrapper_requires_owned_receipt_and_exact_trusted_text(monkeypatch, change):
    source, published = _source()
    authority_type = type(source.text_integrity_authority())
    original = authority_type.resolve_text
    calls = []

    def malformed(self, selector):
        result = original(self, selector)
        if result.status is S.CORROBORATED and result.trusted_text == "W1":
            calls.append(selector.observation_id)
            return replace(result, **change)
        return result

    monkeypatch.setattr(authority_type, "resolve_text", malformed)
    _assert_unavailable(_resolve(source, published))
    assert len(calls) == 1


def test_malformed_rival_must_not_make_a_composite_window_unique(monkeypatch):
    source, published = _source(_elevation_pdf(composite=True))
    _assert_unavailable(_resolve(source, published))
    authority_type = type(source.text_integrity_authority())
    original = authority_type.resolve_text
    calls = []

    def foreign_rival(self, selector):
        result = original(self, selector)
        if result.trusted_text == "D1":
            calls.append(selector.observation_id)
            return replace(result, receipt=replace(result.receipt, document_id="foreign"))
        return result

    monkeypatch.setattr(authority_type, "resolve_text", foreign_rival)
    _assert_unavailable(_resolve(source, published))
    assert len(calls) == 1


@pytest.mark.parametrize("change", [
    {"document_id": "foreign"}, {"revision_id": "foreign"},
    {"source_sha256": "0" * 64}, {"snapshot_id": "foreign"},
    {"page_id": "2"}, {"native_observation_id": "foreign"},
    {"source_partition_id": "page:2"}, {"text_integrity_receipt_id": "foreign"},
    {"source_bbox": (0., 0., 10., 10.)}, {"corroborated_text": "W2"},
    {"source_bbox": None}, {"page_parent_observation_id": "foreign"},
    {"views": ()}, {"render_dpis": ()},
])
def test_positive_raster_record_requires_exact_native_source_scope(monkeypatch, change):
    source, published = _source(_glyph_unverified_elevation_pdf())
    backend = _exact_word_backend(source, published)
    before = _resolve(source, published, backend=backend)
    assert before.status is S.CORROBORATED
    original = RasterTextCorroborationProducer.publish
    calls = []

    def foreign(self, selector):
        result = original(self, selector)
        if result.status is S.CORROBORATED:
            calls.append(selector.observation_id)
            return replace(result, record=replace(result.record, **change))
        return result

    with monkeypatch.context() as patch:
        patch.setattr(RasterTextCorroborationProducer, "publish", foreign)
        _assert_unavailable(_resolve(source, published, backend=backend))
    assert calls
    assert _resolve(source, published, backend=backend) == before


def test_duplicate_inventory_and_failed_source_page_abstain_then_recover(monkeypatch):
    source, published = _source()
    before = _resolve(source, published)
    assert before.status is S.CORROBORATED
    for changed in (
        replace(published, text_observation_ids=(*published.text_observation_ids, published.text_observation_ids[0])),
        replace(published, coverage=replace(published.coverage, failed_pages=(1,))),
    ):
        with monkeypatch.context() as patch:
            patch.setitem(source._published_by_revision, published.revision.revision_id, changed)
            _assert_unavailable(_resolve(source, changed))
    assert _resolve(source, published) == before


def test_healthy_record_is_stable_under_inventory_order_and_no_mutation(monkeypatch):
    source, published = _source()
    before = _resolve(source, published)
    assert before.status is S.CORROBORATED
    snapshot = asdict(source.published_snapshot_for_revision(published.revision.revision_id))
    with monkeypatch.context() as patch:
        reordered = replace(published, text_observation_ids=tuple(reversed(published.text_observation_ids)))
        patch.setitem(source._published_by_revision, published.revision.revision_id, reordered)
        assert _resolve(source, reordered) == before
    assert asdict(source.published_snapshot_for_revision(published.revision.revision_id)) == snapshot
    assert _resolve(source, published) == before
