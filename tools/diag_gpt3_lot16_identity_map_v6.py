from __future__ import annotations

import json
from pathlib import Path

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    collect_live_physical_net_wall_claim,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.run_source_closed_project_handoff import _source_page_scopes


PROJECT="au_qld_lot16_power"
PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
PROJECT_DIR=Path("benchmarks/frozen_holdout/full_plan_v2/projects")/PROJECT
ROOT=Path("artifacts/gpt3-lot16-exact-v6")
BBOX_TOL_PT=0.75


def bbox_from_geometry(geometry):
    values=tuple(float(v) for v in (geometry or ()))
    if len(values)==4:
        x0,y0,x1,y1=values
        return (min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
    if len(values)>=4 and len(values)%2==0:
        xs=values[0::2]
        ys=values[1::2]
        return (min(xs),min(ys),max(xs),max(ys))
    return None


def bbox_delta(a,b):
    return max(abs(float(x)-float(y)) for x,y in zip(a,b))


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    combined=json.loads((ROOT/f"{PROJECT}.json").read_text(encoding="utf-8"))
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

    topology,support,page_count=_source_page_scopes(PDF)
    all_pages=tuple(range(page_count))
    claim=collect_live_physical_net_wall_claim(
        PDF,
        pages=all_pages,
        topology_pages=topology,
        room_area_support_pages=support,
    )
    canonical_by_physical={
        str(o.physical_opening_id):o
        for o in claim.canonical_openings
    }

    # Native source observations have stable source-owned ids independent of the
    # later physical-opening authority graph. Re-ingest only to resolve exact
    # text receipts/bboxes referenced by the canonical opening provenance.
    payload=PDF.read_bytes()
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"live-source:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=tuple(str(i+1) for i in all_pages),
    )
    authority=source.authority()

    bindings=[]
    audit=[]
    used_items=set()

    for q in sorted(
        (x for x in combined.get("quantities",()) if not x.get("abstained",False)),
        key=lambda x:x["quantity_id"],
    ):
        qid=str(q["quantity_id"])
        refs=tuple(str(x) for x in (q.get("object_identity_refs") or ()) if str(x))
        if len(refs)!=1:
            raise SystemExit(f"{qid}: expected exactly one physical identity")
        physical_id=refs[0]
        canonical=canonical_by_physical.get(physical_id)

        resolved_text=[]
        if canonical is not None:
            candidate_ids=[
                str(x)
                for x in canonical.evidence_ids
                if str(x).startswith("source_observation_")
            ]
            seen=set()
            for observation_id in candidate_ids:
                if observation_id in seen:
                    continue
                seen.add(observation_id)
                result=authority.resolve_visible(ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                ))
                obs=result.observation
                if obs is None:
                    continue
                raw_text=str(getattr(obs,"raw_text","") or "").strip()
                bbox=bbox_from_geometry(getattr(obs,"geometry",()))
                if not raw_text or bbox is None:
                    continue
                resolved_text.append({
                    "observation_id":observation_id,
                    "bbox":bbox,
                })

        by_item={}
        for obs in resolved_text:
            for cand in frozen:
                delta=bbox_delta(obs["bbox"],cand["bbox"])
                if delta <= BBOX_TOL_PT:
                    existing=by_item.get(cand["benchmark_item_id"])
                    candidate={
                        "benchmark_item_id":cand["benchmark_item_id"],
                        "object_ref":cand["object_ref"],
                        "frozen_bbox":cand["bbox"],
                        "production_bbox":obs["bbox"],
                        "observation_id":obs["observation_id"],
                        "max_bbox_delta_pt":delta,
                    }
                    if existing is None or delta < existing["max_bbox_delta_pt"]:
                        by_item[cand["benchmark_item_id"]]=candidate

        matches=sorted(by_item.values(),key=lambda x:(x["max_bbox_delta_pt"],x["benchmark_item_id"]))
        status="UNMATCHED"
        if canonical is None:
            status="CANONICAL_OPENING_UNAVAILABLE"
        elif len(matches)>1:
            status="GEOMETRY_AMBIGUOUS"
        elif len(matches)==1 and matches[0]["benchmark_item_id"] not in used_items:
            match=matches[0]
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
            "canonical_opening_found":canonical is not None,
            "canonical_figured_area_record_id":(
                None if canonical is None else canonical.figured_area_record_id
            ),
            "canonical_evidence_id_count":(
                0 if canonical is None else len(canonical.evidence_ids)
            ),
            "resolved_text_observation_count":len(resolved_text),
            "status":status,
            "matches":[{
                **m,
                "frozen_bbox":list(m["frozen_bbox"]),
                "production_bbox":list(m["production_bbox"]),
            } for m in matches],
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
            "sealed_quantity_count":len([
                x for x in combined.get("quantities",()) if not x.get("abstained",False)
            ]),
            "canonical_opening_count":len(canonical_by_physical),
            "binding_count":len(bindings),
            "frozen_bbox_candidate_count":len(frozen),
            "audit":audit,
        },indent=2,sort_keys=True)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "sealed_quantity_count":len([
            x for x in combined.get("quantities",()) if not x.get("abstained",False)
        ]),
        "canonical_opening_count":len(canonical_by_physical),
        "binding_count":len(bindings),
        "frozen_bbox_candidate_count":len(frozen),
        "audit":audit,
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
