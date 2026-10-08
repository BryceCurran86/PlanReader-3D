"""Both ordinary raster readers authenticate the frozen identity payload."""
from dataclasses import replace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_source_visibility_v1 import _image_only_pdf


@pytest.mark.parametrize('damage', ['dpi', 'version', 'hash', 'pixel_geometry',
    'geometry', 'visibility_hash', 'receipt', 'primitive_index'])
def test_both_readers_reject_damaged_ordinary_render_provenance(damage):
    source = SourceVisibilityProducer(producer_method='raster-receipt-identity-test',producer_version='1')
    initial = source.ingest_native_pdf_bytes(document_id='raster-receipt-identity-test',
        source_bytes=_image_only_pdf(),source_locator='memory://raster-receipt-identity-test.pdf')
    published = source.augment_with_raster_visible_segments(initial.revision.revision_id,page_ids=('1',))
    oid, record = next((oid,record) for oid,record in source.authority().authenticated_visible_observations(published)
        if ':1.0.0:' in record.source_primitive_ref)
    selector = ObservationSelector(document_id=published.revision.document_id,revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,snapshot_id=published.snapshot.snapshot_id,observation_id=oid)
    key = selector.snapshot_id, oid
    assert source.authority().resolve_visible(selector).status is Status.CORROBORATED
    if damage=='receipt': del source._raster_visibility_receipts[key]
    elif damage=='primitive_index':
        parent_id=source._raster_visibility_receipts[key].parent_observation_id
        parent=source._producer._store.observations[(selector.snapshot_id,parent_id)]
        changed_ref=record.source_primitive_ref.rsplit(':',1)[0]+':99999'
        source._producer._store.observations[key]=replace(record,source_primitive_ref=changed_ref)
        source._producer._store.observations[(selector.snapshot_id,parent_id)]=replace(parent,source_primitive_ref=changed_ref.removeprefix('visible:'))
    else:
        field,value={
            'dpi':('dpi',999),'version':('detector_version','unknown'),
            'hash':('image_sha256','0'*64),'pixel_geometry':('pixel_geometry',(0.,0.,1.,0.)),
            'geometry':('geometry',(0.,0.,1.,0.)),'visibility_hash':('visibility_render_sha256','0'*64),
        }[damage]
        source._raster_visibility_receipts[key]=replace(source._raster_visibility_receipts[key],**{field:value})
    assert source.authority().resolve_visible(selector).status is not Status.CORROBORATED
    with pytest.raises(RuntimeError): source.authority().authenticated_visible_observations(published)
