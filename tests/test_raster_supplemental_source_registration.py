"""Supplemental source lines require complete immutable registration and paint."""
from dataclasses import replace

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_observation_authority import ObservationSelector
from test_raster_terminal_wall_band_segments import _source, _rows, _image, _png


@pytest.mark.parametrize('warm', [False, True])
@pytest.mark.parametrize('family', ['compact_solid_wall_band_v1', 'terminal_solid_wall_band_v1'])
@pytest.mark.parametrize('damage', ['dpi', 'pixels', 'image_hash', 'full_hash', 'receipt'])
def test_both_readers_reject_damaged_supplemental_registration(warm, family, damage):
    source, initial = _source()
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    oid = next(oid for oid in snapshot.visible_observation_ids
               if ':' + family + ':' in source._producer._store.observations[
                   (snapshot.snapshot.snapshot_id, oid)].source_primitive_ref)
    selector = ObservationSelector(document_id=snapshot.revision.document_id,
        revision_id=snapshot.revision.revision_id, source_sha256=snapshot.revision.source_sha256,
        snapshot_id=snapshot.snapshot.snapshot_id, observation_id=oid)
    authority = source.authority()
    if warm:
        assert authority.resolve_visible(selector).status is Status.CORROBORATED
        assert authority.authenticated_visible_observations(snapshot)
    key = selector.snapshot_id, selector.observation_id
    receipt = source._raster_visibility_receipts[key]
    if damage == 'receipt':
        del source._raster_visibility_receipts[key]
    else:
        field, value = {
            'dpi': ('dpi', 144), 'pixels': ('pixel_geometry', (0., 0., 1., 1.)),
            'image_hash': ('image_sha256', '0' * 64),
            'full_hash': ('visibility_render_sha256', '0' * 64),
        }[damage]
        source._raster_visibility_receipts[key] = replace(receipt, **{field: value})
    assert authority.resolve_visible(selector).status in {Status.ABSTAINED, Status.CONFLICT}
    with pytest.raises(RuntimeError):
        authority.authenticated_visible_observations(snapshot)


@pytest.mark.parametrize('family', ['compact_solid_wall_band_v1', 'terminal_solid_wall_band_v1'])
def test_live_detector_version_is_provenance_and_cannot_rename_source_geometry(family):
    source, initial = _source()
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    selector, record = next((s, r) for s, r in _rows(source, snapshot)
                            if ':' + family + ':' in r.source_primitive_ref)
    authority = source.authority()
    expected = authority.resolve_visible(selector)
    bulk = authority.authenticated_visible_observations(snapshot)
    key = selector.snapshot_id, selector.observation_id
    source._raster_visibility_receipts[key] = replace(source._raster_visibility_receipts[key],
                                                     detector_version='future-detector')
    assert authority.resolve_visible(selector) == expected
    assert authority.authenticated_visible_observations(snapshot) == bulk


def test_later_page_safety_failure_does_not_hide_completed_source_page_on_retry(monkeypatch):
    import pb_source_visibility_authority as visibility
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=72., height=48.)
        page.insert_image(page.rect, stream=_png(_image()), keep_proportion=False)
    raw = doc.tobytes()
    doc.close()
    source = SourceVisibilityProducer(producer_method='two-page-source-retry', producer_version='1')
    initial = source.ingest_native_pdf_bytes(document_id='two-page-source-retry', source_bytes=raw,
                                             source_locator='memory://two-pages.pdf')
    original = visibility.detect_terminal_raster_wall_band_segments
    calls = 0
    def fail_second_page(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError('raster opening primitive count exceeds safety bound')
        return original(*args, **kwargs)
    monkeypatch.setattr(visibility, 'detect_terminal_raster_wall_band_segments', fail_second_page)
    with pytest.raises(ValueError, match='safety bound'):
        source.augment_with_raster_visible_segments(initial.revision.revision_id)
    assert source.published_snapshot_for_revision(initial.revision.revision_id) == initial
    assert not source._raster_visibility_attempted_pages
    monkeypatch.setattr(visibility, 'detect_terminal_raster_wall_band_segments', original)
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id)
    rows = source.authority().authenticated_visible_observations(snapshot)
    assert {record.page_id for _, record in rows} == {'1', '2'}
    assert source.augment_with_raster_visible_segments(initial.revision.revision_id) == snapshot
