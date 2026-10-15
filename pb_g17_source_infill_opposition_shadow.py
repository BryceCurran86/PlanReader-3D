"""Source-owned G17 infill opposes candidate wall continuity, in shadow only.

No source primitive is removed or reassigned. The existing actual opening
proof, source paint and same-root F.07 are required even for CANDIDATE atoms.
These atoms and the additional W4 partition grant no physical wall or host.
"""
from __future__ import annotations

from dataclasses import asdict

from pb_g17_plan_wall_scope_shadow import build_g17_plan_wall_scope_shadow,_graph
from pb_g17_w4_equivalence_competitor_shadow import _positive_collinear_source_overlap
from pb_migration_contracts import EvidenceAtom,EvidenceResolutionStatus,stable_contract_id
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_typed_negative_evidence import KIND_SYMBOL,POLARITY_OPPOSING


def _infill_interval(observation,opening):
    """Exact positive interval inside the actual opening, no nearest-line join."""
    if observation.observation_kind not in ('raster_line_run','raster_thin_ink_run'):
        return None
    box=opening.aperture_bbox_pt
    if box is None or len(box)!=4 or len(observation.geometry)!=4:
        return None
    x0,y0,x1,y1=box
    a,b,c,d=observation.geometry
    if x1-x0>=2*(y1-y0)>0 and b==d and y0<b<y1:
        lo,hi=max(x0,min(a,c)),min(x1,max(a,c))
        return (lo,b,hi,b) if hi>lo else None
    if y1-y0>=2*(x1-x0)>0 and a==c and x0<a<x1:
        lo,hi=max(y0,min(b,d)),min(y1,max(b,d))
        return (a,lo,a,hi) if hi>lo else None
    return None


def build_g17_source_infill_opposition_shadow(source,*,revision_id:str,page_id:str)->dict:
    if type(source) is not SourceVisibilityProducer:
        raise TypeError('actual SourceVisibilityProducer required')
    pub=source.published_snapshot_for_revision(revision_id)
    if pub is None:
        raise ValueError('current original source revision required')
    baseline=build_g17_plan_wall_scope_shadow(source,revision_id=revision_id,page_id=page_id)
    # F.07 depends on native title/figure/room receipts too. A later mutation
    # outside the G17 supports must invalidate the complete source read.
    with source._native_dimension_source_proof_batch(pub,page_id=page_id):
        return _build(source,baseline=baseline,revision_id=revision_id,page_id=page_id)


