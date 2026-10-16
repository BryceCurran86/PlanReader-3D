"""Compare actual production customer runs around an isolated source observer.

Decode scope is the production collector's own scope. No all-page diagnostic
seal or archived quantity value may substitute for these exact source claims.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import pb_live_physical_net_wall_integration as live
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_opening_customer_projection import project_live_opening_customer_rows
from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
from pb_migration_contracts import canonical_contract_json
from pb_source_visibility_authority import SourceVisibilityProducer


def _source_stage(composition):
    return dict(hosts=[asdict(r) for r in composition.opening_bindings],
        frames=[asdict(r) for r in composition.host_frames],
        wall_scopes=[asdict(s) for s in composition.physical_wall_candidate_authority._scopes.values()])


def _customer_receipt(claim,project_id):
    sealed=seal_live_opening_area_claim_run(claim,workspace_id=1,project_id=project_id)
    rows=project_live_opening_customer_rows(claim,workspace_id=1,project_id=project_id)
    verified=verify_sealed_customer_output(sealed,rows)
    return dict(canonical_openings=[o.to_dict() for o in claim.canonical_openings],
        original_quantities=[q.to_dict() for q in claim.opening_quantity_evidence],
        original_count_quantities=[q.to_dict() for q in claim.opening_count_quantity_evidence],
        sealed_run=sealed.to_dict(),customer_rows=rows,verification=asdict(verified))


def verify_original_customer_scope_retention(pdf:Path,*,page_indices:tuple[int,...],
    project_id:str,infill_opposition:bool=False,terminal_flanks:bool=False)->dict:
    if type(infill_opposition) is not bool or type(terminal_flanks) is not bool:
        raise ValueError('explicit boolean source observer mode required')
    if infill_opposition and terminal_flanks:
        raise ValueError('one independently addressed source experiment per run')
    if (not page_indices or any(type(p) is not int or p<0 for p in page_indices)
            or len(set(page_indices))!=len(page_indices)):
        raise ValueError('unique nonnegative production page indices required')
    digest=sha256(pdf.read_bytes()).hexdigest()
    original=live.compose_live_wall_opening_authority
    stages=[];observations=[];mode={'shadow':False}
    def transparent(*args,**kwargs):
        result=original(*args,**kwargs)
        stages.append(_source_stage(result))
        if mode['shadow']:
            source=kwargs['source_visibility_producer']
            if type(source) is not SourceVisibilityProducer:
                raise TypeError('actual production source required')
            revision=kwargs['revision_id']
            pub=source.published_snapshot_for_revision(revision)
            if pub is None or pub.revision.source_sha256!=digest:
                raise RuntimeError('original production source SHA mismatch')
            if terminal_flanks:
                from pb_g17_terminal_flank_source_shadow import build_g17_terminal_flank_source_inventory_shadow as reader
            elif infill_opposition:
                from pb_g17_source_infill_opposition_shadow import build_g17_source_infill_opposition_shadow as reader
            else:
                from pb_g17_plan_wall_scope_shadow import build_g17_plan_wall_scope_shadow as reader
            for page_id in result.page_ids:
                observations.append(reader(source,revision_id=revision,page_id=page_id))
            if source.published_snapshot_for_revision(revision)!=pub:
                raise RuntimeError('source observer changed production snapshot')
        return result
    # One process owns this transparent diagnostic hook; no production module
    # file is edited. Forward once, return the identical actual object, restore
    # even if the observer or downstream collector raises.
    try:
        live.compose_live_wall_opening_authority=transparent
        before=live.collect_live_physical_net_wall_claim(pdf,pages=page_indices,
            topology_pages=page_indices,room_area_support_pages=None)
        baseline=_customer_receipt(before,project_id)
        mode['shadow']=True
        after=live.collect_live_physical_net_wall_claim(pdf,pages=page_indices,
            topology_pages=page_indices,room_area_support_pages=None)
        candidate=_customer_receipt(after,project_id)
    finally:
        live.compose_live_wall_opening_authority=original
    if len(stages)!=2 or stages[0]!=stages[1] or baseline!=candidate:
        raise RuntimeError('original production wall/host/frame/quantity/seal/customer receipts changed')
    if len(observations)!=len(page_indices):
        raise RuntimeError('original source observer scope incomplete')
    stage_fingerprint=sha256(canonical_contract_json(stages[0]).encode()).hexdigest()
    return dict(source_sha256=digest,production_page_indices=page_indices,
        original_customer_scope_verified=True,all_actual_production_receipts_unchanged=True,
        source_stage_fingerprint=stage_fingerprint,source_observers=observations,
        baseline_customer_receipts=baseline,candidate_customer_receipts=candidate,
        new_host_granted=False,new_metric_quantity_granted=False,benchmark_score_granted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',required=True,type=Path)
    parser.add_argument('--page',required=True,type=int)
    parser.add_argument('--project-id',required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--infill-opposition',action='store_true')
    mode.add_argument('--terminal-flanks',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=verify_original_customer_scope_retention(args.pdf,page_indices=(args.page-1,),
        project_id=args.project_id,infill_opposition=args.infill_opposition,terminal_flanks=args.terminal_flanks)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    receipt=result['baseline_customer_receipts']
    print(json.dumps(dict(source_sha256=result['source_sha256'],
        original_customer_scope_verified=True,unchanged=True,
        verified_customer_rows=receipt['verification']['valid_quantity_count'],
        original_quantity_values=[q['value'] for q in receipt['original_quantities']],
        source_stage_fingerprint=result['source_stage_fingerprint'])))


if __name__=='__main__':
    main()
