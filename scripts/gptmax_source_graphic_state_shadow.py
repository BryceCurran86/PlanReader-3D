"""Original-source graphic state beside unchanged experimental topology."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_physical_wall_candidate_authority import _source_page_segments, MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import SourceObservationRecord
from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_room_topology_primitive_lineage import lineage_from_source_segments
from tools.diag_gptmax_full_foreground_run_source import (
    _default_source, _trace_sources, original_full_foreground_report,
)
from tools.diag_opening_wall_face_preservation import source_face_report


def encoded(value):
    return json.dumps(value,sort_keys=True,allow_nan=False,default=lambda x:x.value).encode()


def join_graphic_state(graph,records,source_segments):
    """Descriptive join only; bare caller objects do not authenticate paint."""
    original={r.observation_id:r for r in records}
    if len(original)!=len(records): raise ValueError('duplicate original source identity')
    styles={}
    for segment in source_segments:
        if any(type(segment[f+'_present']) is not bool for f in
                ('width','stroke','fill','layer','dashes','clip') if f+'_present' in segment):
            raise ValueError('graphic-state presence must be explicit boolean')
        key=segment.get('source_observation_id')
        if key not in original: raise ValueError('foreign graphic-state source parent')
        r=original[key]
        geometry=tuple(segment[k] for k in ('x1','y1','x2','y2'))
        if (geometry!=r.geometry or segment.get('document_id')!=r.document_id
                or str(segment.get('page_id'))!=r.page_id):
            raise ValueError('contradictory graphic-state source geometry or scope')
        styles.setdefault(key,[]).append(dict(segment,id=key))
    rows=[]; seen=set()
    for edge in graph['all_w2_edges']:
        key=edge['edge_id'];parents=edge['source_observation_ids']
        if (key in seen or not isinstance(parents,(tuple,list)) or len(set(parents))!=len(parents)
                or not set(parents)<=original.keys()):
            raise ValueError('unowned actual graph fragment')
        seen.add(key)
        matched=sorted(set(parents)&styles.keys());missing=sorted(set(parents)-styles.keys())
        lineage=lineage_from_source_segments([s for p in matched for s in styles[p]])
        known_values={r['id'] for r in lineage['source_records'] if any(
            r.get(f+'_present') for f in ('width','stroke','fill','layer','dashes','clip'))}
        unavailable_values=sorted(set(parents)-known_values)
        rows.append(dict(edge_id=key,source_observation_ids=sorted(parents),
            w2_fragment_geometry_pt=edge['w2_fragment_geometry_pt'],w3_retained=edge['w3_retained'],
            matched_graphic_state_source_ids=matched,missing_graphic_state_source_ids=missing,
            source_parent_ownership_available=bool(parents),
            status=(EvidenceResolutionStatus.CANDIDATE.value if parents else EvidenceResolutionStatus.ABSTAINED.value),
            reason_codes=([] if parents else ['derived_fragment_source_parent_unavailable']),
            all_fragment_parent_descriptors_available=bool(parents) and not missing,
            graphic_values_unavailable_source_ids=unavailable_values,
            all_fragment_parents_have_graphic_state=bool(parents) and not unavailable_values,
            literal_source_graphic_state=lineage,graphic_state_authentication_from_join_alone=False,
            structural_wall_role_proven=False,physical_equivalence_proven=False,
            host_publication_allowed=False))
    return sorted(rows,key=lambda r:r['edge_id'])


def original_graphic_state_report(source_bytes,*,page_id,expected_source_sha):
    if type(source_bytes) is not bytes or sha256(source_bytes).hexdigest()!=expected_source_sha:
        raise ValueError('immutable original source PDF SHA mismatch')
    before=source_face_report(source_bytes,page_ids=(page_id,))
    foreground=original_full_foreground_report(source_bytes,page_id=page_id,
        expected_source_sha=expected_source_sha,trace=False)
    source,published,ordinary=_default_source(source_bytes,expected_source_sha,page_id)
    if encoded([asdict(r) for r in ordinary])!=encoded(foreground['ordinary_visible_source_records']):
        raise ValueError('fresh ordinary source record inventories disagree')
    records=tuple(SourceObservationRecord(**r) for r in [
        *foreground['ordinary_visible_source_records'],
        *(r['source_observation'] for r in foreground['authenticated_pixel_source_records'])])
    manifest=encoded([asdict(r) for r in records])
    segments,owned_ids,_,_=_source_page_segments(source_producer=source,published=published,
        source_bytes=source_bytes,page_id=page_id,decision_scope_id='graphic-state-shadow',
        resolved_visible_observations=tuple((r.observation_id,r) for r in ordinary))
    if set(owned_ids)!={r.observation_id for r in ordinary}:
        raise ValueError('ordinary graphic-state source universe mismatch')
    if {s.get('source_observation_id') for s in segments}!=set(owned_ids):
        raise ValueError('graphic-state rows do not cover exact ordinary source membership')
    graph=_trace_sources(records,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True,
        w4_identity_abstention_shadow=True)
    graph_bytes=encoded(graph)
    rows=join_graphic_state(graph,records,segments)
    if graph_bytes!=encoded(graph) or manifest!=encoded([asdict(r) for r in records]):
        raise RuntimeError('graphic state changed original graph or source records')
    if source.published_snapshot_for_revision(published.revision.revision_id)!=published:
        raise RuntimeError('graphic state changed original source snapshot')
    after=source_face_report(source_bytes,page_ids=(page_id,))
    if encoded(before)!=encoded(after):
        raise RuntimeError('graphic state changed original production receipts')
    return dict(source_sha256=expected_source_sha,page_id=page_id,
        original_source_reauthenticated=True,default_production_state_unchanged=True,
        original_production_receipts_sha256=sha256(encoded(before)).hexdigest(),
        original_production_summary=before['summary'],
        input_source_manifest_sha256=sha256(manifest).hexdigest(),
        exact_unmodified_graph_sha256=sha256(graph_bytes).hexdigest(),
        full_source_input_count=len(records),ordinary_source_graphic_record_count=len(ordinary),
        source_primitive_safety_cap=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        graphic_state_rows=rows,source_graph=graph,
        graphic_state_controls_topology_filtering=False,structural_wall_role_proven=False,
        physical_wall_authority=False,physical_equivalence_proven=False,
        host_publication_allowed=False,opening_count_publication_allowed=False,
        metric_quantity_publication_allowed=False,benchmark_accuracy=None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf',type=Path,required=True);p.add_argument('--page-id',required=True)
    p.add_argument('--expected-source-sha',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    r=original_graphic_state_report(a.pdf.read_bytes(),page_id=a.page_id,expected_source_sha=a.expected_source_sha)
    a.output.write_bytes(encoded(r)+b'\n')
    print(json.dumps(dict(inputs=r['full_source_input_count'],ordinary=r['ordinary_source_graphic_record_count'],
        unchanged_production=True,structural_wall_role_proven=False)))


if __name__=='__main__': main()
