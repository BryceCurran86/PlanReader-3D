"""Original source-authenticated opening tag census, diagnostic only.

Neither an external tag nor its proximity may elect a physical opening.
Only complete source-owned text/OCR receipts and actual source apertures are
listed. A future producer must independently prove actual leader geometry.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import math

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_tag_normalization import normalize_opening_tag
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_schedule_opening_instance_binding_authority import (
    _aperture_contains_bbox, _bbox_of_points, _geometry_points,
    _opening_aperture_for_physical_opening,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def build_g17_original_plan_tag_census_shadow(source, composition, *, revision_id, page_id):
    """Inspect producer-owned opening and text universes; never bind a tag."""
    if type(source) is not SourceVisibilityProducer:
        raise TypeError('original SourceVisibilityProducer required')
    pub=source.published_snapshot_for_revision(revision_id)
    if (pub is None or source._producer.current_revision_id(pub.revision.document_id)!=revision_id
            or page_id not in tuple(str(x) for x in pub.coverage.decoded_pages)
            or page_id in tuple(str(x) for x in pub.coverage.failed_pages)):
        raise ValueError('current authenticated decoded original page required')
    if composition.physical_opening_authority is not source.physical_opening_authority():
        raise ValueError('foreign physical opening producer')
    root=dict(document_id=pub.revision.document_id,revision_id=revision_id,
              source_sha256=pub.revision.source_sha256,snapshot_id=pub.snapshot.snapshot_id,
              page_id=page_id)
    complete=pub.coverage.state=='complete' and not pub.coverage.failed_pages
    openings=[]
    for trace in composition.opening_bindings:
        obs_id=trace.representative_observation_id
        selector=ObservationSelector(**{k:root[k] for k in ('document_id','revision_id','source_sha256','snapshot_id')},
                                     observation_id=obs_id)
        result=composition.physical_opening_authority.prove_existence(selector)
        item=result.existence_record
        if (result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.proposition!=PHYSICAL_OPENING_EXISTS or item is None
                or item.record_id!=trace.opening_identity_id):
            raise RuntimeError('original opening existence no longer authenticates')
        if item.page_id != page_id:
            continue
        aperture=_opening_aperture_for_physical_opening(source,item)
        openings.append(dict(physical_opening_id=item.record_id,
            representative_source_observation_id=obs_id,
            authentic_aperture_geometry_available=aperture is not None,
            _aperture=aperture))
    if len({x['physical_opening_id'] for x in openings})!=len(openings):
        raise RuntimeError('duplicate physical opening identity')
    words=[]
    unavailable=[]
    integrity=source.text_integrity_authority()
    for oid in pub.text_observation_ids:
        selector=ObservationSelector(**{k:root[k] for k in ('document_id','revision_id','source_sha256','snapshot_id')},
                                     observation_id=oid)
        result=integrity.resolve_text(selector)
        receipt=result.receipt
        if (result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.trusted_text is None or receipt is None):
            unavailable.append(oid)
            continue
        if str(receipt.page_id)!=page_id:
            continue
        bbox=_bbox_of_points(_geometry_points(tuple(float(v) for v in receipt.geometry)))
        if bbox is None:
            unavailable.append(oid)
            continue
        normal=normalize_opening_tag(result.trusted_text)
        if normal is None:
            continue
        words.append(dict(observation_id=oid,text=result.trusted_text,
            normalized_tag=normal.tag,source_kind='trusted_native',bbox=bbox))
    for observation in source.authenticated_ocr_tag_observations(revision_id):
        if str(observation.page_id)!=page_id:
            continue
        bbox=_bbox_of_points(_geometry_points(tuple(float(v) for v in observation.geometry)))
        if bbox is None or not all(math.isfinite(float(x)) for x in bbox):
            unavailable.append(observation.observation_id)
            continue
        normalized=normalize_opening_tag(observation.raw_text)
        if normalized is None:
            continue
        words.append(dict(observation_id=observation.observation_id,
            text=observation.raw_text,normalized_tag=normalized.tag,
            source_kind='authenticated_ocr',bbox=bbox))
    words.sort(key=lambda r:(r['observation_id'],r['source_kind']))
    records=[]
    for word in words:
        geometrically_contained=tuple(sorted(
            x['physical_opening_id'] for x in openings
            if x['_aperture'] is not None and _aperture_contains_bbox(x['_aperture'],word['bbox'])
        ))
        records.append(dict(word,
            contained_in_authenticated_apertures=geometrically_contained,
            outside_all_authenticated_apertures=not geometrically_contained,
            unique_owner_granted=False,
            schedule_binding_granted=False,
            height_or_width_granted=False))
    if source.published_snapshot_for_revision(revision_id)!=pub:
        raise RuntimeError('original source mutated during tag census')
    return dict(root, source_decode_complete=complete,
        physical_opening_count=len(openings),
        physical_openings=[{k:v for k,v in row.items() if k!='_aperture'} for row in openings],
        source_text_integrity_unavailable_observation_ids=tuple(sorted(set(unavailable))),
        tag_candidate_records=records,
        candidate_outside_all_apertures=sum(x['outside_all_authenticated_apertures'] for x in records),
        source_text_tag_candidates=len(records),
        actual_source_leader_topology_proven=False,
        source_coverage_exhaustiveness_proven=False,
        opening_tag_binding_granted=False,
        source_schedule_binding_granted=False,
        physical_host_granted=False,metric_quantity_granted=False,
        original_source_authenticated_by_report=False)
