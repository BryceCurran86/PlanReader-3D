"""Original-byte-authenticated full-page endpoint-index experiment, no hosts."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import SourceObservationRecord
from scripts.gptmax_exact_endpoint_flank_shadow import _local_records, annotate_source_span_coverage
from scripts.gptmax_full_foreground_flank_stages import _flank_stage_rows
from tools.diag_gptmax_full_foreground_flank import full_foreground_flank_census
from tools.diag_gptmax_full_foreground_run_source import original_full_foreground_report, _trace_sources
from tools.diag_gptmax_raster_host_source_membership import original_raster_host_ancestry_census
from tools.diag_gptmax_required_flank_source import required_flank_source_census


def _encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


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
        graph=_trace_sources(records,exact_endpoint_shadow=indexed,
            exact_endpoint_index_shadow=indexed)
        rows=_flank_stage_rows(joined,original,required,graph)
        annotate_source_span_coverage(rows,original,required)
        modes[name]=dict(source_graph=graph,opening_rows=rows)
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
