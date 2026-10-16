"""Read-only derived G17 source-span report from a same-source producer replay.

Only a separately SHA-checked original PDF producer run can authenticate input;
this serialized diagnostic NEVER re-verifies PDF bytes or grants wall/host/count
or commercial authority. Preserve every opposing/unknown original source row.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace as N

from pb_g17_source_interval_coverage_shadow import audit_g17_original_source_interval_coverage


def _wall(row):
    return N(wall_candidate_id=row['wall_candidate_id'],source_edge_fragments=tuple(
        N(edge_id=x['edge_id'],geometry=x['geometry'],source_primitive_ids=x['source_primitive_ids'])
        for x in row['source_edge_fragments']))


def audit_serialized_original_g17_intervals(source_report: dict, *, expected_sha256: str) -> dict:
    if (source_report.get('source_sha256')!=expected_sha256
            or source_report.get('primitive_safety_cap')!=20_000
            or source_report.get('published_source_snapshot_unchanged') is not True
            or source_report.get('all_original_wall_host_frame_area_receipts_unchanged') is not True
            or source_report.get('all_original_sealed_customer_rows_unchanged') is not True):
        raise ValueError('verified source and original customer controls required')
    plan=source_report['isolated_300_dpi_plan_wall_scope_shadow']
    for field in ('source_sha256','snapshot_id','page_id'):
        if plan[field]!=source_report[field]:
            raise ValueError('G17 source lineage mismatch')
    if not plan['source_viewport_ownership_id'] or any(plan[k] for k in (
            'scope_complete','structural_wall_role_granted','physical_wall_equivalence_granted',
            'host_granted','metric_quantity_granted')):
        raise ValueError('original isolated source-only plan scope required')
    source_rows={}
    for row in plan['source_primitive_dispositions']:
        observed=row['observation_id']
        if observed in source_rows:
            raise ValueError('duplicate original source observation')
        source_rows[observed]=row
    if len(source_rows)!=plan['source_primitive_count']:
        raise ValueError('original source inventory incomplete')
    modes=('default_w2_w3_w4','exact_coordinate_w2_w3_w4')
    candidates={mode:tuple(_wall(x) for x in plan[mode]['w4_records']) for mode in modes}
    opened={row['record']['record_id'] for row in plan['physical_openings']}
    if len(opened)!=len(plan['physical_openings']):
        raise ValueError('physical opening identities are not unique')
    results=[]
    for case in sorted(source_report['opening_local_source_shadows'],key=lambda x:x['physical_opening_id']):
        name=case['physical_opening_id']
        if name not in opened or case['status']!='abstained' or case['opening_host_granted']:
            raise ValueError('unverified or promoted source opening')
        flanks=[]
        for flank in case['flanks']:
            originals=[]
            ineligible=[]
            for oid in flank['source_observation_ids']:
                row=source_rows.get(oid)
                if row is None:
                    raise ValueError('opening flank outside source producer inventory')
                # A positive opening-local inset witness is NOT equivalent to
                # full original primitive paint. Carry false spans as negatives.
                positive=(row['drawing_disposition']=='inside'
                          and row['inside_original_image_regions'] is True
                          and row['source_paint']['original_solid_and_unchanged'] is True)
                if positive:
                    originals.append(N(edge_id=oid,geometry=row['geometry'],
                                       source_primitive_ids=(row['source_primitive_id'],)))
                else:
                    ineligible.append(dict(observation_id=oid,
                        drawing_disposition=row['drawing_disposition'],
                        full_original_paint_supported=bool(row['source_paint']['original_solid_and_unchanged'])))
            graph_results={}
            for mode in modes:
                assessment=audit_g17_original_source_interval_coverage(originals,candidates[mode])
                source_edges=assessment['original_source_edges']
                first_reasons=Counter(x['first_blocker'] for x in source_edges)
                full=sum(any(x['complete_original_interval_candidate'] for x in row['competing_wall_candidates'])
                         for row in source_edges)
                graph_results[mode]=dict(full_original_source_intervals_with_candidate_coverage=full,
                    source_interval_first_blockers=dict(sorted(first_reasons.items())),
                    same_primitive_candidate_interval_witnesses=sum(
                        sum(bool(x['source_owned_interval_witnesses']) for x in row['competing_wall_candidates'])
                        for row in source_edges),
                    structural_wall_role_granted=False, physical_equivalence_granted=False)
            flanks.append(dict(opening_local_paint_supported=flank['source_ink_supported'],
                original_full_paint_source_count=len(originals),
                original_full_paint_negative_observations=tuple(ineligible),
                graph_diagnostics=graph_results,opening_host_granted=False))
        results.append(dict(physical_opening_id=name,flanks=flanks,
            source_wall_role_granted=False,host_granted=False,metric_quantity_granted=False))
    if not results:
        raise ValueError('original source has no opening-local unresolved cases')
    return dict(source_sha256=expected_sha256,snapshot_id=source_report['snapshot_id'],
        page_id=source_report['page_id'],original_source_reauthentication_performed=False,
        source_producer_archived_customer_receipts_unchanged=True,
        unhosted_openings_examined=len(results),openings=results,
        new_host_granted=False,new_metric_quantity_granted=False,
        original_opening_universe_complete_proven=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-report',type=Path,required=True)
    parser.add_argument('--expected-source-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    content=args.original_report.read_bytes()
    derived=audit_serialized_original_g17_intervals(json.loads(content),
        expected_sha256=args.expected_source_sha)
    derived['read_only_source_report_sha256']=sha256(content).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(derived,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(unhosted_openings_examined=derived['unhosted_openings_examined'],
                          no_new_host=not derived['new_host_granted'],source_sha256=derived['source_sha256'])))


if __name__=='__main__':
    main()
