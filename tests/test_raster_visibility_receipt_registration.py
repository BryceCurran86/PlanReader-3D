"""Registration receipts cannot borrow previously authenticated source identity."""
from dataclasses import asdict, replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_source_visibility_v1 import _image_only_pdf, _selector


def _fixture():
    source = SourceVisibilityProducer(producer_method='registration-proof-test', producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='registration-proof-test',
        source_bytes=_image_only_pdf(), source_locator='memory://registration-proof-test.pdf')
    published = source.augment_with_raster_visible_segments(published.revision.revision_id)
    authority = source.authority()
    key = (published.snapshot.snapshot_id, published.visible_observation_ids[0])
    return source, published, authority, key


@pytest.mark.parametrize('warm', [False, True])
@pytest.mark.parametrize('damage', ['dpi', 'pixels', 'render', 'geometry', 'receipt_missing'])
def test_scalar_and_bulk_registration_fail_closed_before_and_after_cache_hits(warm, damage):
    source, published, authority, key = _fixture()
    selector = _selector(published, key[1])
    if warm:
        assert authority.resolve_visible(selector).status is Status.CORROBORATED
        assert authority.authenticated_visible_observations(published)
    receipt = source._raster_visibility_receipts[key]
    if damage == 'dpi': damaged = replace(receipt, dpi=999)
    elif damage == 'pixels': damaged = replace(receipt, pixel_geometry=(0., 0., 1., 1.))
    elif damage == 'render': damaged = replace(receipt, image_sha256='0' * 64)
    elif damage == 'geometry': damaged = replace(receipt, geometry=(0., 0., 1., 1.))
    else: damaged = None
    if damaged is None:
        del source._raster_visibility_receipts[key]
    else:
        source._raster_visibility_receipts[key] = damaged
    assert authority.resolve_visible(selector).status in {Status.ABSTAINED, Status.CONFLICT}
    with pytest.raises(RuntimeError):
        authority.authenticated_visible_observations(published)


def test_detector_provenance_change_keeps_frozen_source_identity_and_registration():
    source, published, authority, key = _fixture()
    selector = _selector(published, key[1])
    expected = authority.resolve_visible(selector)
    before = asdict(expected.observation)
    bulk = authority.authenticated_visible_observations(published)
    source._raster_visibility_receipts[key] = replace(
        source._raster_visibility_receipts[key], detector_version='future-detector')
    assert authority.resolve_visible(selector) == expected
    assert authority.authenticated_visible_observations(published) == bulk
    assert asdict(authority.resolve_visible(selector).observation) == before
