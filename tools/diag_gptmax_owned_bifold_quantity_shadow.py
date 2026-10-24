"""Replay original source through opt-in descriptor and existing quantity/seal producers.

This creates review artifacts only, never customer persistence or production
activation. Baseline source/host/frame/canonical/quantity/seal receipts are
retained separately and default recomposition must remain exactly equal.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_raster_opening_source_primitives import MAX_PRIMITIVES
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def owned_bifold_quantity_shadow_report(original_pdf: bytes, *, page_ids) -> dict:
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("original PDF bytes required")
    pages=tuple(page_ids)
    if (not pages or len(set(pages))!=len(pages) or any(
        type(p) is not str or not p.isdecimal() or int(p)<1 or str(int(p))!=p for p in pages)):
        raise ValueError("canonical original page selectors required")
    digest=sha256(original_pdf).hexdigest()
    source=SourceVisibilityProducer(producer_method='live-physical-net-wall',
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub=source.ingest_native_pdf_bytes(document_id=f'live-source:{digest[:32]}',
        source_bytes=original_pdf,source_locator='memory://owned-bifold-shadow.pdf',
        page_ids=tuple(int(p) for p in pages))
    composition=compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=pub.revision.revision_id,page_ids=pages)
    pub=source.published_snapshot_for_revision(pub.revision.revision_id)
    def voids(**flags):
        return compose_live_physical_opening_voids(source_visibility_producer=source,
            wall_opening_composition=composition,**flags)
    baseline=voids()
    before=_retention(composition,baseline,verify_customer_rows=True)
    candidate=voids(bifold_descriptor_shadow=True)
    after=_retention(composition,candidate,verify_customer_rows=True)
    old={q['quantity_id']:q for q in before['quantities']}
    new={q['quantity_id']:q for q in after['quantities']}
    if len(old)!=len(before['quantities']) or len(new)!=len(after['quantities']):
        raise RuntimeError('duplicate quantity address')
    if any(new.get(qid)!=q for qid,q in old.items()):
        raise RuntimeError('original quantity receipt changed')
    old_rows={r['quantity_id']:r for r in before['customer_rows']}
    new_rows={r['quantity_id']:r for r in after['customer_rows']}
    if any(new_rows.get(qid)!=row for qid,row in old_rows.items()):
        raise RuntimeError('original customer receipt changed')
    if any(before[k]!=after[k] for k in ('walls','hosts','frames')):
        raise RuntimeError('original source/host/frame receipt changed')
    canonical={r.physical_opening_id:r for r in candidate.canonical_openings}
    dimension=OpeningLabelDimensionProducer.from_source_visibility_producer(source,bifold_descriptor_shadow=True)
    semantics=OpeningLabelSemanticProducer.from_source_visibility_producer(source,bifold_descriptor_shadow=True)
    evidence=[]
    for quantity_id in sorted(new.keys()-old.keys()):
        q=new[quantity_id]
        if len(q['input_entity_ids'])!=1:raise RuntimeError('physical identity unavailable')
        identity=q['input_entity_ids'][0];opening=canonical[identity]
        selector=ObservationSelector(document_id=pub.revision.document_id,
            revision_id=pub.revision.revision_id,source_sha256=digest,
            snapshot_id=pub.snapshot.snapshot_id,observation_id=opening.representative_observation_id)
        physical=composition.physical_opening_authority.prove_existence(selector)
        label=dimension.publish_scope(selector);semantic=semantics.publish_scope(selector)
        if label.evidence is None or semantic.evidence is None or physical.existence_record is None:
            raise RuntimeError('original candidate evidence unavailable')
        host_selector=composition.binding_selectors[identity]
        host=composition.opening_host_binding_authority.resolve(host_selector)
        frame_selector=composition.host_frame_selectors.get(identity)
        frame=(composition.opening_host_frame_authority.resolve(frame_selector) if frame_selector else None)
        if host.record is None or frame is None or frame.evidence is None:
            raise RuntimeError('complete original host/frame unavailable')
        text=[]
        for oid in label.evidence.source_text_observation_ids:
            address=ObservationSelector(document_id=selector.document_id,revision_id=selector.revision_id,
                source_sha256=digest,snapshot_id=selector.snapshot_id,observation_id=oid)
            resolved=source.text_integrity_authority().resolve_text(address)
            if resolved.receipt is None or resolved.trusted_text is None:
                raise RuntimeError('original native text receipt unavailable')
            text.append(asdict(resolved))
        evidence.append(dict(quantity_id=quantity_id,canonical_opening=opening.to_dict(),
            physical_existence_result=asdict(physical),host_result=asdict(host),frame_result=asdict(frame),
            original_decision_scope_id=host.record.decision_scope_id,
            original_snapshot_id=pub.snapshot.snapshot_id,original_native_text_receipts=text,
            semantic_result=asdict(semantic),figured_label_result=asdict(label),quantity=q,
            customer_row=new_rows[quantity_id]))
    if (_retention(composition,voids(),verify_customer_rows=True)!=before
        or source.published_snapshot_for_revision(pub.revision.revision_id)!=pub
        or sha256(source._producer._store.source_bytes_by_revision[pub.revision.revision_id]).hexdigest()!=digest):
        raise RuntimeError('original production changed during shadow')
    return dict(status='UNPUBLISHED_SHADOW_REVIEW',source_sha256=digest,snapshot_id=pub.snapshot.snapshot_id,
        baseline_receipts=before,candidate_receipts=after,additional_quantity_evidence=evidence,
        original_quantity_and_customer_receipts_unchanged=True,
        original_source_host_frame_receipts_unchanged=True,default_recomposition_unchanged=True,
        count_granted=False,production_activation_granted=False,primitive_safety_cap=MAX_PRIMITIVES)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',type=Path,required=True)
    parser.add_argument('--page-id',action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=owned_bifold_quantity_shadow_report(args.pdf.read_bytes(),page_ids=args.page_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True))


if __name__=='__main__':main()
