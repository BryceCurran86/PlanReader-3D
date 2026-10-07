from dataclasses import replace

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_opening_dimension_authority import OPENING_DIMENSION_EXISTENCE_REQUIRED
from test_raster_door_swing_g17_contract import _sheet, _pdf


def test_raster_support_is_read_from_its_sealed_namespace_without_inventing_width():
    source = SourceVisibilityProducer(producer_method='raster-dimension-contract', producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='raster-dimension-contract',
        source_bytes=_pdf(_sheet(leaf=True, arc=True, leaf_bundle=True)),
        source_locator='memory://raster-dimension-contract.pdf', page_ids=('1',))
    published = source.augment_with_raster_opening_primitives(published.revision.revision_id, page_ids=('1',))
    physical = source.physical_opening_authority()
    proven = []
    for oid in published.raster_opening_primitive_observation_ids:
        selector = ObservationSelector(document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id, observation_id=oid)
        result = physical.prove_existence(selector)
        if result.status is Status.CORROBORATED:
            proven.append((selector, result.existence_record))
    assert proven
    selector, opening = proven[0]
    authority = source.opening_dimension_authority()
    support = authority._visible_records(opening)
    assert {r.observation_id for r in support} == set(opening.source_observation_ids)
    width = authority.resolve_width(selector)
    assert width.status is Status.ABSTAINED
    assert width.value_mm is None
    assert OPENING_DIMENSION_EXISTENCE_REQUIRED not in width.reason_codes
    assert any('jamb' in r or 'witness' in r for r in width.reason_codes)
    # Unknown raster support and stale lineage cannot be supplied by callers.
    assert authority._visible_records(replace(opening, source_observation_ids=('unowned',))) == ()
    assert authority._visible_records(replace(opening, source_sha256='0' * 64)) == ()
