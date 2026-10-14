"""Use the actual customer transparency harness with one fixed source reader.

Only the diagnostic observer selection is temporarily routed. Production
collector, composition, signed export and verification always delegate to
their original implementation through the existing harness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pb_g17_source_infill_opposition_shadow as infill
from tools.verify_g17_original_customer_scope_retention import verify_original_customer_scope_retention


def verify_original_infill_endpoint_customer_retention(pdf, *, page_indices, project_id):
    original = infill.build_g17_source_infill_opposition_shadow
    def endpoint_reader(source, *, revision_id, page_id):
        return original(source,revision_id=revision_id,page_id=page_id,
            infill_endpoint_opposition=True)
    try:
        infill.build_g17_source_infill_opposition_shadow = endpoint_reader
        result = verify_original_customer_scope_retention(pdf,page_indices=page_indices,
            project_id=project_id,infill_opposition=True)
    finally:
        infill.build_g17_source_infill_opposition_shadow = original
    for observer in result['source_observers']:
        for partition in observer['candidate_partitions'].values():
            if 'source_endpoint_opposed_continuations' not in partition:
                raise RuntimeError('actual source endpoint observer not executed')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',required=True,type=Path)
    parser.add_argument('--page',required=True,type=int)
    parser.add_argument('--project-id',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=verify_original_infill_endpoint_customer_retention(args.pdf,
        page_indices=(args.page-1,),project_id=args.project_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(original_customer_scope_verified=result['original_customer_scope_verified'],
        verified_customer_rows=result['baseline_customer_receipts']['verification']['valid_quantity_count'],
        endpoint_barriers={name:len(p['source_endpoint_opposed_continuations'])
            for o in result['source_observers'] for name,p in o['candidate_partitions'].items()})))


if __name__=='__main__':
    main()