def _build(source,*,baseline,revision_id,page_id):
    pub=source.published_snapshot_for_revision(revision_id)
    root={k:baseline[k] for k in ('document_id','revision_id','source_sha256','snapshot_id','page_id')}
    result=dict(root,source_viewport_ownership_id=baseline['source_viewport_ownership_id'],
        status=EvidenceResolutionStatus.ABSTAINED.value,reason_codes=['independent_structural_wall_role_and_host_required'],
        original_infill_intervals=[],opposing_atoms=[],candidate_partitions={},
        baseline_w2_geometry_unchanged=True,ordinary_source_snapshot_unchanged=True,
        host_granted=False,structural_wall_role_granted=False,
        physical_wall_equivalence_granted=False,metric_quantity_granted=False)
    if not baseline['source_viewport_ownership_id']:
        result['reason_codes']=['source_owned_plan_required_for_infill_role']
        return result
    visibility=source.authority();authority=source.physical_opening_authority()
    original_receipts={oid:source._raster_opening_primitive_receipts.get((root['snapshot_id'],oid))
                       for oid in pub.raster_opening_primitive_observation_ids}
    observations={}
    source_rows={r['observation_id']:r for r in baseline['source_primitive_dispositions']}
    for oid,row in sorted(source_rows.items()):
        address=ObservationSelector(root['document_id'],revision_id,root['source_sha256'],root['snapshot_id'],oid)
        proof=visibility.resolve_raster_opening_primitive(address)
        o=proof.observation
        if (proof.status is not EvidenceResolutionStatus.CORROBORATED or o is None
                or tuple(o.geometry)!=tuple(row['geometry']) or o.page_id!=page_id
                or o.source_primitive_ref!='visible:'+row['source_primitive_id']):
            raise RuntimeError('original_infill_source_integrity_failure')
        observations[oid]=o
    intervals=[]
    for raw in baseline['physical_openings']:
        expected=raw['record'];records={}
        for oid in expected['source_observation_ids']:
            address=ObservationSelector(root['document_id'],revision_id,root['source_sha256'],root['snapshot_id'],oid)
            proof=authority.prove_existence(address)
            if (proof.status is EvidenceResolutionStatus.CORROBORATED
                    and proof.proposition==PHYSICAL_OPENING_EXISTS and proof.existence_record is not None):
                records[proof.existence_record.record_id]=proof.existence_record
        opening=records.get(expected['record_id'])
        if opening is None or asdict(opening)!=expected:
            raise RuntimeError('original_infill_opening_proof_changed')
        for oid in opening.source_observation_ids:
            row=source_rows.get(oid);o=observations.get(oid)
            if row is None or o is None:
                raise RuntimeError('original_infill_support_outside_authenticated_scope')
            interval=_infill_interval(o,opening)
            if (interval is None or not row['inside_original_image_regions']
                    or not row['source_paint']['original_solid_and_unchanged']):
                continue
            box=baseline['source_viewport_bbox']
            a,b,c,d=interval
            if not (box[0]<=min(a,c)<=max(a,c)<=box[2] and box[1]<=min(b,d)<=max(b,d)<=box[3]):
                continue
            intervals.append(dict(physical_opening_id=opening.record_id,source_observation_id=oid,
                source_primitive_id=row['source_primitive_id'],geometry=interval))
    intervals.sort(key=lambda x:(x['physical_opening_id'],x['source_observation_id']))
    result['original_infill_intervals']=intervals
    segments=[]
    for row in source_rows.values():
        if (row['drawing_disposition']=='inside' and row['inside_original_image_regions']
                and row['source_paint']['original_solid_and_unchanged']):
            a,b,c,d=row['geometry']
            segments.append(dict(id=row['source_primitive_id'],x1=a,y1=b,x2=c,y2=d,
                kind='line',kind_present=True,layer='',dashes='',width=0.,width_present=False))
    for name in ('default_w2_w3_w4','exact_coordinate_w2_w3_w4'):
        original=baseline[name]
        scope_id=stable_contract_id('g17-infill-opposition-shadow',dict(root,
            viewport_ownership_id=baseline['source_viewport_ownership_id'],snap_tolerance_pt=original['snap_tolerance_pt']))
        partition=_graph(segments,root=root,scope_id=scope_id,tolerance=original['snap_tolerance_pt'],
                         infill_intervals=intervals)
        if partition['w2_edges']!=original['w2_edges']:
            raise RuntimeError('source_infill_experiment_changed_original_w2_geometry')
        result['candidate_partitions'][name]=partition
        for record in partition['w4_records']:
            for interval in intervals:
                if not any(interval['source_primitive_id'] in f['source_primitive_ids']
                    and _positive_collinear_source_overlap(f['geometry'],interval['geometry'])
                    for f in record['source_edge_fragments']):
                    continue
                payload=dict(root,physical_opening_id=interval['physical_opening_id'],
                    source_observation_id=interval['source_observation_id'],geometry=interval['geometry'],
                    wall_candidate_id=record['wall_candidate_id'],partition=name)
                atom=EvidenceAtom(evidence_id=stable_contract_id('g17-infill-opposition',payload),
                    document_id=root['document_id'],page_id=page_id,kind=KIND_SYMBOL,
                    method='source_owned_opening_infill_opposition_shadow',
                    viewport_id=baseline['source_viewport_id'],status=EvidenceResolutionStatus.CANDIDATE,
                    reason_codes=('source_owned_opening_infill_opposes_wall_continuity',),
                    metadata=dict(payload,polarity=POLARITY_OPPOSING,source_role='opening_infill',
                        source_snapshot_id=root['snapshot_id'],physical_host_authority=False))
                result['opposing_atoms'].append(atom.to_dict())
    if source.published_snapshot_for_revision(revision_id)!=pub:
        raise RuntimeError('source_infill_experiment_changed_original_snapshot')
    if original_receipts!={oid:source._raster_opening_primitive_receipts.get((root['snapshot_id'],oid))
                          for oid in pub.raster_opening_primitive_observation_ids}:
        raise RuntimeError('source_infill_original_pixel_receipts_changed')
    # Reauthenticate every original source parent after the additional graph.
    for oid,o in observations.items():
        address=ObservationSelector(root['document_id'],revision_id,root['source_sha256'],root['snapshot_id'],oid)
        proof=visibility.resolve_raster_opening_primitive(address)
        if proof.status is not EvidenceResolutionStatus.CORROBORATED or proof.observation!=o:
            raise RuntimeError('source_infill_receipts_changed_during_read')
    for oid in set(pub.raster_opening_primitive_observation_ids)-observations.keys():
        address=ObservationSelector(root['document_id'],revision_id,root['source_sha256'],root['snapshot_id'],oid)
        proof=visibility.resolve_raster_opening_primitive(address)
        if proof.status is not EvidenceResolutionStatus.CORROBORATED or proof.observation is None:
            raise RuntimeError('source_infill_competing_source_changed_during_read')
    return result
