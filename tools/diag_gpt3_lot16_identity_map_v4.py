from __future__ import annotations

import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PROJECT="au_qld_lot16_power"
PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
PROJECT_DIR=Path("benchmarks/frozen_holdout/full_plan_v2/projects")/PROJECT
ROOT=Path("artifacts/gpt3-lot16-exact-v4")
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

    payload=PDF.read_bytes()
    document_id=f"live-source:{source_sha[:32]}"
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published=source.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=tuple(str(i) for i in range(1,14)),
    )
    authority=source.authority()

    audit=[]
    bindings=[]
    used_items=set()
    resolved_obs_cache={}

    def resolve_observation(observation_id):
        if observation_id in resolved_obs_cache:
            return resolved_obs_cache[observation_id]
        selector=ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result=authority.resolve_visible(selector)
        resolved_obs_cache[observation_id]=result.observation
        return result.observation

    by_qid={q["quantity_id"]:q for q in family.get("quantities",())}
    combined_ids={q["quantity_id"] for q in combined.get("quantities",()) if not q.get("abstained",False)}
    family_ids=set(by_qid)
    if combined_ids != family_ids:
        raise SystemExit(
            f"combined/family quantity mismatch: combined={sorted(combined_ids)} family={sorted(family_ids)}"
        )

    for qid in sorted(combined_ids):
        row=by_qid[qid]
        refs=tuple(str(x) for x in (row.get("object_identity_refs") or ()) if str(x))
        source_obs_ids=[
            str(x)
            for x in (row.get("evidence_ids") or ())
            if str(x).startswith("source_observation_")
        ]
        source_observations=[]
        for observation_id in source_obs_ids:
            obs=resolve_observation(observation_id)
            if obs is None:
                continue
            raw_text=str(getattr(obs,"raw_text","") or "").strip()
            box=bbox_from_geometry(getattr(obs,"geometry",()))
            if not raw_text or box is None:
                continue
            source_observations.append({
                "observation_id":observation_id,
                "bbox":box,
            })

        match_by_item={}
        for obs in source_observations:
            for cand in frozen:
                delta=bbox_delta(obs["bbox"],cand["bbox"])
                if delta <= BBOX_TOL_PT:
                    key=cand["benchmark_item_id"]
                    existing=match_by_item.get(key)
                    candidate={
                        "benchmark_item_id":key,
                        "object_ref":cand["object_ref"],
                        "frozen_bbox":cand["bbox"],
                        "observation_id":obs["observation_id"],
                        "production_bbox":obs["bbox"],
                        "max_bbox_delta_pt":delta,
                    }
                    if existing is None or delta < existing["max_bbox_delta_pt"]:
                        match_by_item[key]=candidate

        matches=sorted(match_by_item.values(),key=lambda x:(x["max_bbox_delta_pt"],x["benchmark_item_id"]))
        status="UNMATCHED"
        if len(matches)==1 and len(refs)==1 and matches[0]["benchmark_item_id"] not in used_items:
            match=matches[0]
            used_items.add(match["benchmark_item_id"])
            bindings.append({
                "benchmark_item_id":match["benchmark_item_id"],
                "production_object_identity_refs":[refs[0]],
                "production_family":"opening_area",
            })
            status="BOUND"
        elif len(matches)>1:
            status="AMBIGUOUS"

        audit.append({
            "quantity_id":qid,
            "object_identity_refs":list(refs),
            "source_text_observation_count":len(source_observations),
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
        json.dumps(identity_map,indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    (ROOT/"lot16.identity-audit.json").write_text(
        json.dumps({
            "bbox_tolerance_pt":BBOX_TOL_PT,
            "sealed_quantity_count":len(combined_ids),
            "binding_count":len(bindings),
            "frozen_bbox_candidate_count":len(frozen),
            "resolved_source_observation_count":len(resolved_obs_cache),
            "audit":audit,
        },indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    print(json.dumps({
        "sealed_quantity_count":len(combined_ids),
        "binding_count":len(bindings),
        "frozen_bbox_candidate_count":len(frozen),
        "resolved_source_observation_count":len(resolved_obs_cache),
        "audit":audit,
    },indent=2,sort_keys=True))


if __name__=="__main__":
    main()
