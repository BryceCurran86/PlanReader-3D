from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from pb_migration_contracts import stable_contract_id
from pb_opening_label_dimension_authority import (
    OPENING_LABEL_DIMENSION_SCHEMA_VERSION,
    _resolve_owned_dimension_values_mm,
    _trusted_text_lines,
    parse_opening_label_dimensions,
)


PROJECT="au_qld_lot16_power"
PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
PROJECT_DIR=Path("benchmarks/frozen_holdout/full_plan_v2/projects")/PROJECT
ROOT=Path("artifacts/gpt3-lot16-exact-v4")
BBOX_TOL_PT=0.75


def bbox_delta(a,b):
    return max(abs(float(x)-float(y)) for x,y in zip(a,b))


def measurement_record_id(row):
    matches=[
        str(x) for x in (row.get("evidence_ids") or ())
        if str(x).startswith("opening_label_dimension_")
    ]
    if len(matches)!=1:
        raise SystemExit(
            f"expected exactly one opening-label measurement id for {row.get('quantity_id')}: {matches}"
        )
    return matches[0]


def candidate_evidence_ids(*, line, physical_id, page_id, viewport_id):
    parsed=parse_opening_label_dimensions(line.text)
    if parsed is None:
        return ()
    out=[]
    for semantic_kind in (None,"door","window"):
        for authenticated_semantic in (False,True):
            owned=_resolve_owned_dimension_values_mm(
                parsed,
                opening_record_id=physical_id,
                semantic_kind=semantic_kind,
                authenticated_semantic_evidence=authenticated_semantic,
            )
            if owned is None:
                continue
            values,compact_used=owned
            payload={
                "schema_version":OPENING_LABEL_DIMENSION_SCHEMA_VERSION,
                "opening_record_id":physical_id,
                "page_id":page_id,
                "viewport_id":viewport_id,
                "source_text_observation_ids":tuple(sorted(line.observation_ids)),
                "raw_text":parsed.raw_text,
                "dimension_values_mm":values,
                "compact_hundreds_used":compact_used,
                "semantic_kind":semantic_kind,
            }
            evidence_id=stable_contract_id(
                "opening_label_dimension",
                payload,
                digest_chars=32,
            )
            out.append((evidence_id,payload))
    unique={}
    for evidence_id,payload in out:
        unique.setdefault(evidence_id,payload)
    return tuple(unique.items())


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    combined=json.loads((ROOT/f"{PROJECT}.json").read_text(encoding="utf-8"))
    family=json.loads((ROOT/"family_runs/opening_area.sealed.json").read_text(encoding="utf-8"))
    source_sha=combined["source_sha256s"][0]

    takeoff=json.loads((PROJECT_DIR/"reference_takeoff.json").read_text(encoding="utf-8"))
    item_by_object_ref={}
    for item in takeoff.get("items",()):
        if not item.get("denominator_eligible",False):
            continue
        for ref in item.get("expected_object_refs",()):
            item_by_object_ref[str(ref)]=str(item["item_id"])

    truth=json.loads((PROJECT_DIR/"reference_truth_draft.json").read_text(encoding="utf-8"))
    frozen=[]
    for row in truth.get("verified_physical_candidates",()):
        attrs=row.get("attributes") or {}
        bbox=attrs.get("source_bbox_pdf_pt")
        object_ref=str(row.get("object_ref") or "")
        if (
            object_ref
            and object_ref in item_by_object_ref
            and isinstance(bbox,list)
            and len(bbox)==4
        ):
            frozen.append({
                "object_ref":object_ref,
                "benchmark_item_id":item_by_object_ref[object_ref],
                "bbox":tuple(float(v) for v in bbox),
            })

    by_qid={q["quantity_id"]:q for q in family.get("quantities",())}
    combined_ids={
        q["quantity_id"]
        for q in combined.get("quantities",())
        if not q.get("abstained",False)
    }
    if combined_ids != set(by_qid):
        raise SystemExit("combined/family opening-area quantity mismatch")

    # Capture the exact producer instance created by the production claim.
    # This keeps every derived snapshot minted by the real wall/opening chain.
    import pb_live_physical_net_wall_integration as live

    captured={}
    original_source_cls=live.SourceVisibilityProducer

    def _capture_source(*args,**kwargs):
        obj=original_source_cls(*args,**kwargs)
        captured["source"]=obj
        return obj

    live.SourceVisibilityProducer=_capture_source
    try:
        claim=live.collect_live_physical_net_wall_claim(
            PDF,
            pages=tuple(range(13)),
            topology_pages=(2,),
            room_area_support_pages=None,
        )
    finally:
        live.SourceVisibilityProducer=original_source_cls

    source=captured.get("source")
    if source is None:
        raise SystemExit("failed to capture production SourceVisibilityProducer")

    claim_qids={
        q.quantity_id
        for q in (getattr(claim,"opening_quantity_evidence",()) or ())
        if not q.abstained and q.value is not None
    }
    if claim_qids != combined_ids:
        raise SystemExit(
            f"captured claim/sealed quantity mismatch: claim={sorted(claim_qids)} sealed={sorted(combined_ids)}"
        )

    canonical_by_physical={
        str(o.physical_opening_id):o
        for o in (getattr(claim,"canonical_openings",()) or ())
    }

    bindings=[]
    audit=[]
    used_items=set()

    for qid in sorted(combined_ids):
        row=by_qid[qid]
        refs=tuple(str(x) for x in (row.get("object_identity_refs") or ()) if str(x))
        if len(refs)!=1:
            raise SystemExit(f"{qid}: expected exactly one physical identity")
        physical_id=refs[0]
        target_measurement=measurement_record_id(row)
        page_id=str(row.get("source_page") or "")
        viewport_id=str(row.get("viewport_id") or "") or None

        canonical=canonical_by_physical.get(physical_id)
        if canonical is None:
            raise SystemExit(f"{qid}: sealed physical id absent from captured production claim")
        if str(canonical.figured_area_record_id or "") != target_measurement:
            raise SystemExit(
                f"{qid}: sealed/captured measurement id mismatch: "
                f"{target_measurement} != {canonical.figured_area_record_id}"
            )

        # Production may advance the revision to newer derived snapshots after
        # this opening was canonicalised. Temporarily point the producer's
        # published snapshot at the exact immutable opening snapshot so the
        # page-level trusted-text helper sees the same source universe that
        # minted the sealed measurement record.
        producer=getattr(source,"_producer",None)
        store=getattr(producer,"_store",None)
        published_cache=getattr(source,"_published_by_revision",None)
        if store is None or published_cache is None:
            raise SystemExit("captured source internals unavailable")
        historical_snapshot=store.snapshots.get(canonical.snapshot_id)
        current_published=published_cache.get(canonical.revision_id)
        if historical_snapshot is None or current_published is None:
            raise SystemExit(
                f"{qid}: canonical source snapshot unavailable: {canonical.snapshot_id}"
            )
        # Diagnostic-only immutable snapshot replay. The text observation ids
        # are source-native and remain stable across derived snapshots; the
        # snapshot id controls the receipt/integrity lookup used by production.
        historical_published=type(current_published)(
            revision=current_published.revision,
            coverage=current_published.coverage,
            snapshot=historical_snapshot,
            base_source_snapshot_id=current_published.base_source_snapshot_id,
            visible_observation_ids=current_published.visible_observation_ids,
            text_observation_ids=current_published.text_observation_ids,
            ocr_tag_observation_ids=current_published.ocr_tag_observation_ids,
            raster_opening_primitive_observation_ids=(
                current_published.raster_opening_primitive_observation_ids
            ),
        )
        published_cache[canonical.revision_id]=historical_published
        try:
            scope=SimpleNamespace(
                document_id=canonical.document_id,
                revision_id=canonical.revision_id,
                source_sha256=canonical.source_sha256,
                snapshot_id=canonical.snapshot_id,
                page_id=canonical.page_id,
            )
            trusted_lines=_trusted_text_lines(source,scope)
        finally:
            published_cache[canonical.revision_id]=current_published

        evidence_matches=[]
        for line in trusted_lines:
            for evidence_id,payload_candidate in candidate_evidence_ids(
                line=line,
                physical_id=physical_id,
                page_id=str(canonical.page_id),
                viewport_id=canonical.viewport_id,
            ):
                if evidence_id == target_measurement:
                    evidence_matches.append({
                        "measurement_record_id":evidence_id,
                        "bbox":tuple(float(v) for v in line.bbox),
                        "source_text_observation_ids":tuple(line.observation_ids),
                        "payload":payload_candidate,
                    })

        # A sealed measurement record must resolve to exactly one source label
        # claim. Anything else remains unresolved instead of guessing.
        geometry_matches=[]
        if len(evidence_matches)==1:
            production_bbox=evidence_matches[0]["bbox"]
            by_item={}
            for cand in frozen:
                delta=bbox_delta(production_bbox,cand["bbox"])
                if delta <= BBOX_TOL_PT:
                    existing=by_item.get(cand["benchmark_item_id"])
                    candidate={
                        "benchmark_item_id":cand["benchmark_item_id"],
                        "object_ref":cand["object_ref"],
                        "frozen_bbox":cand["bbox"],
                        "production_bbox":production_bbox,
                        "max_bbox_delta_pt":delta,
                    }
                    if existing is None or delta < existing["max_bbox_delta_pt"]:
                        by_item[cand["benchmark_item_id"]]=candidate
            geometry_matches=sorted(
                by_item.values(),
                key=lambda x:(x["max_bbox_delta_pt"],x["benchmark_item_id"]),
            )

        status="UNMATCHED"
        if len(evidence_matches)>1:
            status="MEASUREMENT_EVIDENCE_AMBIGUOUS"
        elif len(evidence_matches)==1 and len(geometry_matches)>1:
            status="GEOMETRY_AMBIGUOUS"
        elif (
            len(evidence_matches)==1
            and len(geometry_matches)==1
            and geometry_matches[0]["benchmark_item_id"] not in used_items
        ):
            match=geometry_matches[0]
            used_items.add(match["benchmark_item_id"])
            bindings.append({
                "benchmark_item_id":match["benchmark_item_id"],
                "production_object_identity_refs":[physical_id],
                "production_family":"opening_area",
            })
            status="BOUND"

        audit.append({
            "quantity_id":qid,
            "physical_opening_id":physical_id,
            "measurement_record_id":target_measurement,
            "measurement_evidence_match_count":len(evidence_matches),
            "geometry_match_count":len(geometry_matches),
            "status":status,
            "evidence_matches":[{
                "measurement_record_id":m["measurement_record_id"],
                "bbox":list(m["bbox"]),
                "source_text_observation_ids":list(m["source_text_observation_ids"]),
            } for m in evidence_matches],
            "geometry_matches":[{
                **m,
                "frozen_bbox":list(m["frozen_bbox"]),
                "production_bbox":list(m["production_bbox"]),
            } for m in geometry_matches],
        })

    identity_map={
        "schema_version":"1.0.0",
        "project_id":PROJECT,
        "source_sha256s":combined["source_sha256s"],
        "bindings":bindings,
    }
    (ROOT/"lot16.identity-map.json").write_text(
        json.dumps(identity_map,indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    (ROOT/"lot16.identity-audit.json").write_text(
        json.dumps({
            "bbox_tolerance_pt":BBOX_TOL_PT,
            "sealed_quantity_count":len(combined_ids),
            "binding_count":len(bindings),
            "frozen_bbox_candidate_count":len(frozen),
            "audit":audit,
        },indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "sealed_quantity_count":len(combined_ids),
        "binding_count":len(bindings),
        "frozen_bbox_candidate_count":len(frozen),
        "audit":audit,
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
