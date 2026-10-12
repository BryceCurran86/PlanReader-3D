"""Original-byte-authenticated full-page endpoint-index experiment, no hosts."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import SourceObservationRecord
from pb_opening_host_binding_authority import _OpeningGeometry
from pb_wall_room_topology_contracts import WallCandidate
from scripts.gptmax_exact_endpoint_flank_shadow import _local_records, annotate_source_span_coverage
from scripts.gptmax_full_foreground_flank_stages import _flank_stage_rows, _contacts
from tools.diag_gptmax_full_foreground_flank import full_foreground_flank_census
from tools.diag_gptmax_full_foreground_run_source import original_full_foreground_report, _trace_sources
from tools.diag_gptmax_raster_host_source_membership import original_raster_host_ancestry_census
from tools.diag_gptmax_required_flank_source import required_flank_source_census


def _encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def _closed_chain_abstention_receipt(error, records):
    """Observe an actual rejected constructor, never create a replacement wall.

    Read the failing call's traceback only. Do not patch a class, bypass its
    guard, reassemble a partial universe, or infer later failures from this one.
    """
    trace, rejected, tb = None, None, error.__traceback__
    while tb is not None:
        frame=tb.tb_frame
        if frame.f_code is _trace_sources.__code__: trace=frame.f_locals
        if frame.f_code is WallCandidate.__post_init__.__code__: rejected=frame.f_locals.get('self')
        tb=tb.tb_next
    if trace is None or rejected is None or rejected.end_node_ids[0]!=rejected.end_node_ids[1]:
        raise RuntimeError('actual rejected W4 constructor receipt unavailable') from error
    original={r.observation_id:r for r in records}
    edges={str(e['id']):e for e in trace['graph']['edges']}
    retained={str(e['id']) for e in trace['deduped']['edges']}
    ids=rejected.face_a_segment_ids
    if not ids or len(set(ids))!=len(ids) or not set(ids)<=retained:
        raise RuntimeError('rejected W4 chain has unavailable original W3 fragments') from error
    rows=[]
    for key in ids:
        e=edges[key]
        parents=tuple(e['primitive_lineage']['source_primitive_ids'])
        if not parents or not set(parents)<=original.keys():
            raise RuntimeError('rejected W4 chain has foreign source ancestry') from error
        rows.append(dict(edge_id=key,w2_fragment_geometry_pt=[e[k] for k in ('x1','y1','x2','y2')],
            source_observation_ids=sorted(parents),w3_retained=True,physical_host_authority=False))
    return dict(status=EvidenceResolutionStatus.ABSTAINED.value,
        reason_codes=[str(error)],rejected_attempt_candidate_id=rejected.candidate_id,
        end_node_ids=rejected.end_node_ids,centerline_pt=rejected.centerline_pts,
        actual_owned_w3_fragment_rows=rows,
        only_first_assembly_failure_observed=True,w4_candidate_universe_available=False,
        physical_wall_authority=False,host_publication_allowed=False,
        source_parent_transfer_allowed=False)


def _source_spans_before_failed_w4(error, joined, original, required, records):
    """Inventory actual W2/W3 coverage while W4 membership stays unavailable."""
    trace,tb=None,error.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code is _trace_sources.__code__: trace=tb.tb_frame.f_locals
        tb=tb.tb_next
    if trace is None: raise RuntimeError('actual failed W4 graph context unavailable') from error
    source_ids={r.observation_id for r in records}
    retained={str(e['id']) for e in trace['deduped']['edges']}
    by_parent={key:[] for key in source_ids}
    for edge in trace['graph']['edges']:
        parents=edge['primitive_lineage']['source_primitive_ids']
        if not set(parents)<=source_ids:
            raise RuntimeError('failed W4 graph has foreign source ancestry') from error
        row=dict(edge_id=str(edge['id']),source_observation_ids=sorted(parents),
            w2_fragment_geometry_pt=[edge[k] for k in ('x1','y1','x2','y2')],
            w3_retained=str(edge['id']) in retained,
            w4_membership_available=False,experimental_w4_candidate_ids=None,
            physical_host_authority=False)
        for parent in parents: by_parent[parent].append(row)
    output=[]
    for opening in joined['opening_rows']:
        identity=opening['opening_identity_id']
        source,=(r for r in original['opening_rows'] if r['opening_identity_id']==identity)
        requirement,=(r for r in required['opening_rows'] if r['opening_identity_id']==identity)
        geometry=_OpeningGeometry(**source['original_aperture_coordinate_basis'])
        flanks=[]
        for flank in opening['flanks']:
            req,=(f for f in requirement['flanks'] if f['role']==flank['role'])
            pixels=[]
            for pixel in flank['pixel_run_candidates']:
                key=pixel['source_observation_id']
                if key not in by_parent: raise RuntimeError('original flank source unavailable')
                edges=[dict(e,matches_original_required_flank_geometry=
                    _contacts(e['w2_fragment_geometry_pt'],geometry,req)) for e in by_parent[key]]
                pixels.append(dict(source_observation_id=key,source_line_pt=pixel['source_line_pt'],
                    actual_w2_edge_rows=edges,w4_membership_available=False,
                    host_publication_allowed=False,physical_equivalence_proven=False))
            flanks.append(dict(role=flank['role'],source_run_rows=pixels,
                w4_membership_available=False,host_publication_allowed=False))
        output.append(dict(opening_identity_id=identity,flanks=flanks,
            w4_membership_available=False,host_publication_allowed=False))
    annotate_source_span_coverage(output,original,required)
    return output


def full_page_endpoint_source_report(source_bytes, *, page_id, expected_source_sha):
    if not isinstance(source_bytes, bytes) or sha256(source_bytes).hexdigest()!=expected_source_sha:
        raise ValueError('immutable original PDF SHA mismatch')
    original=original_raster_host_ancestry_census(source_bytes,page_id=page_id,
        expected_source_sha=expected_source_sha)
    raw=_encoded(original)
    required=required_flank_source_census(original,expected_source_sha=expected_source_sha)
    required['input_report_sha256']=sha256(raw).hexdigest()
    foreground=original_full_foreground_report(source_bytes,page_id=page_id,
        expected_source_sha=expected_source_sha,trace=False)
    joined=full_foreground_flank_census(raw,required,foreground,pdf_bytes=source_bytes,
        expected_source_sha=expected_source_sha)
    records=tuple(SourceObservationRecord(**r) for r in [
        *foreground['ordinary_visible_source_records'],
        *(r['source_observation'] for r in foreground['authenticated_pixel_source_records'])])
    manifest=_encoded([asdict(r) for r in records])
    modes={}
    for name,indexed in (('default_full_page_shadow',False),('indexed_exact_endpoint_full_page_shadow',True)):
        try:
            graph=_trace_sources(records,exact_endpoint_shadow=indexed,
                exact_endpoint_index_shadow=indexed)
        except ValueError as error:
            if not indexed or str(error)!='a wall candidate cannot start and end at the same node':
                raise
            receipt=_closed_chain_abstention_receipt(error,records)
            modes[name]=dict(source_graph=None,opening_rows=None,
                w4_assembly_status=EvidenceResolutionStatus.ABSTAINED.value,
                first_failure_receipt=receipt,
                source_span_rows_before_w4=_source_spans_before_failed_w4(
                    error,joined,original,required,records))
        else:
            rows=_flank_stage_rows(joined,original,required,graph)
            annotate_source_span_coverage(rows,original,required)
            modes[name]=dict(source_graph=graph,opening_rows=rows,
                w4_assembly_status=EvidenceResolutionStatus.CANDIDATE.value,
                first_failure_receipt=None,source_span_rows_before_w4=None)
    # Bounded original-source legacy controls use exactly the same local
    # inventories as #2445. They do not claim full-page legacy-zero parity.
    controls=[]
    for opening in sorted(joined['opening_rows'],key=lambda r:r['opening_identity_id']):
        seeds=sorted({p['source_observation_id'] for f in opening['flanks']
            for p in f['pixel_run_candidates']})
        local,extent=_local_records(records,seeds)
        legacy=_trace_sources(local,exact_endpoint_shadow=True)
        indexed=_trace_sources(local,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True)
        if legacy!=indexed:
            raise RuntimeError('indexed endpoint shadow changed original local legacy graph')
        controls.append(dict(opening_identity_id=opening['opening_identity_id'],
            input_source_count=len(local),source_extent_pt=extent,
            complete_local_legacy_graph_equal=True,host_publication_allowed=False))
    if manifest!=_encoded([asdict(r) for r in records]):
        raise RuntimeError('shadow changed original source input records')
    after=original_raster_host_ancestry_census(source_bytes,page_id=page_id,
        expected_source_sha=expected_source_sha)
    if original!=after:
        raise RuntimeError('full-page endpoint shadow changed production source state')
    return dict(schema_version='1.0.0',source_sha256=expected_source_sha,page_id=page_id,
        original_source_reauthenticated=True,default_production_state_unchanged=True,
        original_source_report_sha256=sha256(raw).hexdigest(),
        original_opening_bindings=original['opening_bindings'],original_host_frames=original['host_frames'],
        input_source_manifest_sha256=sha256(manifest).hexdigest(),
        full_source_input_primitive_count=len(records),
        source_primitive_safety_cap=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        identical_full_page_source_inputs_for_both_modes=True,
        complete_full_page_legacy_zero_graph_equality_proven=False,
        local_legacy_exact_controls=controls,**modes,
        full_page_scope_is_authenticated_floor_plan_viewport=False,
        physical_wall_authority=False,physical_equivalence_proven=False,
        source_parent_transfer_allowed=False,structural_source_universe_complete=False,
        host_publication_allowed=False,opening_count_publication_allowed=False,
        metric_quantity_publication_allowed=False,benchmark_accuracy=None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',type=Path,required=True)
    parser.add_argument('--page-id',required=True)
    parser.add_argument('--expected-source-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=full_page_endpoint_source_report(args.pdf.read_bytes(),page_id=args.page_id,
        expected_source_sha=args.expected_source_sha)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(inputs=result['full_source_input_primitive_count'],
        default_production_state_unchanged=True,host_publication_allowed=False)))


if __name__=='__main__':
    main()
