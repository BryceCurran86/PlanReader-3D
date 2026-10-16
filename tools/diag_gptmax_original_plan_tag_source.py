"""Run source-owned plan tag census with full before/after signed retention."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_g17_original_plan_tag_census_shadow import build_g17_original_plan_tag_census_shadow
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def run_original_plan_tag_first_gate(source_bytes: bytes, *, page_id: str):
    digest=sha256(source_bytes).hexdigest()
    source=SourceVisibilityProducer(producer_method='live-physical-net-wall',
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    original=source.ingest_native_pdf_bytes(document_id=f'live-source:{digest[:32]}',
        source_bytes=source_bytes,source_locator='memory://original-g17-plan-tags.pdf')
    revision=original.revision.revision_id
    def composition():
        walls=compose_live_wall_opening_authority(source_visibility_producer=source,
            revision_id=revision,page_ids=(page_id,))
        voids=compose_live_physical_opening_voids(source_visibility_producer=source,
            wall_opening_composition=walls)
        return walls,voids
    walls,voids=composition()
    pub=source.published_snapshot_for_revision(revision)
    if pub is None or pub.revision.source_sha256!=digest:
        raise RuntimeError('original source producer SHA unavailable')
    baseline=_retention(walls,voids,verify_customer_rows=True)
    census=build_g17_original_plan_tag_census_shadow(source,walls,
        revision_id=revision,page_id=page_id)
    next_walls,next_voids=composition()
    after=_retention(next_walls,next_voids,verify_customer_rows=True)
    if (source.published_snapshot_for_revision(revision)!=pub
            or baseline!=after):
        raise RuntimeError('original wall/host/frame/area/seal/customer changed by census')
    return dict(source_sha256=digest,snapshot_id=pub.snapshot.snapshot_id,
        page_id=page_id,original_wall_host_frame_area_seal_customer_unchanged=True,
        baseline_customer_rows=len(baseline['customer_rows']),
        baseline_customer_verification=baseline['customer_verification'],
        census=census,new_binding_granted=False,new_metric_quantity_granted=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf',type=Path,required=True)
    p.add_argument('--page-id',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=run_original_plan_tag_first_gate(a.pdf.read_bytes(),page_id=a.page_id)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    c=result['census']
    print(json.dumps(dict(source_sha256=result['source_sha256'],
        source_tag_candidates=c['source_text_tag_candidates'],
        outside_apertures=c['candidate_outside_all_apertures'],
        authentic_openings=c['physical_opening_count'],
        customer_rows_unchanged=result['baseline_customer_rows'])))


if __name__=='__main__':
    main()
