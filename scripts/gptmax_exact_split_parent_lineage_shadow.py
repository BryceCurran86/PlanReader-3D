"""Original splitter-emitter source ancestry; shadow only, no host promotion."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import SourceObservationRecord
from scripts.gptmax_exact_source_fragment_bundles import join_actual_source_bundles
from tools.diag_gptmax_full_foreground_run_source import (
    _trace_sources, original_full_foreground_report,
)
from tools.diag_opening_wall_face_preservation import source_face_report


def encoded(value):
    return json.dumps(value,sort_keys=True,allow_nan=False,default=lambda x:x.value).encode()


def topology_only(graph):
    """Compare exact existing geometry/membership, never normalize topology."""
    copy=deepcopy(graph)
    copy.pop('source_parent_census')
    for row in (*copy['all_w2_edges'],*copy['all_snap_collapsed_fragments']):
        row.pop('source_observation_ids')
    for chain in copy['all_w4_abstained_chain_rows']:
        for fragment in chain['actual_owned_w3_fragment_rows']:
            fragment.pop('primitive_lineage')
            fragment.pop('source_observation_ids')
    return copy


def original_split_parent_report(source_bytes,*,expected_source_sha,page_id):
    if type(source_bytes) is not bytes or sha256(source_bytes).hexdigest()!=expected_source_sha:
        raise ValueError('immutable original source SHA mismatch')
    production_before=source_face_report(source_bytes,page_ids=(page_id,))
    foreground=original_full_foreground_report(source_bytes,expected_source_sha=expected_source_sha,page_id=page_id)
    records=tuple(SourceObservationRecord(**r) for r in [
        *foreground['ordinary_visible_source_records'],
        *(r['source_observation'] for r in foreground['authenticated_pixel_source_records'])])
    source_manifest=encoded([asdict(r) for r in records])
    if len(records)>MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError('original source input safety cap exceeded')
    options=dict(exact_endpoint_shadow=True,exact_endpoint_index_shadow=True,w4_identity_abstention_shadow=True)
    before=_trace_sources(records,**options)
    after=_trace_sources(records,**options,exact_split_parent_lineage_shadow=True)
    if encoded(topology_only(before))!=encoded(topology_only(after)):
        raise ValueError('split parent shadow changed actual topology or W4 dispositions')
    before_bundles=join_actual_source_bundles(before,records)
    after_bundles=join_actual_source_bundles(after,records)
    by_source={r.observation_id:r for r in records}
    old_edges={r['edge_id']:r for r in before['all_w2_edges']}
    recovered=[]
    for row in after['all_w2_edges']:
        old=old_edges[row['edge_id']]
        previous=set(old['source_observation_ids']);current=set(row['source_observation_ids'])
        if not previous<=current or not current<=by_source.keys():
            raise ValueError('split lineage lost or borrowed original parents')
        if previous!=current:
            recovered.append(dict(edge_id=row['edge_id'],source_geometry_pt=row['w2_fragment_geometry_pt'],
                previous_source_observation_ids=sorted(previous),
                exact_split_parent_observation_ids_added=sorted(current-previous),
                original_source_records=[asdict(by_source[p]) for p in sorted(current-previous)],
                w3_retained=row['w3_retained'],status=EvidenceResolutionStatus.CANDIDATE.value,
                original_input_source_reauthenticated=True,host_publication_allowed=False))
    old_by_edges={tuple(r['actual_w2_edge_ids']):r for r in before_bundles['actual_assembly_records']}
    recovered_bundles=[]
    for row in after_bundles['actual_assembly_records']:
        previous=old_by_edges[tuple(row['actual_w2_edge_ids'])]
        if not previous['all_fragment_source_parents_available'] and row['all_fragment_source_parents_available']:
            recovered_bundles.append(dict(before=previous,after=row))
    if source_manifest!=encoded([asdict(r) for r in records]):
        raise ValueError('shadow changed original input source records')
    production_after=source_face_report(source_bytes,page_ids=(page_id,))
    if encoded(production_before)!=encoded(production_after):
        raise ValueError('split parent shadow changed default production source receipts')
    return dict(source_sha256=expected_source_sha,page_id=page_id,
        original_source_reauthenticated=True,default_production_receipts_unchanged=True,
        original_production_receipts_sha256=sha256(encoded(production_before)).hexdigest(),
        original_production_summary=production_before['summary'],
        input_source_manifest_sha256=sha256(source_manifest).hexdigest(),input_source_count=len(records),
        source_primitive_safety_cap=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        exact_shadow_topology_membership_sha256=sha256(encoded(topology_only(after))).hexdigest(),
        actual_topology_and_w4_dispositions_unchanged=True,
        exact_candidate_abstention_partition_verified=after_bundles['exact_candidate_abstention_partition_verified'],
        before_parentless_retained_fragment_count=sum(not r['source_observation_ids'] for r in before['all_w2_edges'] if r['w3_retained']),
        after_parentless_retained_fragment_count=sum(not r['source_observation_ids'] for r in after['all_w2_edges'] if r['w3_retained']),
        recovered_split_fragment_rows=recovered,recovered_actual_assembly_source_ownership=recovered_bundles,
        source_ownership_is_not_structural_wall_role=True,physical_equivalence_proven=False,
        structural_wall_role_proven=False,host_publication_allowed=False,
        opening_count_publication_allowed=False,metric_quantity_publication_allowed=False,benchmark_accuracy=None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf',required=True,type=Path);p.add_argument('--page-id',required=True)
    p.add_argument('--expected-source-sha',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    r=original_split_parent_report(a.pdf.read_bytes(),expected_source_sha=a.expected_source_sha,page_id=a.page_id)
    a.output.write_bytes(encoded(r)+b'\n')
    print(json.dumps(dict(inputs=r['input_source_count'],recovered_fragments=len(r['recovered_split_fragment_rows']),
        recovered_assembly_source_ownership=len(r['recovered_actual_assembly_source_ownership']),
        default_source_unchanged=True,topology_unchanged=True,host_publication=False)))


if __name__=='__main__':main()
