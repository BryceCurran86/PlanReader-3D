"""One original Lot16 producer replay and read-only W3 source-parent census."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_g17_w3_original_parent_span_shadow import audit_g17_w3_short_arm_source_parents
from tools.diag_gptmax_producer_owned_g17_wall_shadow import producer_owned_wall_shadow_report


def original_source_w3_parent_report(source_bytes: bytes, *, page_id: str) -> dict:
    digest=sha256(source_bytes).hexdigest()
    result=producer_owned_wall_shadow_report(source_bytes,page_id=page_id,
                                            include_plan_wall_scope=True)
    if (result['source_sha256']!=digest
            or not result['all_original_sealed_customer_rows_unchanged']
            or not result['all_original_wall_host_frame_area_receipts_unchanged']
            or not result['published_source_snapshot_unchanged']
            or result['new_physical_host_or_metric_granted']):
        raise RuntimeError("source producer retained neither wall/host/frame nor signed customers")
    original=result['isolated_300_dpi_plan_wall_scope_shadow']
    if (original is None or original['source_sha256']!=digest
            or original['snapshot_id']!=result['snapshot_id']
            or not original['source_viewport_ownership_id']):
        raise RuntimeError("original producer owned plan view unavailable")
    census=audit_g17_w3_short_arm_source_parents(original)
    verification=result['original_sealed_customer_receipts']['customer_verification']
    if verification['valid_quantity_count']!=len(result['original_sealed_customer_receipts']['customer_rows']):
        raise RuntimeError("original customer receipts are not fully verified")
    return dict(source_sha256=digest,snapshot_id=result['snapshot_id'],page_id=page_id,
        verified_signed_customer_count=verification['valid_quantity_count'],
        original_host_count=result['original_host_count'],
        original_frame_count=result['original_frame_count'],
        original_physical_opening_count=result['original_physical_opening_count'],
        all_original_signed_customer_and_host_frame_receipts_unchanged=True,
        source_producer_replayed_original_immutable_PDF=True,
        independent_W3_original_parent_shadow=census,
        new_structural_wall_host_metric_or_count_granted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',required=True,type=Path)
    parser.add_argument('--page-id',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=original_source_w3_parent_report(args.pdf.read_bytes(),page_id=args.page_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    shadow=result['independent_W3_original_parent_shadow']
    print(json.dumps(dict(source_sha256=result['source_sha256'],
        signed_customer_count=result['verified_signed_customer_count'],
        short_arm_count={k:len(v) for k,v in
            shadow['candidate_only_short_child_original_parent_results'].items()}),sort_keys=True))


if __name__=='__main__':
    main()
